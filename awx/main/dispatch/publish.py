import inspect
import logging
import sys
from uuid import uuid4
from functools import wraps
from time import time

from django.conf import settings
from kombu import Connection, Exchange, Producer

from awx.main.utils.pglock import advisory_lock

logger = logging.getLogger('awx.main.dispatch')


def serialize_task(f):
    return '.'.join([f.__module__, f.__name__])


class task:
    """
    Used to decorate a function or class so that it can be run asynchronously
    via the task dispatcher.  Tasks can be simple functions:

    @task()
    def add(a, b):
        return a + b

    ...or classes that define a `run` method:

    @task()
    class Adder:
        def run(self, a, b):
            return a + b

    # Tasks can be run synchronously...
    assert add(1, 1) == 2
    assert Adder().run(1, 1) == 2

    # ...or published to a queue:
    add.apply_async([1, 1])
    Adder.apply_async([1, 1])

    # Tasks can also define a specific target queue or exchange type:

    @task(queue='slow-tasks')
    def snooze():
        time.sleep(10)

    @task(queue='tower_broadcast', exchange_type='fanout')
    def announce():
        print "Run this everywhere!"
    """

    def __init__(self, queue=None, exchange_type=None):
        self.queue = queue
        self.exchange_type = exchange_type

    def __call__(self, fn=None):
        queue = self.queue
        exchange_type = self.exchange_type

        class PublisherMixin(object):

            queue = None

            @classmethod
            def delay(cls, *args, **kwargs):
                return cls.apply_async(args, kwargs)

            @classmethod
            def apply_async(cls, args=None, kwargs=None, queue=None, uuid=None, **kw):
                task_id = uuid or str(uuid4())
                args = args or []
                kwargs = kwargs or {}
                queue = (
                    queue or
                    getattr(cls.queue, 'im_func', cls.queue) or
                    settings.CELERY_DEFAULT_QUEUE
                )
                obj = {
                    'uuid': task_id,
                    'args': args,
                    'kwargs': kwargs,
                    'task': cls.name
                }
                obj.update(**kw)
                if callable(queue):
                    queue = queue()
                if not settings.IS_TESTING(sys.argv):
                    with Connection(settings.BROKER_URL) as conn:
                        exchange = Exchange(queue, type=exchange_type or 'direct')
                        producer = Producer(conn)
                        logger.debug('publish {}({}, queue={})'.format(
                            cls.name,
                            task_id,
                            queue
                        ))
                        producer.publish(obj,
                                         serializer='json',
                                         compression='bzip2',
                                         exchange=exchange,
                                         declare=[exchange],
                                         delivery_mode="persistent",
                                         routing_key=queue)
                return (obj, queue)

        # If the object we're wrapping *is* a class (e.g., RunJob), return
        # a *new* class that inherits from the wrapped class *and* BaseTask
        # In this way, the new class returned by our decorator is the class
        # being decorated *plus* PublisherMixin so cls.apply_async() and
        # cls.delay() work
        bases = []
        ns = {'name': serialize_task(fn), 'queue': queue}
        if inspect.isclass(fn):
            bases = list(fn.__bases__)
            ns.update(fn.__dict__)
        cls = type(
            fn.__name__,
            tuple(bases + [PublisherMixin]),
            ns
        )
        if inspect.isclass(fn):
            return cls

        # if the object being decorated is *not* a class (it's a Python
        # function), make fn.apply_async and fn.delay proxy through to the
        # PublisherMixin we dynamically created above
        setattr(fn, 'name', cls.name)
        setattr(fn, 'apply_async', cls.apply_async)
        setattr(fn, 'delay', cls.delay)
        return fn


def get_names(func_name, args):
    name = func_name
    # If function takes args, then make lock specific to those args
    if args:
        name += '_' + ','.join([str(arg) for arg in args])
    wait_name = name + '_wait'
    return (name, wait_name)


def lazy_execute(f):
    @wraps(f)
    def new_func(*args, **kwargs):
        name, wait_name = get_names(f.__name__, args)

        # Non-blocking, acquire the wait lock
        wait_lock_cm = advisory_lock(wait_name, wait=False)
        wait_lock_result = wait_lock_cm.__enter__()
        if not wait_lock_result:
            logger.debug('Another process waits to carry out {}, exiting.'.format(name))
            wait_lock_cm.__exit__(None, None, None)
            return

        # blocking, acquire the compute lock
        start = time()
        logger.debug('Going to wait for {} lock before performing task.'.format(name))
        with advisory_lock(name, wait=True):
            delta = time() - start
            msg = 'Took {} seconds to obtain {} lock, running now.'.format(delta, name)
            if delta < 0.1:
                logger.debug(msg)
            else:
                logger.info(msg)
            wait_lock_cm.__exit__(None, None, None)
            return f(*args, **kwargs)

    return new_func


def lazy_apply_async(orig_fn):
    @wraps(orig_fn.apply_async)
    def new_apply_async(cls, args=None, kwargs=None, queue=None, uuid=None, **kw):
        name, wait_name = get_names(orig_fn.__name__, args)
        with advisory_lock(wait_name, wait=False) as wait_lock:
            if wait_lock:
                logger.debug('Submitting task with lock {}.'.format(name))  # TODO: remove log
                return orig_fn.apply_async.apply_async(args=args, kwargs=kwargs, queue=queue, uuid=uuid, **kw)
            else:
                logger.debug('Task {} already queued, not submitting.'.format(name))
    return new_apply_async


class lazy_task:
    """
    task wrapper to schedule time-sensitive idempotent tasks efficiently
    see section in docs/tasks.md
    """
    def __init__(self, *args, **kwargs):
        # Saves the instantiated version of the general task decorator for later
        self.task_decorator = task(*args, **kwargs)

    def __call__(self, fn=None):
        if not inspect.isfunction(fn):
            raise RuntimeError('lazy tasks only supported for functions, given {}'.format(fn))
        # This converts the function into a lazier version of itself
        # which is picky about whether it will perform the work
        # or not, depending on breadcrumbs from other processes
        patient_fn = lazy_execute(fn)

        # This is passing-through the original task decorator that all tasks use
        task_fn = self.task_decorator(patient_fn)

        # lazy_apply_async checks for active locks to determine
        # if there is a need to schedule the task or, bail as no-op
        setattr(task_fn, 'apply_async', lazy_apply_async(task_fn))

        return task_fn

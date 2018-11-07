import logging
import json
from functools import wraps
from importlib import import_module
from inspect import isfunction

# Django
from django.db.models import DateTimeField, Model, CharField
from django.db import connection, IntegrityError

# solo, Django app
from solo.models import SingletonModel

# AWX
from awx.main.utils.pglock import advisory_lock
from awx.main.dispatch.publish import task


__all__ = ['TowerScheduleState', 'lazy_task', 'resubmit_lazy_tasks']

logger = logging.getLogger('awx.main.dispatch')


class TowerScheduleState(SingletonModel):
    schedule_last_run = DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.schedule_last_run.strftime('%Y%m%dT%H%M%SZ')


LAZY_TASK_MODULES = {}


class TaskRescheduleFlag(Model):
    """Used by the lazy_task decorator.
    Names are a slug, corresponding to task combined with arguments.
    """
    name = CharField(unique=True, max_length=512, primary_key=True)

    class Meta:
        app_label = 'main'

    def __unicode__(self):
        return self.name

    @staticmethod
    def get_task_name(func_name, args):
        name = func_name
        # If function takes args, then make lock specific to those args
        if args:
            name += ':' + json.dumps(args)
        return name

    @staticmethod
    def import_task(name):
        module = import_module(LAZY_TASK_MODULES[name])
        _call = None
        if hasattr(module, name):
            _call = getattr(module, name, None)
        return _call

    @staticmethod
    def parse_args(args_str):
        return json.loads(args_str)

    def get_task_and_args(self):
        name, args_str = self.name.split(':', 1)
        fn = TaskRescheduleFlag.import_task(name)
        args = TaskRescheduleFlag.parse_args(args_str)
        return (fn, args)


def lazy_execute(f):
    @wraps(f)
    def new_func(*args, **kwargs):
        name = TaskRescheduleFlag.get_task_name(f.__name__, args)

        # NOTE: In a stricter form of this scheme, we would check the flag
        # and exit here if not set
        # this weaker form still allows periodic runs to do work

        # non-blocking, acquire the compute lock
        with advisory_lock(name, wait=False) as compute_lock:
            if not compute_lock:
                try:
                    TaskRescheduleFlag.objects.create(name=name)
                    logger.debug('Another process is doing {}, rescheduled for after it completes.'.format(name))
                    with advisory_lock(name, wait=False) as compute_lock2:
                        gave_up_lock = bool(compute_lock2)
                    if gave_up_lock:
                        f.apply_async(args=args, kwargs=kwargs)
                        logger.debug('Resubmitted task {} due to race condition.'.format(name))
                except IntegrityError:
                    logger.debug('Another process is doing {}, reschedule is already planned, no-op.'.format(name))
                return

            # Claim flag, a flag may or may not exist, this is fire-and-forget
            TaskRescheduleFlag.objects.filter(name=name).delete()
            logger.debug('Obtained {} lock, now I am obligated to perform the work.'.format(name))

            try:
                return f(*args, **kwargs)
            finally:
                # This is import to maintain the execution chain
                try:
                    if TaskRescheduleFlag.objects.filter(name=name).exists():
                        # Another process requested re-scheduling while running, re-submit
                        f.apply_async(args=args, kwargs=kwargs)
                        logger.debug('Resubmitted task {}.'.format(name))
                    else:
                        logger.debug('Work for {} lock has been cleared.'.format(name))
                except Exception:
                    logger.exception('Resubmission check of task {} failed, unexecuted work could remain.'.format(name))

    return new_func


def lazy_apply_async(orig_fn):
    def new_apply_async(args=None, kwargs=None, queue=None, uuid=None, **kw):
        if connection.in_atomic_block:
            raise RuntimeError('Idempotent tasks should NEVER be called inside a transaction, use on_commit.')

        name = TaskRescheduleFlag.get_task_name(orig_fn.__name__, args)

        if TaskRescheduleFlag.objects.filter(name=name).exists():
            logger.debug('Reschedule already planned for {}, no-op.'.format(name))
            return  # Reschedule is already planned
            # NOTE: returning here creates the need to reschedule lost processes
            # alternative would be to check the flag & the lock in this method

        # NOTE: setting the flag needs to happen before advisory_lock check, to avoid race condition
        # we count on the running process picking up the flag
        try:
            TaskRescheduleFlag.objects.create(name=name)
        except IntegrityError:
            # Likely race condition, another process created it in last 0.005 seconds, which is fine
            pass

        with advisory_lock(name, wait=False) as compute_lock:
            lock_available = bool(compute_lock)

        if not lock_available:
            logger.debug('Task {} already queued, not submitting.'.format(name))
            return

        logger.debug('Submitting task with lock {}.'.format(name))  # TODO: remove log
        return orig_fn.apply_async(args=args, kwargs=kwargs, queue=queue, uuid=uuid, **kw)

    return new_apply_async


def lazy_delay(orig_fn):
    def new_delay(*args, **kwargs):
        return orig_fn.lazy_apply_async(args, kwargs)
    return new_delay


def lazy_task(*args, **kwargs):
    """
    task wrapper to schedule time-sensitive idempotent tasks efficiently
    see section in docs/tasks.md
    """
    # Saves the instantiated version of the general task decorator for later
    task_decorator = task(*args, **kwargs)

    def new_decorator(fn):
        if not isfunction(fn):
            raise RuntimeError('lazy tasks only supported for functions, given {}'.format(fn))

        # This is passing-through the original task decorator that all tasks use
        task_fn = task_decorator(fn)

        # This converts the function into a lazier version of itself which
        # may or may not perform the work, depending on breadcrumbs from other processes
        lazy_fn = lazy_execute(task_fn)

        # copy tasks bound to the PublisherMixin from dispatch code
        LAZY_TASK_MODULES[fn.__name__] = task_fn.name.rsplit('.', 1)[0]
        setattr(lazy_fn, 'name', task_fn.name)
        setattr(lazy_fn, 'apply_async', task_fn.apply_async)
        setattr(lazy_fn, 'delay', task_fn.delay)
        # lazy_apply_async checks for active locks to determine
        # if there is a need to schedule the task or, bail as no-op
        setattr(lazy_fn, 'lazy_apply_async', lazy_apply_async(lazy_fn))
        setattr(lazy_fn, 'lazy_delay', lazy_delay(lazy_fn))

        return lazy_fn

    return new_decorator


@lazy_task()
def resubmit_lazy_tasks():
    """Fallback in case that processes running tasks were terminated unexpectedly
    """
    for flag in TaskRescheduleFlag.objects.all():
        with advisory_lock(flag.name, wait=False) as compute_lock:
            lock_available = bool(compute_lock)
        if not lock_available:
            continue  # already being ran, good
        fn, args = flag.get_task_and_args()
        fn.apply_async(args=args)

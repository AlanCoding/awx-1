import inspect
import logging
from functools import wraps

# Django
from django.db.models import DateTimeField, Model, CharField
from django.db import connection

# solo, Django app
from solo.models import SingletonModel

# AWX
from awx.main.utils.pglock import advisory_lock
from awx.main.dispatch.publish import task


__all__ = ['TowerScheduleState', 'lazy_task']

logger = logging.getLogger('awx.main.dispatch')


class TowerScheduleState(SingletonModel):
    schedule_last_run = DateTimeField(auto_now_add=True)


class TaskRescheduleFlag(Model):
    """Used by the lazy_task decorator.
    Names are a slug, corresponding to task combined with arguments.
    """
    name = CharField(unique=True)

    class Meta:
        app_label = 'main'


def get_task_name(func_name, args):
    name = func_name
    # If function takes args, then make lock specific to those args
    if args:
        name += '_' + ','.join([str(arg) for arg in args])
    return name


def lazy_execute(f):
    @wraps(f)
    def new_func(*args, **kwargs):
        name = get_task_name(f.__name__, args)

        # Check flag
        try:
            flag = TaskRescheduleFlag.objects.filter(name=name)
        except TaskRescheduleFlag.DoesNotExist:
            logger.debug('Another process seems to have already done {}, exiting.'.format(name))
            return

        # non-blocking, acquire the compute lock
        with advisory_lock(name, wait=False) as compute_lock:
            if not compute_lock:
                logger.debug('Another process is doing {}, reschedule is planned, no-op.'.format(name))
                return

            # Claim flag
            try:
                flag.delete()
            except TaskRescheduleFlag.DoesNotExist:  # TODO: also get right exception here
                logger.debug('Another process seems to have already done {}, exiting.'.format(name))
                return

            logger.debug('Obtained {} lock, now I am obligated to perform the work.'.format(name))
            try:
                return f(*args, **kwargs)
            finally:
                # This is import to maintain the execution chain
                try:
                    if TaskRescheduleFlag.objects.exists(name=name):
                        # Another process requested re-scheduling while running, re-submit
                        f.apply_async(args=args, kwargs=kwargs, precheck=False)
                except Exception:
                    logger.exception('Resubmission check of task {} failed, unexecuted work could remain.'.format(name))

    return new_func


def lazy_apply_async(orig_fn):
    @wraps(orig_fn.apply_async)
    def new_apply_async(cls, args=None, kwargs=None, queue=None, uuid=None, precheck=True, **kw):
        if not precheck:
            return orig_fn.apply_async(args=args, kwargs=kwargs, queue=queue, uuid=uuid, **kw)

        name = get_task_name(orig_fn.__name__, args)

        if TaskRescheduleFlag.objects.filter(name=name).exists():
            return  # Reschedule is already planned

        if connection.in_atomic_block:
            raise RuntimeError('Idempotent tasks should NEVER be called inside a transaction, use on_commit.')

        try:
            TaskRescheduleFlag.objects.create(name=name)
        except Exception:  # TODO: change to exact exception
            # Likely race condition, another process created it in last 0.005 seconds, which is fine
            return

        with advisory_lock(name, wait=False) as compute_lock:
            lock_available = bool(compute_lock)

        if lock_available:
            logger.debug('Submitting task with lock {}.'.format(name))  # TODO: remove log
            return orig_fn.apply_async(args=args, kwargs=kwargs, queue=queue, uuid=uuid, **kw)
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

        # This is passing-through the original task decorator that all tasks use
        task_fn = self.task_decorator(
            # This converts the function into a lazier version of itself which
            # may or may not perform the work, depending on breadcrumbs from other processes
            lazy_execute(fn)
        )

        # lazy_apply_async checks for active locks to determine
        # if there is a need to schedule the task or, bail as no-op
        setattr(task_fn, 'apply_async', lazy_apply_async(task_fn))

        return task_fn

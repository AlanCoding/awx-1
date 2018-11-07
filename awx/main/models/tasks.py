import inspect
import logging
from functools import wraps

# Django
from django.db.models import DateTimeField, Model, CharField
from django.db import connection, IntegrityError

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
            name += ':' + ','.join([str(arg) for arg in args])
        return name


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
                except IntegrityError:
                    logger.debug('Another process is doing {}, reschedule is already planned, no-op.'.format(name))
                return

            # Claim flag, a flag may or may not exist, this is fire-and-forget
            # TaskRescheduleFlag.objects.filter(name=name).delete()
            logger.debug('Obtained {} lock, now I am obligated to perform the work.'.format(name))

            try:
                return f(*args, **kwargs)
            finally:
                pass
                # This is import to maintain the execution chain
                try:
                    if TaskRescheduleFlag.objects.filter(name=name).exists():
                        # Another process requested re-scheduling while running, re-submit
                        f.apply_async(args=args, kwargs=kwargs)
                except Exception:
                    logger.exception('Resubmission check of task {} failed, unexecuted work could remain.'.format(name))

    return new_func


def lazy_apply_async(orig_fn):
    def new_apply_async(cls, args=None, kwargs=None, queue=None, uuid=None, **kw):
        name = TaskRescheduleFlag.get_task_name(orig_fn.__name__, args)

        if TaskRescheduleFlag.objects.filter(name=name).exists():
            logger.debug('Reschedule already planned for {}, no-op.'.format(name))  # TODO: remove log
            return  # Reschedule is already planned

        if connection.in_atomic_block:
            raise RuntimeError('Idempotent tasks should NEVER be called inside a transaction, use on_commit.')

        # NOTE: this needs to happen before advisory_lock check, to avoid race condition
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


def lazy_task(*args, **kwargs):
    """
    task wrapper to schedule time-sensitive idempotent tasks efficiently
    see section in docs/tasks.md
    """
    # Saves the instantiated version of the general task decorator for later
    task_decorator = task(*args, **kwargs)

    def new_decorator(fn):
        if not inspect.isfunction(fn):
            raise RuntimeError('lazy tasks only supported for functions, given {}'.format(fn))

        # This is passing-through the original task decorator that all tasks use
        task_fn = task_decorator(fn)

        # This converts the function into a lazier version of itself which
        # may or may not perform the work, depending on breadcrumbs from other processes
        lazy_fn = lazy_execute(task_fn)

        # copy tasks bound to the PublisherMixin from dispatch code
        setattr(lazy_fn, 'name', task_fn.name)
        setattr(lazy_fn, 'apply_async', task_fn.apply_async)
        setattr(lazy_fn, 'delay', task_fn.delay)
        # lazy_apply_async checks for active locks to determine
        # if there is a need to schedule the task or, bail as no-op
        setattr(lazy_fn, 'lazy_apply_async', lazy_apply_async(task_fn))

        return lazy_fn

    return new_decorator

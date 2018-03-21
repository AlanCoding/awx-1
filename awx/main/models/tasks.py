import logging
import json
from functools import wraps
from importlib import import_module
from inspect import isfunction

# Django
from django.db.models import DateTimeField, Model, CharField
from django.db import connection, transaction, IntegrityError
from django.conf import settings

# solo, Django app
from solo.models import SingletonModel

# AWX
from awx.main.utils.pglock import advisory_lock
from awx.main.dispatch.publish import task


__all__ = ['TowerScheduleState', 'lazy_task']

logger = logging.getLogger('awx.main.models.tasks')


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
    def gently_set_flag(name):
        """Create a flag in a way that avoids interference with any
        other actomic blocks that may be active
        """
        if connection.in_atomic_block:
            # Nesting transaction block does not set parent rollback
            with transaction.atomic():
                TaskRescheduleFlag.objects.create(name=name)
        else:
            # Preferable option, immediate and efficient
            TaskRescheduleFlag.objects.create(name=name)

    @staticmethod
    def get_lock_name(func_name, args):
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


def validate_not_atomic():
    if connection.in_atomic_block and settings.DEBUG:
        raise RuntimeError('Idempotent tasks should NEVER be called inside a transaction, use on_commit.')


def lazy_execute(f, local_cycles=20):
    @wraps(f)
    def new_func(*args, **kwargs):
        validate_not_atomic()
        name = TaskRescheduleFlag.get_lock_name(f.__name__, args)

        # NOTE: In a stricter form of this design, we would check the flag
        # and exit before doing any work if the flag was not set
        # this current form (the weaker form) still allows periodic runs to do work

        def resubmit(reason):
            try:
                f.apply_async(args=args, kwargs=kwargs)
                logger.info('Resubmitted lazy task {}. {}'.format(name, reason))
            except Exception:
                logger.exception('Resubmission check of task {} failed, unexecuted work could remain.'.format(name))

        ret = None
        flag_exists = True  # may not exist, arbitrary initial value
        with advisory_lock(name, wait=False) as compute_lock:  # non-blocking, acquire lock
            if not compute_lock:
                try:
                    TaskRescheduleFlag.gently_set_flag(name)
                    logger.debug('Another process is doing {}, rescheduled for after it completes.'.format(name))
                    with advisory_lock(name, wait=False) as compute_lock2:
                        gave_up_lock = bool(compute_lock2)
                    if gave_up_lock:
                        resubmit('Continuity gap due to race condition.')
                except IntegrityError:
                    logger.debug('Another process is doing {}, reschedule is already planned, no-op.'.format(name))
                return

            logger.debug('Obtained {} lock, now I am obligated to perform the work.'.format(name))
            for cycle in range(local_cycles):
                # Claim flag, flag may or may not exist, this is fire-and-forget
                TaskRescheduleFlag.objects.filter(name=name).delete()

                ret = f(*args, **kwargs)

                flag_exists = TaskRescheduleFlag.objects.filter(name=name).exists()
                if not flag_exists:
                    logger.info('Work for {} lock cleared in {} cycles.'.format(name, cycle + 1))
                    break
                else:
                    logger.debug('Lazy task {} got rescheduled running cycle {}, repeating.'.format(name, cycle + 1))
            else:
                # After so-long, restart in a new context for OOM concerns, etc.
                resubmit('Reached max of {} local cycles.'.format(local_cycles + 1))

        return ret

    return new_func


# def lazy_apply_async(orig_fn):
#     def new_apply_async(args=None, kwargs=None, queue=None, uuid=None, **kw):
#         validate_not_atomic()
#         name = TaskRescheduleFlag.get_lock_name(orig_fn.__name__, args)
# 
#         # NOTE: setting the flag needs to happen before advisory_lock check
#         # to avoid race condition - running task checks flag before releasing lock
#         try:
#             TaskRescheduleFlag.gently_set_flag(name)
#         except IntegrityError:
#             pass  # Reschedule flag already existed
# 
#         with advisory_lock(name, wait=False) as compute_lock:
#             lock_available = bool(compute_lock)
# 
#         if lock_available:
#             logger.debug('Submitting lazy task with lock {}.'.format(name))
#             return orig_fn.apply_async(args=args, kwargs=kwargs, queue=queue, uuid=uuid, **kw)
#         else:
#             logger.debug('Task {} already queued, not submitting.'.format(name))
#             return
# 
#     return new_apply_async


# def lazy_delay(orig_fn):
#     def new_delay(*args, **kwargs):
#         return orig_fn.lazy_apply_async(args, kwargs)
#     return new_delay


def lazy_task(*args, **kwargs):
    """
    task wrapper to schedule time-sensitive idempotent tasks efficiently
    see section in docs/tasks.md
    """

    def new_decorator(fn):
        if not isfunction(fn):
            raise RuntimeError('lazy tasks only supported for functions, given {}'.format(fn))

        # This is passing-through the original task decorator that all tasks use
        task_fn = task(*args, **kwargs)(fn)

        # This converts the function into a lazier version of itself which
        # uses a non-blocking lock combined with a reschedule flag to make
        # sure it runs after the last request received
        lazy_fn = lazy_execute(task_fn)

        # copy tasks bound to the PublisherMixin from dispatch code
        LAZY_TASK_MODULES[fn.__name__] = task_fn.name.rsplit('.', 1)[0]
        setattr(lazy_fn, 'name', task_fn.name)
        setattr(lazy_fn, 'apply_async', task_fn.apply_async)
        setattr(lazy_fn, 'delay', task_fn.delay)
        # # lazy_apply_async checks for active locks to determine
        # # if there is a need to schedule the task or, bail as no-op
        # setattr(lazy_fn, 'lazy_apply_async', lazy_apply_async(lazy_fn))
        # setattr(lazy_fn, 'lazy_delay', lazy_delay(lazy_fn))

        return lazy_fn

    return new_decorator


# @lazy_task()
# def resubmit_lazy_tasks():
#     """Fallback in case that processes running tasks were terminated unexpectedly
#     This should never be used, unless switching to different submission archecture
#     """
#     for flag in TaskRescheduleFlag.objects.all():
#         with advisory_lock(flag.name, wait=False) as compute_lock:
#             lock_available = bool(compute_lock)
#         if not lock_available:
#             continue  # already being ran, good
#         fn, args = flag.get_task_and_args()
#         fn.apply_async(args=args)


# Python
import logging

# AWX
from awx.main.scheduler import TaskManager
from awx.main.dispatch.publish import task
from awx.main.models.tasks import lazy_task

logger = logging.getLogger('awx.main.scheduler')


@lazy_task()
def run_task_manager():
    logger.debug("Running Tower task manager.")
    tm = TaskManager()
    tm.schedule()
    if tm.needs_reschedule:
        run_task_manager.lazy_delay()  # just don't think too hard about this

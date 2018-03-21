import pytest
import mock
from contextlib import contextmanager

from awx.main.models.tasks import (
    lazy_task,
    TaskRescheduleFlag,
    resubmit_lazy_tasks
)



def f():
    pass


lazy_f = lazy_task()(f)


@contextmanager
def mock_pg_lock(*args, **kwargs):
    yield False  # otherwise gives True with sqlite3 DB


@pytest.mark.django_db
class TestLazyTaskDecorator:
    def test_delay_sets_flag(self):
        assert not TaskRescheduleFlag.objects.filter(name='f').exists()
        with mock.patch.object(lazy_f, 'apply_async') as mock_apply:
            lazy_f.lazy_delay()
            assert TaskRescheduleFlag.objects.filter(name='f').exists()
            mock_apply.assert_called_once()

    def test_do_not_apply_async(self):
        TaskRescheduleFlag.objects.create(name='f:[42]')
        with mock.patch.object(lazy_f, 'apply_async') as mock_apply:
            with mock.patch('awx.main.models.tasks.advisory_lock', new=mock_pg_lock):
                lazy_f.lazy_delay(42)
                mock_apply.assert_not_called()

    def test_call_removes_flag(self):
        TaskRescheduleFlag.objects.create(name='mock_f:[42]')
        local_calls = []

        def mock_f(param):
            local_calls.append(param)

        this_f = lazy_task()(mock_f)
        this_f(42)
        assert local_calls == [42]
        assert not TaskRescheduleFlag.objects.filter(name='mock_f:[42]').exists()

    def test_sets_flag_does_not_run_without_lock(self):
        local_calls = []

        def mock_f(param):
            local_calls.append(param)

        this_f = lazy_task()(mock_f)
        with mock.patch('awx.main.models.tasks.advisory_lock', new=mock_pg_lock):
            this_f(42)
        assert local_calls == []
        assert TaskRescheduleFlag.objects.filter(name='mock_f:[42]').exists()


@pytest.mark.django_db
class TestTaskRescheduleFlag:
    @pytest.mark.parametrize('args', [
        [42],
        [1, 'foo'],
        ['bar'],
        [True, False]
    ])
    def test_args_store_and_retreive(self, args):
        lock_name = TaskRescheduleFlag.get_lock_name(f.__name__, args)
        flag = TaskRescheduleFlag(lock_name)
        recalc_f, recalc_args = flag.get_task_and_args()
        assert recalc_f == f
        assert recalc_args == args 

    def test_resubmit_method(self):
        TaskRescheduleFlag.objects.create(name='f:[42]')
        with mock.patch.object(f, 'apply_async') as mock_apply:
            resubmit_lazy_tasks()
            mock_apply.assert_called_once_with(args=[42])

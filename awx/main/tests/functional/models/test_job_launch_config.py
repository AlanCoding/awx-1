import pytest
import mock

# AWX
from awx.main.models import JobTemplate, JobLaunchConfig


@pytest.fixture
def full_jt(inventory, project, machine_credential):
    jt = JobTemplate.objects.create(
        name='my-jt',
        inventory=inventory,
        project=project,
        playbook='helloworld.yml'
    )
    jt.credentials.add(machine_credential)
    return jt


@pytest.mark.django_db
class TestConfigCreation:
    '''
    Checks cases for the auto-creation of a job configuration with the
    creation of a unified job
    '''
    def test_null_configuration(self, full_jt):
        job = full_jt.create_unified_job()
        with pytest.raises(JobLaunchConfig.DoesNotExist):
            job.launch_config

    def test_char_field_change(self, full_jt):
        job = full_jt.create_unified_job(limit='foobar')
        config = job.launch_config
        assert config.limit == 'foobar'
        assert config.char_prompts == {'limit': 'foobar'}

    def test_added_credential(self, full_jt, credential):
        job = full_jt.create_unified_job(credentials=[credential])
        config = job.launch_config
        assert set(config.credentials.all()) == set([credential])

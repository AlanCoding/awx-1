
# Python
import pytest
from unittest import mock
from contextlib import contextmanager

from awx.main.models import Credential
from awx.main.tests.factories import create_survey_spec, create_workflow_job_template

from django.core.cache import cache


def pytest_addoption(parser):
    parser.addoption(
        "--genschema", action="store_true", default=False, help="execute schema validator"
    )


def pytest_configure(config):
    import sys
    sys._called_from_test = True


def pytest_unconfigure(config):
    import sys
    del sys._called_from_test


@pytest.fixture
def survey_spec_factory():
    return create_survey_spec


@pytest.fixture
def job_template_with_survey_passwords_factory(job_template_factory):
    def rf(persisted):
        "Returns job with linked JT survey with password survey questions"
        objects = job_template_factory('jt', organization='org1', survey=[
            {'variable': 'submitter_email', 'type': 'text', 'default': 'foobar@redhat.com'},
            {'variable': 'secret_key', 'default': '6kQngg3h8lgiSTvIEb21', 'type': 'password'},
            {'variable': 'SSN', 'type': 'password'}], persisted=persisted)
        return objects.job_template
    return rf


@pytest.fixture
def workflow_job_template_factory():
    return create_workflow_job_template


@pytest.fixture
def job_template_with_survey_passwords_unit(job_template_with_survey_passwords_factory):
    return job_template_with_survey_passwords_factory(persisted=False)


@pytest.fixture
def mock_cache():
    class MockCache(object):
        cache = {}

        def get(self, key, default=None):
            return self.cache.get(key, default)

        def set(self, key, value, timeout=60):
            self.cache[key] = value

        def delete(self, key):
            del self.cache[key]

    return MockCache()


def pytest_runtest_teardown(item, nextitem):
    # clear Django cache at the end of every test ran
    # NOTE: this should not be memcache, see test_cache in test_env.py
    # this is a local test cache, so we want every test to start with empty cache
    cache.clear()


@pytest.fixture(scope='session', autouse=True)
def mock_external_credential_input_sources():
    # Credential objects query their related input sources on initialization.
    # We mock that behavior out of credentials by default unless we need to
    # test it explicitly.
    with mock.patch.object(Credential, 'dynamic_input_fields', new=[]) as _fixture:
        yield _fixture

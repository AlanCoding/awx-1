from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pytest

from awx.main.models import WorkflowJobTemplate


@pytest.mark.django_db
def test_create_workflow_job_template(run_module, admin_user, organization, survey_spec):
    result = run_module('tower_workflow_job_template', {
        'name': 'foo-workflow',
        'organization': organization.name,
        'extra_vars': {'foo': 'bar', 'another-foo': {'barz': 'bar2'}},
        'survey': survey_spec,
        'survey_enabled': True,
        'state': 'present'
    }, admin_user)
    assert not result.get('failed', False), result

    wfjt = WorkflowJobTemplate.objects.get(name='foo-workflow')
    assert wfjt.extra_vars == '{"foo": "bar", "another-foo": {"barz": "bar2"}}'

    result.pop('invocation', None)
    assert result == {
        "name": "foo-workflow",
        "id": wfjt.id,
        "changed": True
    }

    assert wfjt.organization_id == organization.id

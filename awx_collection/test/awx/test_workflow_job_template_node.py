from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pytest

from awx.main.models import WorkflowJobTemplateNode, WorkflowJobTemplate, JobTemplate


@pytest.mark.django_db
def test_create_workflow_job_template_node(run_module, admin_user, organization, project, inventory):
    wfjt = WorkflowJobTemplate.objects.create(organization=organization, name='foo-workflow')
    WorkflowJobTemplate.objects.create(organization=None, name='foo-workflow')  # to test org scoping

    jt = JobTemplate.objects.create(
        project=project,
        inventory=inventory,
        playbook='helloworld.yml',
        name='foo-jt'
    )

    result = run_module('tower_workflow_job_template_node', {
        'identifier': '42',
        'workflow_job_template': 'foo-workflow',
        'organization': organization.name,
        'unified_job_template': 'foo-jt',
        'state': 'present'
    }, admin_user)
    assert not result.get('failed', False), result.get('msg', result)

    node = WorkflowJobTemplateNode.objects.get(identifier='42')

    result.pop('invocation', None)
    assert result == {
        "name": "42",  # NOTE: should this be identifier instead?
        "id": node.id,
        "changed": True
    }

    assert node.workflow_job_template_id == wfjt.id
    assert node.unified_job_template_id == jt.id

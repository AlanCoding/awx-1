from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pytest

from awx.main.models import WorkflowJobTemplateNode, WorkflowJobTemplate, JobTemplate


@pytest.fixture
def job_template(project, inventory):
    return JobTemplate.objects.create(
        project=project,
        inventory=inventory,
        playbook='helloworld.yml',
        name='foo-jt',
        ask_variables_on_launch=True,
        ask_credential_on_launch=True
    )


@pytest.fixture
def wfjt(organization):
    WorkflowJobTemplate.objects.create(organization=None, name='foo-workflow')  # to test org scoping
    return WorkflowJobTemplate.objects.create(organization=organization, name='foo-workflow')


@pytest.mark.django_db
def test_create_workflow_job_template_node(run_module, admin_user, wfjt, job_template):
    result = run_module('tower_workflow_job_template_node', {
        'identifier': '42',
        'workflow_job_template': 'foo-workflow',
        'organization': wfjt.organization.name,
        'unified_job_template': 'foo-jt',
        'state': 'present'
    }, admin_user)
    assert not result.get('failed', False), result.get('msg', result)

    node = WorkflowJobTemplateNode.objects.get(identifier='42')

    result.pop('invocation', None)
    assert result == {
        "name": "42",  # FIXME: should this be identifier instead
        "id": node.id,
        "changed": True
    }

    assert node.workflow_job_template_id == wfjt.id
    assert node.unified_job_template_id == job_template.id


@pytest.mark.django_db
def test_create_with_edges(run_module, admin_user, wfjt, job_template):
    next_nodes = [
        WorkflowJobTemplateNode.objects.create(
            identifier='foo{0}'.format(i),
            workflow_job_template=wfjt,
            unified_job_template=job_template
        ) for i in range(3)
    ]
    # Create to temporarily woraround other issue https://github.com/ansible/awx/issues/5177
    WorkflowJobTemplateNode.objects.create(
        identifier='42',
        workflow_job_template=wfjt,
        unified_job_template=job_template
    )

    result = run_module('tower_workflow_job_template_node', {
        'identifier': '42',
        'workflow_job_template': 'foo-workflow',
        'organization': wfjt.organization.name,
        'unified_job_template': 'foo-jt',
        'success_nodes': ['foo0'],
        'always_nodes': ['foo1'],
        'failure_nodes': ['foo2'],
        'state': 'present'
    }, admin_user)
    assert not result.get('failed', False), result.get('msg', result)
    assert result.get('changed', False)

    node = WorkflowJobTemplateNode.objects.get(identifier='42')

    assert list(node.success_nodes.all()) == [next_nodes[0]]
    assert list(node.always_nodes.all()) == [next_nodes[1]]
    assert list(node.failure_nodes.all()) == [next_nodes[2]]

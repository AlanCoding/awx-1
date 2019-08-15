import pytest

from awx.api.versioning import reverse

from awx.main.models.workflow import WorkflowJobTemplate


@pytest.mark.django_db
def test_aliased_forward_reverse_field_searches(instance, options, get, admin):
    url = reverse('api:unified_job_template_list')
    response = options(url, None, admin)
    assert 'job_template__search' in response.data['related_search_fields']
    get(reverse("api:unified_job_template_list") + "?job_template__search=anything", user=admin, expect=200)


@pytest.mark.django_db
def test_set_all_the_prompts(post, organization, inventory, org_admin):
    r = post(
        url = reverse('api:workflow_job_template_list'),
        data = dict(
            name='My new workflow',
            organization=organization.id,
            inventory=inventory.id,
            limit='foooo',
            ask_limit_on_launch=True,
            scm_branch='bar',
            ask_scm_branch_on_launch=True
        ),
        user = org_admin,
        expect = 201
    )
    wfjt = WorkflowJobTemplate.objects.get(id=r.data['id'])
    assert wfjt.char_prompts == {
        'limit': 'foooo', 'scm_branch': 'bar'
    }
    assert wfjt.ask_scm_branch_on_launch is True
    assert wfjt.ask_limit_on_launch is True

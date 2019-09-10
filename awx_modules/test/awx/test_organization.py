import pytest

from awx.main.models import Organization


@pytest.mark.django_db
def test_create_organization(run_module, admin_user):

    module_args = {'name': 'foo', 'description': 'barfoo', 'state': 'present'}

    result = run_module(module_args, admin_user)

    assert result == {
        "organization": "foo",
        "state": "present",
        "id": 1,
        "changed": True,
        "invocation": {
            "module_args": module_args
        }
    }

    org = Organization.objects.get(name='foo')
    assert org.description == 'barfoo'

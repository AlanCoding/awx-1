import os
from unittest import mock
import importlib

import pytest

from awx.main.models import Organization, Inventory

from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import PluginLoader


inventory_path = os.path.join(os.path.dirname(__file__), 'data', 'example.tower.yml')
plugin_path = os.path.join(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    ),
    'plugins', 'inventory'
)


# @pytest.fixture
# def module():
#     inventory_loader = PluginLoader(
#         'InventoryModule',
#         'ansible.plugins.inventory',
#         plugin_path,
#         'inventory_plugins'
#     )
#     plugin = inventory_loader.get('awx.awx.tower')
#     return plugin


@pytest.mark.django_db
def test_load_inventory(mock_request, admin_user):
    print('plugin path')
    print(plugin_path)
    InventoryModule = importlib.import_module('plugins.inventory.tower').InventoryModule
    module = InventoryModule()
    module._load_name = 'awx.awx.tower'  # have to set for whatever reason
    org = Organization.objects.create(name='Default')
    Inventory.objects.create(organization=org, name='foo_inventory')
    with mock_request(admin_user):
        module.parse(mock.MagicMock(), DataLoader(), inventory_path, cache=False)

# @pytest.mark.django_db
# def test_load_inventory(run_module, admin_user, project, inventory):
#
#     module_args = {
#         'name': 'foo', 'playbook': 'helloworld.yml',
#         'project': project.name, 'inventory': inventory.name,
#         'job_type': 'run',
#         'state': 'present'
#     }
#
#     result = run_module('tower_job_template', module_args, admin_user)
#
#     jt = JobTemplate.objects.get(name='foo')
#
#     assert result == {
#         "job_template": "foo",
#         "state": "present",
#         "id": jt.id,
#         "changed": True,
#         "invocation": {
#             "module_args": module_args
#         }
#     }
#
#     assert jt.project_id == project.id
#     assert jt.inventory_id == inventory.id


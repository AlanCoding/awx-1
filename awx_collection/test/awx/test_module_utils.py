from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import sys

from unittest import mock

import pytest


def test_duplicate_config(collection_import):
    # imports done here because of PATH issues unique to this test suite
    TowerModule = collection_import('plugins.module_utils.tower_api').TowerModule
    data = {
        'name': 'zigzoom',
        'zig': 'zoom',
        'tower_username': 'bob',
        'tower_config_file': 'my_config'
    }
    with mock.patch('ansible.module_utils.basic.AnsibleModule.warn') as mock_warn:
        with mock.patch.object(TowerModule, 'load_config') as mock_load:
            argument_spec = dict(
                name=dict(required=True),
                zig=dict(type='str'),
            )
            TowerModule(argument_spec=argument_spec, direct_params=data)
        mock_load.mock_calls[-1] == mock.call('my_config')
    mock_warn.assert_called_once_with(
        'The parameter(s) tower_username were provided at the same time as '
        'tower_config_file. Precedence may be unstable, '
        'we suggest either using config file or params.'
    )

@pytest.mark.parametrize('host, endpoint, expect', [
    ('ansible.com', 'users', 'https://ansible.com/api/v2/users/'),
    ('ansible.com', '/api/v2/users', 'https://ansible.com/api/v2/users/'),
    ('ansible.com', 'users/50/', 'https://ansible.com/api/v2/users/50/'),
])
def test_get_absolute_url(collection_import, host, endpoint, expect):
    TowerModule = collection_import('plugins.module_utils.tower_api').TowerModule
    module = TowerModule(argument_spec={}, direct_params={'tower_host': host})
    assert module.get_absolute_url(endpoint) == expect

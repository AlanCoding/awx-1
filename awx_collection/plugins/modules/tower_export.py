#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2017, John Westcott IV <john.westcott.iv@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: tower_export
author: "Jeff Bradberry (@jbradberry)"
version_added: "3.7"
short_description: export resources from Ansible Tower.
description:
    - Export assets from Ansible Tower.
options:
    all:
      description:
        - Export all assets
      type: bool
      default: 'False'
    organizations:
      description:
        - organization name to export
      default: ''
      type: str
    user:
      description:
        - user name to export
      default: ''
      type: str
    team:
      description:
        - team name to export
      default: ''
      type: str
    credential_type:
      description:
        - credential type name to export
      default: ''
      type: str
    credential:
      description:
        - credential name to export
      default: ''
      type: str
    notification_template:
      description:
        - notification template name to export
      default: ''
      type: str
    inventory_script:
      description:
        - inventory script name to export
      default: ''
      type: str
    inventory:
      description:
        - inventory name to export
      default: ''
      type: str
    project:
      description:
        - project name to export
      default: ''
      type: str
    job_template:
      description:
        - job template name to export
      default: ''
      type: str
    workflow:
      description:
        - workflow name to export
      default: ''
      type: str

requirements:
  - "awxkit >= 9.3.0"

notes:
  - Specifying a name of "all" for any asset type will export all items of that asset type.

extends_documentation_fragment: awx.awx.auth
'''

EXAMPLES = '''
- name: Export all tower assets
  tower_export:
    all: True

- name: Export all inventories
  tower_export:
    inventory: ''

- name: Export a job template named "My Template" and all Credentials
  tower_export:
    job_template: "My Template"
    credential: ''
'''

from os import environ

from ..module_utils.ansible_tower import TowerModule

try:
    import awxkit
except ImportError:
    HAS_AWXKIT = False
else:
    HAS_AWXKIT = True
    from awxkit import config
    from awxkit.api import get_registered_page
    from awxkit.api.client import Connection
    from awxkit.cli.resource import Export
    from awxkit.awx.utils import as_user


def main():
    argument_spec = dict(
        all=dict(type='bool', default=False),
        credentials=dict(default=''),
        credential_types=dict(default=''),
        inventories=dict(default=''),
        inventory_scripts=dict(default=''),
        job_templates=dict(default=''),
        notification_templates=dict(default=''),
        organizations=dict(default=''),
        projects=dict(default=''),
        teams=dict(default=''),
        users=dict(default=''),
        workflows=dict(default=''),
    )

    module = TowerModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_AWXKIT:
        module.fail_json(msg='awxkit required for this module')

    EXPORT_ORDER = [
        'users',
        'organizations',
        'teams',
        'credentials'
    ]

    export_all = module.params.get('all')
    assets_to_export = []
    for asset_type in EXPORT_ORDER:
        if export_all or module.params.get(asset_type) == '':
            assets_to_export.append((asset_type, ''))
        else:
            assets_to_export.append((asset_type, module.params.get(asset_type)))

    result = dict(
        assets=None,
        changed=False,
        message='',
    )

    config_params = [
        ('base_url', 'tower_host', 'TOWER_HOST'),
        ('token', 'tower_oauthtoken', 'TOWER_TOKEN'),
        ('username', 'tower_username', 'TOWER_USERNAME'),
        ('password', 'tower_password', 'TOWER_PASSWORD'),
        ('insecure', 'validate_certs', 'TOWER_VERIFY_SSL')
    ]
    for key, param, env_var in config_params:
        val = None
        if module.params.get(param):
            val = module.params.get(param)
        elif environ.get(env_var):
            val = environ.get(env_var)

        if key == 'insecure':
            val = bool(not val)

        if val is not None:
            setattr(config, key, val)

    connection = Connection(config.base_url, verify=not config.insecure)
    with as_user(connection, config.username, config.password):
        v2 = get_registered_page('/api/v2/')(connection).get()
        exporter = Export()
        exporter.v2 = v2
        assets = exporter.perform_export(assets_to_export)
        result['assets'] = assets

    module.exit_json(**result)


if __name__ == '__main__':
    main()

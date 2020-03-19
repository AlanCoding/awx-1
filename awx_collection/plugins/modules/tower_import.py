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
module: tower_import
author: "Jeff Bradberry (@jbradberry)"
version_added: "3.7"
short_description: import resources into Ansible Tower.
description:
    - Import assets into Ansible Tower. See
      U(https://www.ansible.com/tower) for an overview.
options:
    assets:
      description:
        - The assets to import.
        - This can be the output of tower_export or loaded from a file
      required: True
      type: dict

notes:
  - One of assets or files needs to be passed in

requirements:
  - "awxkit >= 9.3.0"

extends_documentation_fragment: awx.awx.auth
'''

EXAMPLES = '''
- name: Import all tower assets
  tower_import:
    assets: "{{ export_output.assets }}"
'''

import os
import sys

from ..module_utils.ansible_tower import TowerModule

try:
    import awxkit
except ImportError:
    HAS_AWXKIT = False
else:
    HAS_AWXKIT = True
    from awxkit.cli.resource import Import


def main():
    argument_spec = dict(
        assets=dict(required=False)
    )

    module = TowerModule(argument_spec=argument_spec, supports_check_mode=False)

    assets = module.params.get('assets')

    if not HAS_AWXKIT:
        module.fail_json(msg='towerkit required for this module')

    Import().perform_import(assets)

    if not TOWER_CLI_HAS_EXPORT:
        module.fail_json(msg='ansible-tower-cli version does not support export')

    result = dict(
        changed=False,
        msg='',
        output='',
    )

    module.exit_json(**result)


if __name__ == '__main__':
    main()

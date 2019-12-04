import logging
import json
import re

from awxkit.api.pages import (
    Credential,
    Organization,
    Project,
    UnifiedJob,
    UnifiedJobTemplate
)
from awxkit.utils import (
    filter_by_class,
    random_title,
    update_payload,
    suppress,
    not_provided,
    PseudoNamespace,
    poll_until,
    random_utf8
)
from awxkit.api.mixins import DSAdapter, HasCreate, HasInstanceGroups, HasNotifications, HasVariables, HasCopy
from awxkit.api.resources import resources
import awxkit.exceptions as exc
from . import base
from . import page


log = logging.getLogger(__name__)


class Inventory(HasCopy, HasCreate, HasInstanceGroups, HasVariables, base.Base):

    dependencies = [Organization]

    def print_ini(self):
        """Print an ini version of the inventory"""
        output = list()
        inv_dict = self.related.script.get(hostvars=1).json

        for group in inv_dict.keys():
            if group == '_meta':
                continue

            # output host groups
            output.append('[%s]' % group)
            for host in inv_dict[group].get('hosts', []):
                # FIXME ... include hostvars
                output.append(host)
            output.append('')  # newline

            # output child groups
            if inv_dict[group].get('children', []):
                output.append('[%s:children]' % group)
                for child in inv_dict[group].get('children', []):
                    output.append(child)
                output.append('')  # newline

            # output group vars
            if inv_dict[group].get('vars', {}).items():
                output.append('[%s:vars]' % group)
                for k, v in inv_dict[group].get('vars', {}).items():
                    output.append('%s=%s' % (k, v))
                output.append('')  # newline

        print('\n'.join(output))

    def payload(self, organization, **kwargs):
        payload = PseudoNamespace(
            name=kwargs.get('name') or 'Inventory - {}'.format(
                random_title()),
            description=kwargs.get('description') or random_title(10),
            organization=organization.id)

        optional_fields = (
            'host_filter',
            'insights_credential',
            'kind',
            'variables')

        update_payload(payload, optional_fields, kwargs)

        if 'variables' in payload and isinstance(payload.variables, dict):
            payload.variables = json.dumps(payload.variables)
        if 'insights_credential' in payload and isinstance(
                payload.insights_credential, Credential):
            payload.insights_credential = payload.insights_credential.id

        return payload

    def create_payload(
            self,
            name='',
            description='',
            organization=Organization,
            **kwargs):
        self.create_and_update_dependencies(organization)
        payload = self.payload(
            name=name,
            description=description,
            organization=self.ds.organization,
            **kwargs)
        payload.ds = DSAdapter(self.__class__.__name__, self._dependency_store)
        return payload

    def create(
            self,
            name='',
            description='',
            organization=Organization,
            **kwargs):
        payload = self.create_payload(
            name=name,
            description=description,
            organization=organization,
            **kwargs)
        return self.update_identity(
            Inventories(
                self.connection).post(payload))

    def add_host(self, host=None):
        if host is None:
            return self.related.hosts.create(inventory=self)

        if isinstance(host, base.Base):
            host = host.json
        with suppress(exc.NoContent):
            self.related.hosts.post(host)
        return host

    def wait_until_deleted(self):
        def _wait():
            try:
                self.get()
            except exc.NotFound:
                return True
        poll_until(_wait, interval=1, timeout=60)

    def _assert_content_same(self, inventory2,
                             allow_superset=False, assert_everything=False,
                             use_instance_id=False):
        def get_host_id_mapping(inventory_obj):
            """Hosts have an identifier separate from their name
            the identifier is not known in the script data sent to Ansible
            so we have to get that from the API here, and use it to
            build a mapping from host names to ID
            """
            page = 1
            host_list = []
            while page:
                this_page = inventory_obj.get_related('hosts', page=page, page_size=200)
                host_list += this_page.results
                page_string = this_page.next
                if page_string:
                    page = int(page_string.split('=')[1].split('&')[0])
                else:
                    page = None

            name_to_id = {}
            for h in host_list:
                if use_instance_id and h.instance_id:
                    this_host_id = h.instance_id
                else:
                    # if instance_id wasn't filled in, the name is the id
                    this_host_id = h.name
                name_to_id[h.name] = this_host_id
            return name_to_id

        # Ask it to return towervars and unenabled hosts too
        json_data1 = self.get_related('script', hostvars=1, all=1).json
        json_data2 = inventory2.get_related('script', hostvars=1, all=1).json

        name_to_id1 = get_host_id_mapping(self)
        name_to_id2 = get_host_id_mapping(inventory2)
        host_id_set1 = set(name_to_id1.values())
        host_id_set2 = set(name_to_id2.values())

        errors = ''

        # Check 1: host list
        shared_hosts = host_id_set1 & host_id_set2  # shared host ids
        try:
            if allow_superset:
                assert host_id_set2 == shared_hosts
            else:
                assert host_id_set2 == host_id_set1
        except AssertionError as e:
            errors = '\n'.join([
                errors,
                '',
                'Check 1: hosts',
                ' Hosts did not line up between this and that',
                str(e)
            ])

        # Check 2: group list
        exclude_gn = set(['_meta', 'all', 'ungrouped'])
        groups1 = set(
            group_name for group_name in json_data1.keys() if group_name not in exclude_gn
        )
        groups2 = set(
            group_name for group_name in json_data2.keys() if group_name not in exclude_gn
        )
        shared_groups = groups1 & groups2
        try:
            if allow_superset:
                assert groups2 == shared_groups
            else:
                assert groups2 == groups1
        except AssertionError as e:
            errors = '\n'.join([
                errors,
                '',
                'Check 2: group list',
                ' Groups did not line up between this and that',
                str(e)
            ])
        # Check 2b: group-host conflicts
        name_conflicts = (set(name_to_id1.keys()) | set(name_to_id2.keys())) & shared_groups
        if name_conflicts:
            errors += '\n'.join([
                '',
                'Check 2b: group name and host name conflict for {}'.format(name_conflicts)
            ])

        # Check 3: memberships

        def get_host_memberships(script_data, name_to_id):
            memberships = set()
            for group_name, group_data in script_data.items():
                if group_name in exclude_gn:
                    # this would be redundant with the host list comparision
                    continue
                if 'hosts' not in group_data:
                    continue
                if group_name not in shared_groups:
                    continue
                for host in group_data['hosts']:
                    host_id = name_to_id[host]
                    if host_id not in shared_hosts:
                        continue
                    memberships.add((group_name, host_id))
            return memberships

        memberships1 = get_host_memberships(json_data1, name_to_id1)
        memberships2 = get_host_memberships(json_data2, name_to_id2)
        shared_memberships = memberships1 & memberships2

        try:
            if allow_superset:
                assert memberships2 == shared_memberships
            else:
                assert memberships2 == memberships1
        except AssertionError as e:
            errors = '\n'.join([
                errors,
                '',
                'Check 3: memberships',
                ' Host memberships did not line up between this and that',
                str(e)
            ])

        def get_group_memberships(script_data):
            memberships = set()
            for group_name, group_data in script_data.items():
                if group_name in exclude_gn:
                    continue
                if 'children' not in group_data:
                    continue
                if group_name not in shared_groups:
                    continue
                for child_name in group_data['children']:
                    if child_name not in shared_groups:
                        continue
                    memberships.add((group_name, child_name))
            return memberships

        group_memberships1 = get_group_memberships(json_data1)
        group_memberships2 = get_group_memberships(json_data2)
        shared_group_memberships = group_memberships1 & group_memberships2

        try:
            if allow_superset:
                assert group_memberships2 == shared_group_memberships
            else:
                assert group_memberships2 == group_memberships1
        except AssertionError as e:
            errors = '\n'.join([
                errors,
                '',
                'Check 3b: memberships',
                ' Group memberships did not line up between this and that',
                str(e)
            ])

        # Check 4: groupvars
        for group_name in shared_groups:
            if group_name in name_conflicts:
                # this is a misconfigured state, not coherent in comparision
                continue
            try:
                gvars1 = json_data1[group_name].get('vars', {})
                gvars2 = json_data2[group_name].get('vars', {})
                if allow_superset:
                    gvars1_red = gvars1.copy()
                    for key in gvars1:
                        if key not in gvars2:
                            gvars1_red.pop(key)
                    assert gvars2 == gvars1_red
                else:
                    assert gvars2 == gvars1
            except AssertionError as e:
                errors = '\n'.join([
                    errors,
                    '',
                    'Check 4: groupvars',
                    u'Group vars of {} were not equal between this and that'.format(group_name),
                    str(e)
                ])
                if not assert_everything:
                    break
        if not shared_groups and groups2:
            errors = '\n'.join([errors, '', 'Check 4: groupvars skipped because groups not aligned'])
        # Check 5: hostvars

        def get_host_name_from_id(name_to_id, host_id):
            for host_name, host_id_p in name_to_id.items():
                if host_id == host_id_p:
                    return host_name
            else:
                raise AssertionError('Could not find shared host id {} out of:\n{}'.format(
                    host_id, json.dumps(name_to_id, indent=2)
                ))

        for host_id in shared_hosts:
            if host_id in shared_groups:
                # this is a misconfigured state, not coherent in comparision
                continue
            try:
                host_name_1 = get_host_name_from_id(name_to_id1, host_id)
                host_name_2 = get_host_name_from_id(name_to_id2, host_id)
                d1 = json_data1['_meta']['hostvars'][host_name_1]
                d2 = json_data2['_meta']['hostvars'][host_name_2]
                for key in set(d1.keys()) & set(d2.keys()):
                    if isinstance(d1[key], dict):
                        # we traverse into subdicts to simply the error message
                        sub_dict1 = d1.pop(key)
                        sub_dict2 = d2.pop(key)
                        # put in these placeholders to indicate larger omitted content
                        d1[key] = '<dict-removed>'
                        d2[key] = '<dict-removed>'
                        try:
                            # this does not really work
                            # if allow_superset:
                            #     sub_dict1_red = sub_dict1.copy()
                            #     for key2 in sub_dict1:
                            #         if key2 not in sub_dict2:
                            #             sub_dict1_red.pop(key2)
                            #     assert sub_dict2 == sub_dict1_red
                            assert sub_dict2 == sub_dict1
                        except AssertionError as e:
                            errors = '\n'.join([
                                errors,
                                '',
                                u'  Subdict at {} of hostvars for host {} not equal between this and that'.format(
                                    key, (host_name_1, host_name_2)
                                ),
                                str(e)
                            ])
                if allow_superset:
                    d1_red = d1.copy()
                    for key in d1:
                        if key not in d2:
                            d1_red.pop(key)
                    assert d2 == d1_red
                else:
                    assert d2 == d1
            except AssertionError as e:
                errors = '\n'.join([
                    errors,
                    '',
                    'Check 5: hostvars',
                    ' Hostvars for same host {} did not line up between this and that'.format(
                        (host_name_1, host_name_2)),
                    str(e)
                ])
                if not assert_everything:
                    break
        if not shared_hosts and name_to_id2:
            errors = '\n'.join([errors, '', 'Check 5: hostvars skipped because hosts not aligned'])
        if errors:
            raise AssertionError(errors)

    def assert_is_superset(self, inventory2, **kwargs):
        """Given a second inventory, inventory2, this asserts that this
        inventory contains all the hosts, groups, and relationships
        that the second inventory has
        """
        self._assert_content_same(inventory2, allow_superset=True, **kwargs)

    def assert_content_same(self, inventory2, **kwargs):
        """Given a second inventory, inventory2, this method asserts that
        the content of the second inventory is eactly equal to the content
        of this inventory, considering host, groups, relationships, and vars
        """
        self._assert_content_same(inventory2, allow_superset=False, **kwargs)

    def update_inventory_sources(self, wait=False):
        response = self.related.update_inventory_sources.post()
        source_ids = [entry['inventory_source']
                      for entry in response if entry['status'] == 'started']

        inv_updates = []
        for source_id in source_ids:
            inv_source = self.related.inventory_sources.get(
                id=source_id).results.pop()
            inv_updates.append(inv_source.related.current_job.get())

        if wait:
            for update in inv_updates:
                update.wait_until_completed()
        return inv_updates


page.register_page([resources.inventory,
                    (resources.inventories, 'post'),
                    (resources.inventory_copy, 'post')], Inventory)


class Inventories(page.PageList, Inventory):

    pass


page.register_page([resources.inventories,
                    resources.related_inventories], Inventories)


class InventoryScript(HasCopy, HasCreate, base.Base):

    dependencies = [Organization]

    def payload(self, organization, **kwargs):
        payload = PseudoNamespace(
            name=kwargs.get('name') or 'Inventory Script - {}'.format(
                random_title()),
            description=kwargs.get('description') or random_title(10),
            organization=organization.id,
            script=kwargs.get('script') or self._generate_script())
        return payload

    def create_payload(
            self,
            name='',
            description='',
            organization=Organization,
            script='',
            **kwargs):
        self.create_and_update_dependencies(organization)
        payload = self.payload(
            name=name,
            description=description,
            organization=self.ds.organization,
            script=script,
            **kwargs)
        payload.ds = DSAdapter(self.__class__.__name__, self._dependency_store)
        return payload

    def create(
            self,
            name='',
            description='',
            organization=Organization,
            script='',
            **kwargs):
        payload = self.create_payload(
            name=name,
            description=description,
            organization=organization,
            script=script,
            **kwargs)
        return self.update_identity(
            InventoryScripts(
                self.connection).post(payload))

    def _generate_script(self):
        script = '\n'.join([
            '#!/usr/bin/env python',
            '# -*- coding: utf-8 -*-',
            'import json',
            'inventory = dict()',
            'inventory["{0}"] = dict()',
            'inventory["{0}"]["hosts"] = list()',
            'inventory["{0}"]["hosts"].append("{1}")',
            'inventory["{0}"]["hosts"].append("{2}")',
            'inventory["{0}"]["hosts"].append("{3}")',
            'inventory["{0}"]["hosts"].append("{4}")',
            'inventory["{0}"]["hosts"].append("{5}")',
            'inventory["{0}"]["vars"] = dict(ansible_host="127.0.0.1", ansible_connection="local")',
            'print(json.dumps(inventory))'
        ])
        group_name = re.sub(r"[\']", "", "group-{}".format(random_utf8()))
        host_names = [
            re.sub(
                r"[\':]",
                "",
                "host_{}".format(
                    random_utf8())) for _ in range(5)]

        return script.format(group_name, *host_names)


page.register_page([resources.inventory_script,
                    (resources.inventory_scripts, 'post'),
                    (resources.inventory_script_copy, 'post')], InventoryScript)


class InventoryScripts(page.PageList, InventoryScript):

    pass


page.register_page([resources.inventory_scripts], InventoryScripts)


class Group(HasCreate, HasVariables, base.Base):

    dependencies = [Inventory]
    optional_dependencies = [Credential, InventoryScript]

    @property
    def is_root_group(self):
        """Returns whether the current group is a top-level root group in the inventory"""
        return self.related.inventory.get().related.root_groups.get(id=self.id).count == 1

    def get_parents(self):
        """Inspects the API and returns all groups that include the current group as a child."""
        return Groups(self.connection).get(children=self.id).results

    def payload(self, inventory, credential=None, **kwargs):
        payload = PseudoNamespace(
            name=kwargs.get('name') or 'Group{}'.format(
                random_title(
                    non_ascii=False)),
            description=kwargs.get('description') or random_title(10),
            inventory=inventory.id)

        if credential:
            payload.credential = credential.id

        update_payload(payload, ('variables',), kwargs)

        if 'variables' in payload and isinstance(payload.variables, dict):
            payload.variables = json.dumps(payload.variables)

        return payload

    def create_payload(
            self,
            name='',
            description='',
            inventory=Inventory,
            credential=None,
            source_script=None,
            **kwargs):
        credential, source_script = filter_by_class(
            (credential, Credential), (source_script, InventoryScript))
        self.create_and_update_dependencies(
            inventory, credential, source_script)
        credential = self.ds.credential if credential else None
        payload = self.payload(
            inventory=self.ds.inventory,
            credential=credential,
            name=name,
            description=description,
            **kwargs)
        payload.ds = DSAdapter(self.__class__.__name__, self._dependency_store)
        return payload

    def create(self, name='', description='', inventory=Inventory, **kwargs):
        payload = self.create_payload(
            name=name,
            description=description,
            inventory=inventory,
            **kwargs)

        parent = kwargs.get('parent', None)  # parent must be a Group instance
        resource = parent.related.children if parent else Groups(
            self.connection)
        return self.update_identity(resource.post(payload))

    def add_host(self, host=None):
        if host is None:
            host = self.related.hosts.create(inventory=self.ds.inventory)
            with suppress(exc.NoContent):
                host.related.groups.post(dict(id=self.id))
            return host

        if isinstance(host, base.Base):
            host = host.json
        with suppress(exc.NoContent):
            self.related.hosts.post(host)
        return host

    def add_group(self, group):
        if isinstance(group, page.Page):
            group = group.json
        with suppress(exc.NoContent):
            self.related.children.post(group)

    def remove_group(self, group):
        if isinstance(group, page.Page):
            group = group.json
        with suppress(exc.NoContent):
            self.related.children.post(dict(id=group.id, disassociate=True))


page.register_page([resources.group,
                    (resources.groups, 'post')], Group)


class Groups(page.PageList, Group):

    pass


page.register_page([resources.groups,
                    resources.host_groups,
                    resources.inventory_related_groups,
                    resources.inventory_related_root_groups,
                    resources.group_children,
                    resources.group_potential_children], Groups)


class Host(HasCreate, HasVariables, base.Base):

    dependencies = [Inventory]

    def payload(self, inventory, **kwargs):
        payload = PseudoNamespace(
            name=kwargs.get('name') or 'Host{}'.format(
                random_title(
                    non_ascii=False)),
            description=kwargs.get('description') or random_title(10),
            inventory=inventory.id)

        optional_fields = ('enabled', 'instance_id')

        update_payload(payload, optional_fields, kwargs)

        variables = kwargs.get('variables', not_provided)

        if variables is None:
            variables = dict(
                ansible_host='127.0.0.1',
                ansible_connection='local')

        if variables != not_provided:
            if isinstance(variables, dict):
                variables = json.dumps(variables)
            payload.variables = variables

        return payload

    def create_payload(
            self,
            name='',
            description='',
            variables=None,
            inventory=Inventory,
            **kwargs):
        self.create_and_update_dependencies(
            *filter_by_class((inventory, Inventory)))
        payload = self.payload(
            inventory=self.ds.inventory,
            name=name,
            description=description,
            variables=variables,
            **kwargs)
        payload.ds = DSAdapter(self.__class__.__name__, self._dependency_store)
        return payload

    def create(
            self,
            name='',
            description='',
            variables=None,
            inventory=Inventory,
            **kwargs):
        payload = self.create_payload(
            name=name,
            description=description,
            variables=variables,
            inventory=inventory,
            **kwargs)
        return self.update_identity(Hosts(self.connection).post(payload))


page.register_page([resources.host,
                    (resources.hosts, 'post')], Host)


class Hosts(page.PageList, Host):

    pass


page.register_page([resources.hosts,
                    resources.group_related_hosts,
                    resources.inventory_related_hosts,
                    resources.inventory_sources_related_hosts], Hosts)


class FactVersion(base.Base):

    pass


page.register_page(resources.host_related_fact_version, FactVersion)


class FactVersions(page.PageList, FactVersion):

    @property
    def count(self):
        return len(self.results)


page.register_page(resources.host_related_fact_versions, FactVersions)


class FactView(base.Base):

    pass


page.register_page(resources.fact_view, FactView)


class InventorySource(HasCreate, HasNotifications, UnifiedJobTemplate):

    optional_schedule_fields = tuple()
    dependencies = [Inventory]
    optional_dependencies = [Credential, InventoryScript, Project]

    def payload(
            self,
            inventory,
            source='custom',
            credential=None,
            source_script=None,
            project=None,
            **kwargs):
        payload = PseudoNamespace(
            name=kwargs.get('name') or 'InventorySource - {}'.format(
                random_title()),
            description=kwargs.get('description') or random_title(10),
            inventory=inventory.id,
            source=source)

        if credential:
            payload.credential = credential.id
        if source_script:
            payload.source_script = source_script.id
        if project:
            payload.source_project = project.id

        optional_fields = (
            'group_by',
            'instance_filters',
            'source_path',
            'source_regions',
            'source_vars',
            'timeout',
            'overwrite',
            'overwrite_vars',
            'update_cache_timeout',
            'update_on_launch',
            'update_on_project_update',
            'verbosity')

        update_payload(payload, optional_fields, kwargs)

        return payload

    def create_payload(
            self,
            name='',
            description='',
            source='custom',
            inventory=Inventory,
            credential=None,
            source_script=InventoryScript,
            project=None,
            **kwargs):
        if source != 'custom' and source_script == InventoryScript:
            source_script = None
        if source == 'scm':
            kwargs.setdefault('overwrite_vars', True)
            if project is None:
                project = Project

        inventory, credential, source_script, project = filter_by_class((inventory, Inventory),
                                                                        (credential, Credential),
                                                                        (source_script, InventoryScript),
                                                                        (project, Project))
        self.create_and_update_dependencies(
            inventory, credential, source_script, project)

        if credential:
            credential = self.ds.credential
        if source_script:
            source_script = self.ds.inventory_script
        if project:
            project = self.ds.project

        payload = self.payload(
            inventory=self.ds.inventory,
            source=source,
            credential=credential,
            source_script=source_script,
            project=project,
            name=name,
            description=description,
            **kwargs)
        payload.ds = DSAdapter(self.__class__.__name__, self._dependency_store)
        return payload

    def create(
            self,
            name='',
            description='',
            source='custom',
            inventory=Inventory,
            credential=None,
            source_script=InventoryScript,
            project=None,
            **kwargs):
        payload = self.create_payload(
            name=name,
            description=description,
            source=source,
            inventory=inventory,
            credential=credential,
            source_script=source_script,
            project=project,
            **kwargs)
        return self.update_identity(
            InventorySources(
                self.connection).post(payload))

    def update(self):
        """Update the inventory_source using related->update endpoint"""
        # get related->launch
        update_pg = self.get_related('update')

        # assert can_update == True
        assert update_pg.can_update, \
            "The specified inventory_source (id:%s) is not able to update (can_update:%s)" % \
            (self.id, update_pg.can_update)

        # start the inventory_update
        result = update_pg.post()

        # assert JSON response
        assert 'inventory_update' in result.json, \
            "Unexpected JSON response when starting an inventory_update.\n%s" % \
            json.dumps(result.json, indent=2)

        # locate and return the inventory_update
        jobs_pg = self.related.inventory_updates.get(
            id=result.json['inventory_update'])
        assert jobs_pg.count == 1, \
            "An inventory_update started (id:%s) but job not found in response at %s/inventory_updates/" % \
            (result.json['inventory_update'], self.url)
        return jobs_pg.results[0]

    @property
    def is_successful(self):
        """An inventory_source is considered successful when source != "" and super().is_successful ."""
        return self.source != "" and super(
            InventorySource, self).is_successful

    def add_credential(self, credential):
        with suppress(exc.NoContent):
            self.related.credentials.post(
                dict(id=credential.id, associate=True))

    def remove_credential(self, credential):
        with suppress(exc.NoContent):
            self.related.credentials.post(
                dict(id=credential.id, disassociate=True))


page.register_page([resources.inventory_source,
                    (resources.inventory_sources, 'post')], InventorySource)


class InventorySources(page.PageList, InventorySource):

    pass


page.register_page([resources.inventory_sources,
                    resources.related_inventory_sources],
                   InventorySources)


class InventorySourceGroups(page.PageList, Group):

    pass


page.register_page(
    resources.inventory_sources_related_groups,
    InventorySourceGroups)


class InventorySourceUpdate(base.Base):

    pass


page.register_page([resources.inventory_sources_related_update,
                    resources.inventory_related_update_inventory_sources],
                   InventorySourceUpdate)


class InventoryUpdate(UnifiedJob):

    pass


page.register_page(resources.inventory_update, InventoryUpdate)


class InventoryUpdates(page.PageList, InventoryUpdate):

    pass


page.register_page([resources.inventory_updates,
                    resources.inventory_source_updates,
                    resources.project_update_scm_inventory_updates],
                   InventoryUpdates)


class InventoryUpdateCancel(base.Base):

    pass


page.register_page(resources.inventory_update_cancel, InventoryUpdateCancel)

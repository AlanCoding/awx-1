# Copyright (c) 2017 Ansible, Inc.
# All Rights Reserved.

from django.conf.urls import url

from awx.api.views import (
    RoleList,
    RoleDetail,
    RoleUsersList,
    RoleTeamsList,
    RoleParentsList,
    RoleAncestorsList,
    RoleChildrenList,
)


urls = [
    url(r'^$', RoleList.as_view(), name='role_list'),
    url(r'^(?P<pk>[0-9]+)/$', RoleDetail.as_view(), name='role_detail'),
    url(r'^(?P<pk>[0-9]+)/users/$', RoleUsersList.as_view(), name='role_users_list'),
    url(r'^(?P<pk>[0-9]+)/teams/$', RoleTeamsList.as_view(), name='role_teams_list'),
    url(r'^(?P<pk>[0-9]+)/parents/$', RoleParentsList.as_view(), name='role_parents_list'),
    url(r'^(?P<pk>[0-9]+)/ancestors/$', RoleAncestorsList.as_view(), name='role_ancestors_list'),
    url(r'^(?P<pk>[0-9]+)/children/$', RoleChildrenList.as_view(), name='role_children_list'),
]

__all__ = ['urls']

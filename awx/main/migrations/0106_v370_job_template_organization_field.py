# Generated by Django 2.2.4 on 2019-08-07 19:56

import awx.main.utils.polymorphic
import awx.main.fields
from django.db import migrations, models
import django.db.models.deletion

from awx.main.migrations._rbac import (
    rebuild_role_parentage, rebuild_role_hierarchy,
    migrate_ujt_organization, migrate_ujt_organization_backward,
    restore_inventory_admins, restore_inventory_admins_backward
)


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0105_v370_remove_jobevent_parent_and_hosts'),
    ]

    operations = [
        # backwards parents and ancestors caching
        migrations.RunPython(migrations.RunPython.noop, rebuild_role_parentage),
        # add new organization field for JT and all other unified jobs
        migrations.AddField(
            model_name='unifiedjob',
            name='tmp_organization',
            field=models.ForeignKey(blank=True, help_text='The organization used to determine access to this unified job.', null=True, on_delete=awx.main.utils.polymorphic.SET_NULL, related_name='unifiedjobs', to='main.Organization'),
        ),
        migrations.AddField(
            model_name='unifiedjobtemplate',
            name='tmp_organization',
            field=models.ForeignKey(blank=True, help_text='The organization used to determine access to this template.', null=True, on_delete=awx.main.utils.polymorphic.SET_NULL, related_name='unifiedjobtemplates', to='main.Organization'),
        ),
        # while new and old fields exist, copy the organization fields
        migrations.RunPython(migrate_ujt_organization, migrate_ujt_organization_backward),
        # with data saved, remove old fields
        migrations.RemoveField(
            model_name='project',
            name='organization',
        ),
        migrations.RemoveField(
            model_name='workflowjobtemplate',
            name='organization',
        ),
        # now, without safely rename the new field without conflicts from old field
        migrations.RenameField(
            model_name='unifiedjobtemplate',
            old_name='tmp_organization',
            new_name='organization',
        ),
        migrations.RenameField(
            model_name='unifiedjob',
            old_name='tmp_organization',
            new_name='organization',
        ),
        # parentage of job template roles has genuinely changed at this point
        migrations.AlterField(
            model_name='jobtemplate',
            name='admin_role',
            field=awx.main.fields.ImplicitRoleField(editable=False, null='True', on_delete=django.db.models.deletion.CASCADE, parent_role=['organization.job_template_admin_role'], related_name='+', to='main.Role'),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='execute_role',
            field=awx.main.fields.ImplicitRoleField(editable=False, null='True', on_delete=django.db.models.deletion.CASCADE, parent_role=['admin_role', 'organization.execute_role'], related_name='+', to='main.Role'),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='read_role',
            field=awx.main.fields.ImplicitRoleField(editable=False, null='True', on_delete=django.db.models.deletion.CASCADE, parent_role=['organization.auditor_role', 'inventory.organization.auditor_role', 'execute_role', 'admin_role'], related_name='+', to='main.Role'),
        ),
        # Re-compute the role parents and ancestors caching
        # this may be a no-op because field post_save hooks from migrate_jt_organization
        migrations.RunPython(rebuild_role_parentage, migrations.RunPython.noop),
        migrations.RunPython(rebuild_role_hierarchy, migrations.RunPython.noop),
        # for all permissions that will be removed, make them explicit
        migrations.RunPython(restore_inventory_admins, restore_inventory_admins_backward),
        migrations.RunPython(rebuild_role_hierarchy, migrations.RunPython.noop),
    ]

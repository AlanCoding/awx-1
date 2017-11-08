# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import awx.main.fields

from awx.main.migrations import _migration_utils as migration_utils
from awx.main.migrations._workflow_credential import migrate_workflow_cred


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_v320_drop_v1_credential_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowjobtemplate',
            name='ask_variables_on_launch',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='JobLaunchConfig',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('extra_data', awx.main.fields.JSONField(default={}, blank=True)),
                ('survey_passwords', awx.main.fields.JSONField(default={}, editable=False, blank=True)),
                ('char_prompts', awx.main.fields.JSONField(default={}, blank=True)),
                ('credentials', models.ManyToManyField(related_name='joblaunchconfigs', to='main.Credential')),
                ('inventory', models.ForeignKey(related_name='joblaunchconfigs', on_delete=django.db.models.deletion.SET_NULL, default=None, blank=True, to='main.Inventory', null=True)),
                ('job', models.ForeignKey(related_name='launch_configs', editable=False, to='main.Job')),
            ],
        ),
        migrations.AddField(
            model_name='schedule',
            name='char_prompts',
            field=awx.main.fields.JSONField(default={}, blank=True),
        ),
        migrations.AddField(
            model_name='schedule',
            name='credentials',
            field=models.ManyToManyField(related_name='schedules', to='main.Credential'),
        ),
        migrations.AddField(
            model_name='schedule',
            name='inventory',
            field=models.ForeignKey(related_name='schedules', on_delete=django.db.models.deletion.SET_NULL, default=None, blank=True, to='main.Inventory', null=True),
        ),
        migrations.AddField(
            model_name='schedule',
            name='survey_passwords',
            field=awx.main.fields.JSONField(default={}, editable=False, blank=True),
        ),
        migrations.AddField(
            model_name='workflowjobnode',
            name='credentials',
            field=models.ManyToManyField(related_name='workflowjobnodes', to='main.Credential'),
        ),
        migrations.AddField(
            model_name='workflowjobnode',
            name='extra_data',
            field=awx.main.fields.JSONField(default={}, blank=True),
        ),
        migrations.AddField(
            model_name='workflowjobnode',
            name='survey_passwords',
            field=awx.main.fields.JSONField(default={}, editable=False, blank=True),
        ),
        migrations.AddField(
            model_name='workflowjobtemplatenode',
            name='credentials',
            field=models.ManyToManyField(related_name='workflowjobtemplatenodes', to='main.Credential'),
        ),
        migrations.AddField(
            model_name='workflowjobtemplatenode',
            name='extra_data',
            field=awx.main.fields.JSONField(default={}, blank=True),
        ),
        migrations.AddField(
            model_name='workflowjobtemplatenode',
            name='survey_passwords',
            field=awx.main.fields.JSONField(default={}, editable=False, blank=True),
        ),
        # Run data migration before removing the old credential field
        migrations.RunPython(migration_utils.set_current_apps_for_migrations),
        migrations.RunPython(migrate_workflow_cred),
        migrations.RemoveField(
            model_name='workflowjobnode',
            name='credential',
        ),
        migrations.RemoveField(
            model_name='workflowjobtemplatenode',
            name='credential',
        ),
    ]

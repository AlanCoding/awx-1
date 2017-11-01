# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import awx.main.fields

from awx.main.migrations import _migration_utils as migration_utils
from awx.main.migrations._workflow_credential import migrate_workflow_cred


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_v330_multi_credential'),
    ]

    operations = [
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
        migrations.RunPython(migration_utils.set_current_apps_for_migrations, lambda x, y: None),
        migrations.RunPython(migrate_workflow_cred, lambda x, y: None),
        migrations.RemoveField(
            model_name='workflowjobnode',
            name='credential',
        ),
        migrations.RemoveField(
            model_name='workflowjobtemplatenode',
            name='credential',
        ),
        migrations.CreateModel(
            name='JobLaunchConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('extra_data', awx.main.fields.JSONField(blank=True, default={})),
                ('survey_passwords', awx.main.fields.JSONField(blank=True, default={}, editable=False)),
                ('char_prompts', awx.main.fields.JSONField(blank=True, default={})),
                ('credentials', models.ManyToManyField(related_name='joblaunchconfigs', to='main.Credential')),
                ('inventory', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='joblaunchconfigs', to='main.Inventory')),
                ('job', models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='launch_configs', to='main.UnifiedJob')),
            ],
        ),
        migrations.AddField(
            model_name='workflowjobtemplate',
            name='ask_variables_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_credential_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_diff_mode_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_inventory_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_job_type_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_limit_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_skip_tags_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_tags_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_variables_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AlterField(
            model_name='jobtemplate',
            name='ask_verbosity_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
    ]

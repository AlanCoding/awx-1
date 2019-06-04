# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-06-14 15:08
from __future__ import unicode_literals

import awx.main.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0081_v360_notify_on_start'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='scm_branch',
            field=models.CharField(blank=True, default='', help_text='Branch to use in job run. Project default used if blank. Only allowed if project allow_override field is set to true.', max_length=1024),
        ),
        migrations.AddField(
            model_name='jobtemplate',
            name='ask_scm_branch_on_launch',
            field=awx.main.fields.AskForField(default=False),
        ),
        migrations.AddField(
            model_name='jobtemplate',
            name='scm_branch',
            field=models.CharField(blank=True, default='', help_text='Branch to use in job run. Project default used if blank. Only allowed if project allow_override field is set to true.', max_length=1024),
        ),
        migrations.AddField(
            model_name='project',
            name='allow_override',
            field=models.BooleanField(default=False, help_text='Allow changing the SCM branch or revision in a job template that uses this project.'),
        ),
        migrations.AlterField(
            model_name='project',
            name='scm_update_cache_timeout',
            field=models.PositiveIntegerField(blank=True, default=0, help_text='The number of seconds after the last project update ran that a new project update will be launched as a job dependency.'),
        ),
    ]

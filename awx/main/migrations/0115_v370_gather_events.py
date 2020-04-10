# Generated by Django 2.2.11 on 2020-04-09 13:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0114_v370_remove_deprecated_manual_inventory_sources'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='gather_event_types',
            field=models.CharField(choices=[('all', 'All'), ('errors', 'Only events that contain errors'), ('output', 'Only events that contain stdout or stderr output'), ('none', 'Only Headers')], default='all', help_text='Filters certain events before they are written to the database. Events are still emitted to external loggers but their stdout will be hidden and the filtered events will not show up in the database. This field can be used to limit number of events recorded for extremely large jobs.', max_length=64),
        ),
        migrations.AddField(
            model_name='jobtemplate',
            name='gather_event_types',
            field=models.CharField(choices=[('all', 'All'), ('errors', 'Only events that contain errors'), ('output', 'Only events that contain stdout or stderr output'), ('none', 'Only Headers')], default='all', help_text='Filters certain events before they are written to the database. Events are still emitted to external loggers but their stdout will be hidden and the filtered events will not show up in the database. This field can be used to limit number of events recorded for extremely large jobs.', max_length=64),
        ),
    ]

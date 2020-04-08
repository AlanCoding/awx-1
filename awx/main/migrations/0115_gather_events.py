# Generated by Django 2.2.11 on 2020-04-07 21:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0114_v370_remove_deprecated_manual_inventory_sources'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='gather_event_types',
            field=models.CharField(choices=[('all', 'All'), ('errors', 'Only events that contain errors'), ('none', 'Only Headers')], default='all', max_length=64),
        ),
        migrations.AddField(
            model_name='jobtemplate',
            name='gather_event_types',
            field=models.CharField(choices=[('all', 'All'), ('errors', 'Only events that contain errors'), ('none', 'Only Headers')], default='all', max_length=64),
        ),
    ]

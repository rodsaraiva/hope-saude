# Generated by Django 5.2 on 2025-05-14 15:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0010_alter_agendamento_paciente'),
    ]

    operations = [
        migrations.DeleteModel(
            name='BloqueioTempo',
        ),
    ]

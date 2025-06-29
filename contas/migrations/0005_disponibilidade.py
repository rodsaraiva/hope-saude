# Generated by Django 5.2 on 2025-05-05 00:22

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0004_agendamento'),
    ]

    operations = [
        migrations.CreateModel(
            name='Disponibilidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dia_semana', models.IntegerField(choices=[(0, 'Segunda-feira'), (1, 'Terça-feira'), (2, 'Quarta-feira'), (3, 'Quinta-feira'), (4, 'Sexta-feira'), (5, 'Sábado'), (6, 'Domingo')])),
                ('hora_inicio', models.TimeField()),
                ('hora_fim', models.TimeField()),
                ('profissional', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disponibilidades', to='contas.perfilprofissional')),
            ],
            options={
                'verbose_name': 'Disponibilidade Semanal',
                'verbose_name_plural': 'Disponibilidades Semanais',
                'ordering': ['profissional', 'dia_semana', 'hora_inicio'],
                'unique_together': {('profissional', 'dia_semana', 'hora_inicio', 'hora_fim')},
            },
        ),
    ]

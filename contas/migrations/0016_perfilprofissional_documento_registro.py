# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0015_avaliacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilprofissional',
            name='documento_registro',
            field=models.FileField(
                blank=True,
                help_text='Foto ou scan do documento de registro (CRP/CRM)',
                null=True,
                upload_to='documentos_registro/',
                verbose_name='Documento de Registro'
            ),
        ),
    ] 
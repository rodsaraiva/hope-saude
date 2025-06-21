# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0019_alter_perfilprofissional_documento_registro_function'),
    ]

    operations = [
        migrations.AlterField(
            model_name='perfilprofissional',
            name='documento_registro',
            field=models.FileField(
                blank=True,
                help_text='Foto ou scan do documento de registro (CRP/CRM)',
                null=True,
                upload_to='documentos/',
                verbose_name='Documento de Registro'
            ),
        ),
    ] 
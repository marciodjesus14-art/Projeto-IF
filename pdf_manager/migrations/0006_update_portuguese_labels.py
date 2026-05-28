# Generated manually to align visible labels with accented Portuguese text.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pdf_manager', '0005_alter_processinglog_operation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='title',
            field=models.CharField(max_length=180, verbose_name='título'),
        ),
        migrations.AlterField(
            model_name='processinglog',
            name='operation',
            field=models.CharField(
                choices=[
                    ('pdf_to_jpg', 'PDF para JPG'),
                    ('office_to_pdf', 'Documento para PDF'),
                    ('images_to_pdf', 'Imagem para PDF'),
                    ('merge', 'Juntar PDFs'),
                    ('upload', 'Upload de PDF'),
                    ('rotate', 'Girar páginas'),
                    ('extract', 'Extrair páginas'),
                    ('delete_pages', 'Excluir páginas'),
                    ('reorder', 'Reordenar páginas'),
                    ('protect', 'Proteger arquivo'),
                    ('text', 'Inserir texto'),
                    ('replace_text', 'Substituir texto'),
                    ('image', 'Inserir imagem'),
                    ('signature', 'Assinatura visual'),
                    ('watermark', "Marca d'água"),
                    ('shape', 'Forma gráfica'),
                    ('qr_code', 'QR Code'),
                    ('cancel_changes', 'Cancelar alterações'),
                ],
                max_length=40,
                verbose_name='operação',
            ),
        ),
        migrations.AlterField(
            model_name='processinglog',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                verbose_name='usuário',
            ),
        ),
    ]

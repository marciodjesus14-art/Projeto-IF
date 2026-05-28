from django.db import models
from django.conf import settings


class Document(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='dono',
        on_delete=models.CASCADE,
        related_name='documents',
        blank=True,
        null=True,
    )
    title = models.CharField('título', max_length=180)
    file = models.FileField('arquivo PDF', upload_to='documents/originals/')
    processed_file = models.FileField(
        'arquivo processado',
        upload_to='documents/processed/',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'documento'
        verbose_name_plural = 'documentos'

    def __str__(self):
        return self.title

    @property
    def active_file(self):
        return self.processed_file or self.file


class ProcessingLog(models.Model):
    OPERATION_CHOICES = [
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
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='usuário',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    operation = models.CharField('operação', max_length=40, choices=OPERATION_CHOICES)
    source_name = models.CharField('arquivo de origem', max_length=255, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'processamento'
        verbose_name_plural = 'processamentos'

    def __str__(self):
        return f'{self.get_operation_display()} - {self.source_name}'

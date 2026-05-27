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
    title = models.CharField('titulo', max_length=180)
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

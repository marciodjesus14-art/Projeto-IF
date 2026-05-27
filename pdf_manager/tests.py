import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from reportlab.pdfgen import canvas

from .models import Document
from .services import rotate_pages


MEDIA_ROOT = tempfile.mkdtemp()


def sample_pdf_bytes(text='Teste'):
    buffer = BytesIO()
    packet = canvas.Canvas(buffer)
    packet.drawString(72, 720, text)
    packet.showPage()
    packet.save()
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PdfManagerTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_dashboard_loads(self):
        response = Client().get(reverse('pdf_manager:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gerenciador de Documento PDF')
        self.assertContains(response, 'Criar conta')
        self.assertNotContains(response, 'Documentos recentes')

    def test_staff_dashboard_redirects_to_admin_panel(self):
        user = User.objects.create_user(
            username='admin@ifbaiano.edu.br',
            password='SenhaForte123!',
            is_staff=True,
        )
        client = Client()
        client.force_login(user)

        response = client.get(reverse('pdf_manager:dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('pdf_manager:master_dashboard'))

    def test_staff_user_cannot_access_user_tools(self):
        user = User.objects.create_user(
            username='admin@ifbaiano.edu.br',
            password='SenhaForte123!',
            is_staff=True,
        )
        client = Client()
        client.force_login(user)

        response = client.get(reverse('pdf_manager:upload'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('pdf_manager:login'), response['Location'])

    def test_user_login_rejects_admin_account(self):
        User.objects.create_user(
            username='admin@ifbaiano.edu.br',
            email='admin@ifbaiano.edu.br',
            password='SenhaForte123!',
            is_staff=True,
        )

        response = Client().post(
            reverse('pdf_manager:login'),
            {
                'username': 'admin@ifbaiano.edu.br',
                'password': 'SenhaForte123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Use o login do Painel Administrador')

    def test_upload_pdf_creates_document(self):
        user = User.objects.create_user(username='user@ifbaiano.edu.br', password='SenhaForte123!')
        client = Client()
        client.force_login(user)

        response = client.post(
            reverse('pdf_manager:upload'),
            {
                'file': ContentFile(sample_pdf_bytes(), name='ata-academica.pdf'),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Document.objects.filter(title='ata academica', owner=user).exists())

    def test_rotate_pages_creates_processed_file(self):
        document = Document.objects.create(title='Plano de aula')
        document.file.save('plano.pdf', ContentFile(sample_pdf_bytes()), save=True)

        rotate_pages(document, 90)

        document.refresh_from_db()
        self.assertTrue(document.processed_file.name.endswith('.pdf'))

    def test_document_preview_returns_png(self):
        user = User.objects.create_user(username='user@ifbaiano.edu.br', password='SenhaForte123!')
        document = Document.objects.create(title='Plano de aula', owner=user)
        document.file.save('plano.pdf', ContentFile(sample_pdf_bytes()), save=True)
        client = Client()
        client.force_login(user)

        response = client.get(f"{reverse('pdf_manager:preview', args=[document.pk])}?page=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG'))

    @override_settings(PDF_MANAGER_MAX_UPLOAD_MB=1)
    def test_upload_rejects_pdf_larger_than_limit(self):
        user = User.objects.create_user(username='user@ifbaiano.edu.br', password='SenhaForte123!')
        client = Client()
        client.force_login(user)
        oversized_pdf = SimpleUploadedFile(
            'grande.pdf',
            b'%PDF-1.4\n' + (b'0' * ((1024 * 1024) + 1)),
            content_type='application/pdf',
        )

        response = client.post(
            reverse('pdf_manager:upload'),
            {
                'file': oversized_pdf,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'O arquivo PDF deve ter no maximo 1 MB.')
        self.assertFalse(Document.objects.exists())

    def test_register_creates_user(self):
        response = Client().post(
            reverse('pdf_manager:register'),
            {
                'name': 'Maria Silva',
                'email': 'maria@ifbaiano.edu.br',
                'password': 'SenhaForte123!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='maria@ifbaiano.edu.br').exists())

    def test_office_to_pdf_page_loads(self):
        user = User.objects.create_user(username='user@ifbaiano.edu.br', password='SenhaForte123!')
        client = Client()
        client.force_login(user)

        response = client.get(reverse('pdf_manager:office_to_pdf', args=['documento']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Documento para PDF')
        self.assertContains(response, 'LibreOffice')

    def test_master_dashboard_requires_staff_user(self):
        user = User.objects.create_user(
            username='usuario@ifbaiano.edu.br',
            email='usuario@ifbaiano.edu.br',
            password='SenhaForte123!',
        )
        client = Client()
        client.force_login(user)

        response = client.get(reverse('pdf_manager:master_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('pdf_manager:master_login'), response['Location'])

    def test_master_login_allows_staff_user(self):
        User.objects.create_user(
            username='master@ifbaiano.edu.br',
            email='master@ifbaiano.edu.br',
            password='SenhaForte123!',
            is_staff=True,
        )

        response = Client().post(
            reverse('pdf_manager:master_login'),
            {
                'username': 'master@ifbaiano.edu.br',
                'password': 'SenhaForte123!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('pdf_manager:master_dashboard'))

    def test_django_admin_user_list_has_password_reset_link(self):
        admin_user = User.objects.create_superuser(
            username='admin@ifbaiano.edu.br',
            email='admin@ifbaiano.edu.br',
            password='SenhaForte123!',
        )
        User.objects.create_user(
            username='usuario@ifbaiano.edu.br',
            email='usuario@ifbaiano.edu.br',
            password='SenhaAntiga123!',
        )
        client = Client()
        client.force_login(admin_user)

        response = client.get(reverse('admin:auth_user_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alterar senha')
        self.assertContains(response, 'Papel')
        self.assertContains(response, 'Excluir conta')

    def test_django_admin_user_change_has_role_select(self):
        admin_user = User.objects.create_superuser(
            username='admin@ifbaiano.edu.br',
            email='admin@ifbaiano.edu.br',
            password='SenhaForte123!',
        )
        user = User.objects.create_user(
            username='usuario@ifbaiano.edu.br',
            email='usuario@ifbaiano.edu.br',
            password='SenhaAntiga123!',
        )
        client = Client()
        client.force_login(admin_user)

        response = client.get(reverse('admin:auth_user_change', args=[user.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="role"')
        self.assertContains(response, 'Usuario')
        self.assertContains(response, 'Admin')

    def test_master_can_delete_document(self):
        admin_user = User.objects.create_user(
            username='admin@ifbaiano.edu.br',
            password='SenhaForte123!',
            is_staff=True,
        )
        document = Document.objects.create(title='Documento sigiloso')
        document.file.save('sigiloso.pdf', ContentFile(sample_pdf_bytes()), save=True)
        client = Client()
        client.force_login(admin_user)

        response = client.post(reverse('pdf_manager:master_delete_document', args=[document.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Document.objects.filter(pk=document.pk).exists())


# Create your tests here.

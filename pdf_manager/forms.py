from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

from .models import Document


def max_pdf_upload_size_bytes():
    return int(getattr(settings, 'PDF_MANAGER_MAX_UPLOAD_MB', 25)) * 1024 * 1024


def validate_pdf_upload(file_obj):
    max_size = max_pdf_upload_size_bytes()
    max_mb = getattr(settings, 'PDF_MANAGER_MAX_UPLOAD_MB', 25)
    if file_obj.size > max_size:
        raise forms.ValidationError(f'O arquivo PDF deve ter no maximo {max_mb} MB.')
    if file_obj.content_type not in {'application/pdf', 'application/x-pdf'}:
        raise forms.ValidationError('Envie um arquivo no formato PDF.')
    return file_obj


def validate_file_size(file_obj):
    max_size = max_pdf_upload_size_bytes()
    max_mb = getattr(settings, 'PDF_MANAGER_MAX_UPLOAD_MB', 25)
    if file_obj.size > max_size:
        raise forms.ValidationError(f'O arquivo deve ter no maximo {max_mb} MB.')
    return file_obj


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


class DocumentUploadForm(forms.ModelForm):
    file = forms.FileField(
        label='Arquivo PDF',
        validators=[validate_pdf_upload],
        widget=forms.FileInput(attrs={'accept': 'application/pdf'}),
    )

    class Meta:
        model = Document
        fields = ['file']


class MergeForm(forms.Form):
    files = MultipleFileField(
        label='PDFs para juntar',
        widget=MultipleFileInput(attrs={'accept': 'application/pdf'}),
    )

    def clean_files(self):
        files = self.cleaned_data['files']
        for file_obj in files:
            validate_pdf_upload(file_obj)
        return files


class ImageToPdfForm(forms.Form):
    title = forms.CharField(label='Titulo do PDF', max_length=180)
    images = MultipleFileField(
        label='Imagens',
        widget=MultipleFileInput(attrs={'accept': 'image/*'}),
    )


OFFICE_CONVERSION_TYPES = {
    'documento': {
        'title': 'Documento para PDF',
        'extensions': {'.doc', '.docx', '.odt', '.rtf', '.txt'},
        'accept': '.doc,.docx,.odt,.rtf,.txt',
        'help': 'Formatos aceitos: DOC, DOCX, ODT, RTF e TXT.',
    },
    'apresentacao': {
        'title': 'Apresentacao para PDF',
        'extensions': {'.ppt', '.pptx', '.odp'},
        'accept': '.ppt,.pptx,.odp',
        'help': 'Formatos aceitos: PPT, PPTX e ODP.',
    },
    'planilha': {
        'title': 'Planilha para PDF',
        'extensions': {'.xls', '.xlsx', '.ods', '.csv'},
        'accept': '.xls,.xlsx,.ods,.csv',
        'help': 'Formatos aceitos: XLS, XLSX, ODS e CSV.',
    },
    'html': {
        'title': 'HTML para PDF',
        'extensions': {'.html', '.htm'},
        'accept': '.html,.htm',
        'help': 'Formatos aceitos: HTML e HTM.',
    },
}


class OfficeToPdfForm(forms.Form):
    file = forms.FileField(label='Arquivo', validators=[validate_file_size])

    def __init__(self, *args, conversion_type='documento', **kwargs):
        super().__init__(*args, **kwargs)
        self.conversion_type = conversion_type
        config = OFFICE_CONVERSION_TYPES[conversion_type]
        self.fields['file'].help_text = config['help']
        self.fields['file'].widget.attrs.update({'accept': config['accept']})

    def clean_file(self):
        file_obj = self.cleaned_data['file']
        suffix = Path(file_obj.name).suffix.lower()
        allowed_extensions = OFFICE_CONVERSION_TYPES[self.conversion_type]['extensions']
        if suffix not in allowed_extensions:
            allowed = ', '.join(sorted(allowed_extensions))
            raise forms.ValidationError(f'Formato nao suportado. Use: {allowed}.')
        return file_obj


class RegisterForm(forms.ModelForm):
    name = forms.CharField(label='Nome', max_length=150)
    email = forms.EmailField(label='E-mail institucional')
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['name', 'email', 'password']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este e-mail ja esta cadastrado.')
        return email

    def save(self, commit=True):
        email = self.cleaned_data['email']
        user = User(
            username=email,
            email=email,
            first_name=self.cleaned_data['name'],
        )
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(label='E-mail institucional')
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)

    error_messages = {
        'invalid_login': 'E-mail ou senha invalidos.',
        'inactive': 'Esta conta esta inativa.',
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff:
            raise forms.ValidationError(
                'Use o login do Painel Administrador para esta conta.',
                code='admin_on_user_login',
            )


class MasterLoginForm(AuthenticationForm):
    username = forms.CharField(label='Usuario ou e-mail')
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)

    error_messages = {
        'invalid_login': 'Usuario ou senha invalidos.',
        'inactive': 'Esta conta esta inativa.',
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                'Esta conta nao possui permissao de administrador.',
                code='not_staff',
            )

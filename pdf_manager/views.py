from pathlib import Path

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    DocumentUploadForm,
    ImageToPdfForm,
    MergeForm,
    MasterLoginForm,
    OFFICE_CONVERSION_TYPES,
    OfficeToPdfForm,
    RegisterForm,
    UserLoginForm,
)
from .models import Document, ProcessingLog
from .services import (
    OptionalDependencyError,
    add_image,
    add_qr_code,
    add_shape,
    add_text,
    add_watermark,
    delete_pages,
    extract_pages,
    images_to_pdf_bytes,
    merge_pdfs,
    office_to_pdf_bytes,
    parse_page_numbers,
    pdf_page_count,
    pdf_page_preview_bytes,
    pdf_to_jpg_zip_bytes,
    protect_pdf,
    replace_text_area,
    reorder_pages,
    rotate_pages,
)


def dashboard(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('pdf_manager:master_dashboard')
    return render(request, 'pdf_manager/dashboard.html')


def user_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        logout(request)
        messages.info(request, 'Sessão Admin encerrada. Entre com uma conta de usuário para acessar as ferramentas.')
    elif request.user.is_authenticated:
        return redirect('pdf_manager:dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, 'Login realizado com sucesso.')
            return redirect('pdf_manager:dashboard')
    else:
        form = UserLoginForm(request)
    return render(request, 'pdf_manager/login.html', {'form': form})


def user_logout(request):
    logout(request)
    messages.success(request, 'Você saiu da sua conta.')
    return redirect('pdf_manager:dashboard')


def user_document_queryset(user):
    return Document.objects.filter(owner=user)


def is_master_admin(user):
    return user.is_authenticated and user.is_staff


def is_regular_user(user):
    return user.is_authenticated and not user.is_staff


master_required = user_passes_test(is_master_admin, login_url='pdf_manager:master_login')
user_required = user_passes_test(is_regular_user, login_url='pdf_manager:login')


def master_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('pdf_manager:master_dashboard')

    if request.method == 'POST':
        form = MasterLoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, 'Login administrativo realizado com sucesso.')
            return redirect('pdf_manager:master_dashboard')
    else:
        form = MasterLoginForm(request)

    return render(request, 'pdf_manager/master_login.html', {'form': form})


def master_logout(request):
    logout(request)
    messages.success(request, 'Sessão Admin encerrada.')
    return redirect('pdf_manager:master_login')


@master_required
def master_dashboard(request):
    documents = Document.objects.select_related('owner').all()[:8]
    users = User.objects.order_by('-date_joined')[:8]
    logs = ProcessingLog.objects.select_related('user').all()[:12]
    context = {
        'documents_count': Document.objects.count(),
        'processed_count': Document.objects.exclude(processed_file='').count() + ProcessingLog.objects.count(),
        'users_count': User.objects.count(),
        'masters_count': User.objects.filter(is_staff=True).count(),
        'recent_documents': documents,
        'recent_users': users,
        'recent_logs': logs,
    }
    return render(request, 'pdf_manager/master_dashboard.html', context)


@master_required
def master_delete_document(request, pk):
    if request.method != 'POST':
        return redirect('pdf_manager:master_dashboard')

    document = get_object_or_404(Document, pk=pk)
    title = document.title
    document.delete()
    messages.success(request, f'Documento "{title}" excluído com sucesso.')
    return redirect('pdf_manager:master_dashboard')


@master_required
def master_bulk_delete_documents(request):
    if request.method != 'POST':
        return redirect('pdf_manager:master_dashboard')

    document_ids = request.POST.getlist('document_ids')
    if not document_ids:
        messages.error(request, 'Selecione pelo menos um documento para excluir.')
        return redirect('pdf_manager:master_dashboard')

    deleted_count, _ = Document.objects.filter(pk__in=document_ids).delete()
    messages.success(request, f'{deleted_count} documento(s) excluído(s) com sucesso.')
    return redirect('pdf_manager:master_dashboard')


def log_processing(user, operation, source_name):
    ProcessingLog.objects.create(
        user=user if user.is_authenticated else None,
        operation=operation,
        source_name=source_name,
    )


def register(request):
    if request.user.is_authenticated:
        return redirect('pdf_manager:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Cadastro realizado com sucesso.')
            return redirect('pdf_manager:dashboard')
    else:
        form = RegisterForm()
    return render(request, 'pdf_manager/register.html', {'form': form})


@user_required
def upload_document(request):
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.title = Path(document.file.name).stem.replace('_', ' ').replace('-', ' ').strip()
            document.owner = request.user
            document.save()
            log_processing(request.user, 'upload', document.file.name)
            messages.success(request, 'PDF enviado com sucesso.')
            return redirect('pdf_manager:detail', pk=document.pk)
    else:
        form = DocumentUploadForm()
    return render(
        request,
        'pdf_manager/upload.html',
        {'form': form, 'max_upload_mb': settings.PDF_MANAGER_MAX_UPLOAD_MB},
    )


@user_required
def document_detail(request, pk):
    document = get_object_or_404(user_document_queryset(request.user), pk=pk)
    try:
        page_count = pdf_page_count(document.active_file)
    except Exception:
        page_count = 1
    return render(
        request,
        'pdf_manager/detail.html',
        {
            'document': document,
            'page_count': page_count,
            'page_numbers': range(1, page_count + 1),
        },
    )


@user_required
def document_preview(request, pk):
    document = get_object_or_404(user_document_queryset(request.user), pk=pk)
    try:
        page_number = int(request.GET.get('page', '1'))
    except ValueError:
        page_number = 1
    try:
        content = pdf_page_preview_bytes(document.active_file, page_number=page_number)
    except (OptionalDependencyError, ValueError):
        return HttpResponse(status=404)
    return HttpResponse(content, content_type='image/png')


@user_required
def apply_operation(request, pk):
    document = get_object_or_404(user_document_queryset(request.user), pk=pk)
    if request.method != 'POST':
        return redirect('pdf_manager:detail', pk=document.pk)

    operation = request.POST.get('operation')
    try:
        if operation == 'rotate':
            rotate_pages(document, int(request.POST.get('degrees', '90')))
            log_processing(request.user, 'rotate', document.title)
        elif operation == 'extract':
            extract_pages(document, parse_page_numbers(request.POST.get('pages', '')))
            log_processing(request.user, 'extract', document.title)
        elif operation == 'delete':
            delete_pages(document, parse_page_numbers(request.POST.get('pages', '')))
            log_processing(request.user, 'delete_pages', document.title)
        elif operation == 'reorder':
            reorder_pages(document, parse_page_numbers(request.POST.get('pages', '')))
            log_processing(request.user, 'reorder', document.title)
        elif operation == 'protect':
            protect_pdf(document, request.POST.get('password', ''))
            log_processing(request.user, 'protect', document.title)
        elif operation == 'text':
            add_text(
                document,
                request.POST.get('text', ''),
                int(request.POST.get('page', '1')),
                float(request.POST.get('x', '72')),
                float(request.POST.get('y', '720')),
                int(request.POST.get('size', '12')),
            )
            log_processing(request.user, 'text', document.title)
        elif operation == 'replace_text':
            replace_text_area(
                document,
                request.POST.get('text', ''),
                int(request.POST.get('page', '1')),
                float(request.POST.get('x', '72')),
                float(request.POST.get('y', '700')),
                float(request.POST.get('width', '240')),
                float(request.POST.get('height', '28')),
                int(request.POST.get('size', '12')),
            )
            log_processing(request.user, 'replace_text', document.title)
        elif operation == 'watermark':
            add_watermark(
                document,
                request.POST.get('text', ''),
                int(request.POST.get('size', '44')),
            )
            log_processing(request.user, 'watermark', document.title)
        elif operation == 'shape':
            add_shape(
                document,
                request.POST.get('shape', 'rect'),
                int(request.POST.get('page', '1')),
                float(request.POST.get('x', '72')),
                float(request.POST.get('y', '640')),
                float(request.POST.get('width', '160')),
                float(request.POST.get('height', '80')),
                request.POST.get('color', '#116149'),
            )
            log_processing(request.user, 'shape', document.title)
        elif operation == 'qr_code':
            add_qr_code(
                document,
                request.POST.get('data', ''),
                int(request.POST.get('page', '1')),
                float(request.POST.get('x', '72')),
                float(request.POST.get('y', '640')),
                float(request.POST.get('size', '96')),
            )
            log_processing(request.user, 'qr_code', document.title)
        elif operation in {'image', 'signature'}:
            add_image(
                document,
                request.FILES['image'],
                int(request.POST.get('page', '1')),
                float(request.POST.get('x', '72')),
                float(request.POST.get('y', '640')),
                float(request.POST.get('width', '160')),
            )
            log_processing(request.user, operation, document.title)
        else:
            messages.error(request, 'Operação desconhecida.')
            return redirect('pdf_manager:detail', pk=document.pk)
    except (ValueError, OptionalDependencyError, KeyError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'PDF atualizado com sucesso.')
    return redirect('pdf_manager:detail', pk=document.pk)


@user_required
def cancel_document_changes(request, pk):
    document = get_object_or_404(user_document_queryset(request.user), pk=pk)
    if request.method != 'POST':
        return redirect('pdf_manager:detail', pk=document.pk)

    if document.processed_file:
        document.processed_file.delete(save=False)
        document.processed_file = None
        document.save(update_fields=['processed_file', 'updated_at'])
        log_processing(request.user, 'cancel_changes', document.title)
        messages.success(request, 'Alterações canceladas. O PDF original foi restaurado.')
    else:
        messages.info(request, 'Este documento ainda não possui alterações para cancelar.')
    return redirect('pdf_manager:detail', pk=document.pk)


@user_required
def merge_documents(request):
    if request.method == 'POST':
        form = MergeForm(request.POST, request.FILES)
        files = request.FILES.getlist('files')
        if form.is_valid() and files:
            content = merge_pdfs(files)
            first_name = Path(files[0].name).stem.replace('_', ' ').replace('-', ' ').strip()
            title = f'{first_name} - juntado' if first_name else 'PDF juntado'
            document = Document.objects.create(title=title, owner=request.user)
            document.file.save('pdf-juntado.pdf', ContentFile(content), save=True)
            log_processing(request.user, 'merge', title)
            messages.success(request, 'PDFs juntados com sucesso.')
            return redirect('pdf_manager:detail', pk=document.pk)
    else:
        form = MergeForm()
    return render(
        request,
        'pdf_manager/merge.html',
        {'form': form, 'max_upload_mb': settings.PDF_MANAGER_MAX_UPLOAD_MB},
    )


@user_required
def images_to_pdf(request):
    if request.method == 'POST':
        form = ImageToPdfForm(request.POST, request.FILES)
        images = request.FILES.getlist('images')
        if form.is_valid() and images:
            try:
                content = images_to_pdf_bytes(images)
            except OptionalDependencyError as exc:
                messages.error(request, str(exc))
            else:
                document = Document.objects.create(title=form.cleaned_data['title'], owner=request.user)
                document.file.save('imagens-convertidas.pdf', ContentFile(content), save=True)
                log_processing(request.user, 'images_to_pdf', form.cleaned_data['title'])
                messages.success(request, 'Imagens convertidas em PDF.')
                return redirect('pdf_manager:detail', pk=document.pk)
    else:
        form = ImageToPdfForm()
    return render(request, 'pdf_manager/images_to_pdf.html', {'form': form})


@user_required
def pdf_to_jpg(request):
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            try:
                content = pdf_to_jpg_zip_bytes(uploaded_file)
            except (OptionalDependencyError, ValueError) as exc:
                messages.error(request, str(exc))
            else:
                filename = f'{Path(uploaded_file.name).stem}-jpg.zip'
                response = HttpResponse(content, content_type='application/zip')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                log_processing(request.user, 'pdf_to_jpg', uploaded_file.name)
                return response
    else:
        form = DocumentUploadForm()
    return render(
        request,
        'pdf_manager/pdf_to_jpg.html',
        {'form': form, 'max_upload_mb': settings.PDF_MANAGER_MAX_UPLOAD_MB},
    )


@user_required
def office_to_pdf(request, conversion_type):
    if conversion_type not in OFFICE_CONVERSION_TYPES:
        messages.error(request, 'Tipo de conversão desconhecido.')
        return redirect('pdf_manager:dashboard')

    config = OFFICE_CONVERSION_TYPES[conversion_type]
    if request.method == 'POST':
        form = OfficeToPdfForm(request.POST, request.FILES, conversion_type=conversion_type)
        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            try:
                content = office_to_pdf_bytes(uploaded_file)
            except (OptionalDependencyError, ValueError) as exc:
                messages.error(request, str(exc))
            else:
                title = Path(uploaded_file.name).stem.replace('_', ' ').replace('-', ' ').strip()
                document = Document.objects.create(title=title, owner=request.user)
                document.file.save(f'{Path(uploaded_file.name).stem}.pdf', ContentFile(content), save=True)
                log_processing(request.user, 'office_to_pdf', uploaded_file.name)
                messages.success(request, 'Arquivo convertido para PDF com sucesso.')
                return redirect('pdf_manager:detail', pk=document.pk)
    else:
        form = OfficeToPdfForm(conversion_type=conversion_type)

    return render(
        request,
        'pdf_manager/office_to_pdf.html',
        {
            'form': form,
            'conversion_type': conversion_type,
            'conversion_title': config['title'],
            'max_upload_mb': settings.PDF_MANAGER_MAX_UPLOAD_MB,
        },
    )


@user_required
def download_document(request, pk):
    document = get_object_or_404(user_document_queryset(request.user), pk=pk)
    active_file = document.active_file
    filename = f'{Path(active_file.name).stem}.pdf'
    return FileResponse(active_file.open('rb'), as_attachment=True, filename=filename)

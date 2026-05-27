from io import BytesIO
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.files.base import ContentFile
from pypdf import PdfReader, PdfWriter


class OptionalDependencyError(RuntimeError):
    pass


def _read_pdf(file_obj):
    file_obj.seek(0)
    return PdfReader(file_obj)


def _writer_bytes(writer):
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def save_writer_to_document(document, writer, suffix):
    name = f'{Path(document.file.name).stem}-{suffix}.pdf'
    document.processed_file.save(name, ContentFile(_writer_bytes(writer)), save=True)


def rotate_pages(document, degrees):
    reader = _read_pdf(document.active_file)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(degrees)
        writer.add_page(page)
    save_writer_to_document(document, writer, f'girado-{degrees}')


def extract_pages(document, page_numbers):
    reader = _read_pdf(document.active_file)
    writer = PdfWriter()
    for number in page_numbers:
        index = number - 1
        if 0 <= index < len(reader.pages):
            writer.add_page(reader.pages[index])
    if not writer.pages:
        raise ValueError('Nenhuma pagina valida foi informada.')
    save_writer_to_document(document, writer, 'paginas')


def reorder_pages(document, page_numbers):
    reader = _read_pdf(document.active_file)
    if sorted(page_numbers) != list(range(1, len(reader.pages) + 1)):
        raise ValueError('Informe todas as paginas uma vez. Exemplo: 3,1,2.')
    writer = PdfWriter()
    for number in page_numbers:
        writer.add_page(reader.pages[number - 1])
    save_writer_to_document(document, writer, 'reordenado')


def delete_pages(document, page_numbers):
    reader = _read_pdf(document.active_file)
    writer = PdfWriter()
    excluded = {number - 1 for number in page_numbers}
    for index, page in enumerate(reader.pages):
        if index not in excluded:
            writer.add_page(page)
    if not writer.pages:
        raise ValueError('O PDF precisa manter pelo menos uma pagina.')
    save_writer_to_document(document, writer, 'sem-paginas')


def protect_pdf(document, password):
    reader = _read_pdf(document.active_file)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    save_writer_to_document(document, writer, 'protegido')


def merge_pdfs(files):
    writer = PdfWriter()
    for pdf_file in files:
        reader = _read_pdf(pdf_file)
        for page in reader.pages:
            writer.add_page(page)
    return _writer_bytes(writer)


def add_text(document, text, page_number, x, y, size):
    try:
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise OptionalDependencyError('Instale reportlab para inserir texto no PDF.') from exc

    reader = _read_pdf(document.active_file)
    writer = PdfWriter()
    for index, page in enumerate(reader.pages, start=1):
        if index == page_number:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            overlay = BytesIO()
            packet = canvas.Canvas(overlay, pagesize=(width, height))
            packet.setFont('Helvetica', size)
            packet.drawString(x, y, text)
            packet.save()
            overlay.seek(0)
            page.merge_page(PdfReader(overlay).pages[0])
        writer.add_page(page)
    save_writer_to_document(document, writer, 'texto')


def add_image(document, image_file, page_number, x, y, width):
    try:
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise OptionalDependencyError('Instale reportlab para inserir imagens no PDF.') from exc

    reader = _read_pdf(document.active_file)
    writer = PdfWriter()
    with NamedTemporaryFile(delete=False, suffix=Path(image_file.name).suffix) as temp:
        for chunk in image_file.chunks():
            temp.write(chunk)
        image_path = temp.name

    for index, page in enumerate(reader.pages, start=1):
        if index == page_number:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            overlay = BytesIO()
            packet = canvas.Canvas(overlay, pagesize=(page_width, page_height))
            packet.drawImage(image_path, x, y, width=width, preserveAspectRatio=True, mask='auto')
            packet.save()
            overlay.seek(0)
            page.merge_page(PdfReader(overlay).pages[0])
        writer.add_page(page)
    save_writer_to_document(document, writer, 'imagem')


def images_to_pdf_bytes(images):
    try:
        from PIL import Image
    except ImportError as exc:
        raise OptionalDependencyError('Instale Pillow para converter imagens em PDF.') from exc

    converted = []
    for image_file in images:
        image = Image.open(image_file)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        converted.append(image)
    if not converted:
        raise ValueError('Envie pelo menos uma imagem.')

    buffer = BytesIO()
    first, rest = converted[0], converted[1:]
    first.save(buffer, format='PDF', save_all=True, append_images=rest)
    return buffer.getvalue()


def get_libreoffice_executable():
    configured_path = getattr(settings, 'LIBREOFFICE_EXECUTABLE', '')
    candidates = [
        configured_path,
        'soffice',
        'libreoffice',
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if Path(candidate).exists() or candidate in {'soffice', 'libreoffice'}:
            return candidate
    raise OptionalDependencyError('LibreOffice nao foi encontrado neste computador.')


def office_to_pdf_bytes(uploaded_file):
    executable = get_libreoffice_executable()
    original_name = Path(uploaded_file.name)

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / original_name.name
        output_dir = Path(temp_dir) / 'output'
        output_dir.mkdir()

        with temp_path.open('wb') as target:
            for chunk in uploaded_file.chunks():
                target.write(chunk)

        command = [
            executable,
            '--headless',
            '--convert-to',
            'pdf',
            '--outdir',
            str(output_dir),
            str(temp_path),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        except FileNotFoundError as exc:
            raise OptionalDependencyError('LibreOffice nao foi encontrado no PATH do sistema.') from exc
        except subprocess.TimeoutExpired as exc:
            raise OptionalDependencyError('A conversao demorou demais e foi interrompida.') from exc

        output_pdf = output_dir / f'{original_name.stem}.pdf'
        if result.returncode != 0 or not output_pdf.exists():
            detail = (result.stderr or result.stdout or '').strip()
            message = 'Nao foi possivel converter o arquivo com o LibreOffice.'
            if detail:
                message = f'{message} Detalhe: {detail[:300]}'
            raise ValueError(message)

        return output_pdf.read_bytes()


def pdf_page_count(file_obj):
    file_obj.seek(0)
    reader = PdfReader(file_obj)
    return len(reader.pages)


def pdf_page_preview_bytes(file_obj, page_number=1, zoom=1.8):
    try:
        import fitz
    except ImportError as exc:
        raise OptionalDependencyError('Instale PyMuPDF para gerar a pre-visualizacao do PDF.') from exc

    file_obj.seek(0)
    with fitz.open(stream=file_obj.read(), filetype='pdf') as pdf:
        if pdf.page_count == 0:
            raise ValueError('O PDF nao possui paginas para pre-visualizar.')
        page_index = max(0, min(page_number - 1, pdf.page_count - 1))
        page = pdf.load_page(page_index)
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return pixmap.tobytes('png')


def parse_page_numbers(raw_value):
    try:
        return [int(part.strip()) for part in raw_value.split(',') if part.strip()]
    except ValueError as exc:
        raise ValueError('Use apenas numeros separados por virgula.') from exc

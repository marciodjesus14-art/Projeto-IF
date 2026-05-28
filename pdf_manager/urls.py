from django.urls import path

from . import views

app_name = 'pdf_manager'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('entrar/', views.user_login, name='login'),
    path('sair/', views.user_logout, name='logout'),
    path('registrar/', views.register, name='register'),
    path('master/', views.master_dashboard, name='master_dashboard'),
    path('master/login/', views.master_login, name='master_login'),
    path('master/logout/', views.master_logout, name='master_logout'),
    path('master/documentos/excluir-selecionados/', views.master_bulk_delete_documents, name='master_bulk_delete_documents'),
    path('master/documentos/<int:pk>/excluir/', views.master_delete_document, name='master_delete_document'),
    path('documentos/novo/', views.upload_document, name='upload'),
    path('documentos/juntar/', views.merge_documents, name='merge'),
    path('documentos/imagens-para-pdf/', views.images_to_pdf, name='images_to_pdf'),
    path('documentos/pdf-para-jpg/', views.pdf_to_jpg, name='pdf_to_jpg'),
    path('documentos/converter/<str:conversion_type>-para-pdf/', views.office_to_pdf, name='office_to_pdf'),
    path('documentos/<int:pk>/', views.document_detail, name='detail'),
    path('documentos/<int:pk>/preview.png', views.document_preview, name='preview'),
    path('documentos/<int:pk>/operar/', views.apply_operation, name='operate'),
    path('documentos/<int:pk>/cancelar-alteracoes/', views.cancel_document_changes, name='cancel_changes'),
    path('documentos/<int:pk>/baixar/', views.download_document, name='download'),
]

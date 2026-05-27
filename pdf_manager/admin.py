from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html

from .models import Document


admin.site.site_header = 'Admin IF Baiano'
admin.site.site_title = 'Gerenciador de PDF'
admin.site.index_title = 'Administracao do sistema'


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'created_at', 'updated_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('title', 'owner__username', 'owner__email')


admin.site.unregister(User)


class CustomUserChangeForm(UserChangeForm):
    ROLE_USER = 'user'
    ROLE_ADMIN = 'admin'
    role = forms.ChoiceField(
        label='Papel',
        choices=(
            (ROLE_USER, 'Usuario'),
            (ROLE_ADMIN, 'Admin'),
        ),
        help_text='Define se a conta acessa apenas as ferramentas ou tambem o painel administrativo.',
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['role'].initial = self.ROLE_ADMIN if self.instance.is_staff else self.ROLE_USER

    def save(self, commit=True):
        user = super().save(commit=False)
        selected_role = self.cleaned_data.get('role')
        if selected_role == self.ROLE_ADMIN:
            user.is_staff = True
        else:
            user.is_staff = False
            user.is_superuser = False
        if commit:
            user.save()
            self.save_m2m()
        return user


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    list_display = (
        'username',
        'email',
        'first_name',
        'role',
        'is_staff',
        'is_active',
        'password_reset_link',
        'delete_account_link',
    )
    list_editable = ('is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    actions = ('make_admin', 'make_regular_user')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Papel no sistema', {'fields': ('role',)}),
        ('Informacoes pessoais', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissoes avancadas', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas importantes', {'fields': ('last_login', 'date_joined')}),
    )

    @admin.display(description='Papel')
    def role(self, obj):
        return 'Admin' if obj.is_staff else 'Usuario'

    @admin.action(description='Definir selecionados como Admin')
    def make_admin(self, request, queryset):
        updated = queryset.update(is_staff=True)
        self.message_user(request, f'{updated} usuario(s) definidos como Admin.')

    @admin.action(description='Definir selecionados como Usuario')
    def make_regular_user(self, request, queryset):
        updated = queryset.update(is_staff=False, is_superuser=False)
        self.message_user(request, f'{updated} usuario(s) definidos como Usuario.')

    @admin.display(description='Senha')
    def password_reset_link(self, obj):
        url = reverse('admin:auth_user_password_change', args=[obj.pk])
        return format_html('<a class="button" href="{}">Alterar senha</a>', url)

    @admin.display(description='Conta')
    def delete_account_link(self, obj):
        url = reverse('admin:auth_user_delete', args=[obj.pk])
        return format_html('<a class="button" href="{}">Excluir conta</a>', url)

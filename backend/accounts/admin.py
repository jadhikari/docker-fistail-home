from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.urls import reverse
from django.utils.html import format_html

from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('email',)


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'is_active', 'is_staff')


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    model = CustomUser

    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'change_password_link')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('email', 'first_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )

    def change_password_link(self, obj):
        request = getattr(self, 'request', None)
        if request and request.user.is_superuser and obj.pk != request.user.pk:
            url = reverse('admin:auth_user_password_change', args=[obj.pk])
            return format_html('<a class="button" href="{}">Change password</a>', url)
        return "-"
    change_password_link.short_description = 'Password'
    change_password_link.allow_tags = True

    def changelist_view(self, request, extra_context=None):
        # Store the request on the instance so it can be accessed in `change_password_link`
        self.request = request
        return super().changelist_view(request, extra_context)

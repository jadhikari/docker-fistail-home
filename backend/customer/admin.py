from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from .models import Customer


class CustomerAdminForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

    def clean_status(self):
        new_status = self.cleaned_data.get('status')
        if self.instance and not self.instance.status and new_status:
            if self.current_user and not self.current_user.is_superuser:
                raise ValidationError("Only superusers can change status from inactive to active.")
        return new_status


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm

    list_display = (
        'name',
        'nationality',
        'visa_type',
        'phone_number',
        'email',
        'zairyu_card_number',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
    )
    search_fields = ('name',)
    list_filter = ('nationality', 'visa_type')
    readonly_fields = ('created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        if obj and not obj.status:
            if request.user.is_superuser:
                return [field.name for field in self.model._meta.fields if field.name != 'status']
            return [field.name for field in self.model._meta.fields]
        return super().get_readonly_fields(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        kwargs['form'] = self.form
        form = super().get_form(request, obj, **kwargs)
        form.current_user = request.user  # ✅ safely attach user to form instance
        return form

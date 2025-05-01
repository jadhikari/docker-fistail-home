from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
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

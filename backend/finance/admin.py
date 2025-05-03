from django.contrib import admin
from .models import Revenue

@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'customer',
        'deposit', 'deposit_discount_percent', 'deposit_after_discount',
        'initial_fee', 'initial_fee_discount_percent', 'initial_fee_after_discount',
        'internet', 'utilities',
        'rent', 'rent_discount_percent', 'rent_after_discount',
        'memo', 'created_at'
    ]
    search_fields = ['title', 'customer__id']  # Add customer ID or related field if needed
    list_filter = ['title', 'created_at']

    readonly_fields = [
        'deposit_after_discount', 
        'initial_fee_after_discount', 
        'rent_after_discount'
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('customer')

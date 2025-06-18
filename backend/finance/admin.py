from django.contrib import admin
from .models import HostelRevenue,HostelExpense

@admin.register(HostelRevenue)
class HostelRevenueAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'customer','year','month',
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

@admin.register(HostelExpense)
class HostelExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_hostel_name',
        'purchased_date',
        'purchased_by',
        'get_approved_by_name',  # ✅ Add this line
        'amount_before_tax',
        'amount_tax',
        'amount_total',
        'status',
        'created_by',
        'created_at',
        'updated_by',
        'updated_at',
    )
    list_filter = ('hostel', 'purchased_date', 'status')
    search_fields = ('purchased_by', 'memo', 'status', 'transaction_code')

    readonly_fields = ('amount_total', 'created_by', 'created_at', 'updated_by', 'updated_at')

    def get_hostel_name(self, obj):
        return obj.hostel.name if obj.hostel else "ALL"
    get_hostel_name.short_description = 'Hostel'
    get_hostel_name.admin_order_field = 'hostel'

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.first_name or obj.approved_by.email
        return "-"
    get_approved_by_name.short_description = 'Approved By'

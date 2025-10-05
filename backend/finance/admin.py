from django.contrib import admin
from .models import HostelRevenue, HostelExpense, UtilityExpense

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
        'amount',
        'status',
        'created_by',
        'created_at',
        'updated_by',
        'updated_at',
    )
    list_filter = ('hostel', 'purchased_date', 'status')
    search_fields = ('purchased_by', 'memo', 'status', 'transaction_code')

    readonly_fields = ('created_by', 'created_at', 'updated_by', 'updated_at')

    def get_hostel_name(self, obj):
        return obj.hostel.name if obj.hostel else "ALL"
    get_hostel_name.short_description = 'Hostel'
    get_hostel_name.admin_order_field = 'hostel'

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.first_name or obj.approved_by.email
        return "-"
    get_approved_by_name.short_description = 'Approved By'


@admin.register(UtilityExpense)
class UtilityExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'hostel',
        'expense_type',
        'amount',
        'billing_year',
        'billing_month',
        'date_from',
        'date_to',
        'paid_date',
        'usage_amount',
        'paid_by',
        'approval_status',
        'approved_by',
    )
    list_filter = (
        'hostel',
        'expense_type',
        'approval_status',
        'billing_year',
        'billing_month',
        'paid_date',
    )
    search_fields = (
        'hostel__name',
        'expense_type',
        'description',
        'paid_by__first_name',
        'paid_by__last_name',
        'paid_by__email',
    )
    readonly_fields = ()
    fieldsets = (
        ('Basic Information', {
            'fields': ('hostel', 'expense_type', 'amount', 'description')
        }),
        ('Dates', {
            'fields': ('billing_year', 'billing_month', 'date_from', 'date_to', 'paid_date')
        }),
        ('Usage Details', {
            'fields': ('usage_amount',)
        }),
        ('Approval', {
            'fields': ('paid_by', 'approval_status', 'approved_by')
        }),

    )
    ordering = ('-billing_year', '-billing_month')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('hostel', 'paid_by', 'approved_by')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        # Only superusers can edit approval fields
        if not request.user.is_superuser:
            readonly_fields.extend(['approval_status', 'approved_by'])
        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        # Hide approval section for non-superusers
        if not request.user.is_superuser:
            fieldsets = [fieldset for fieldset in fieldsets if fieldset[0] != 'Approval']
        return fieldsets

    def save_model(self, request, obj, form, change):
        # Only superusers can approve expenses
        if not request.user.is_superuser:
            if 'approval_status' in form.changed_data or 'approved_by' in form.changed_data:
                # Reset to original values if non-superuser tries to change approval
                if obj.pk:
                    original = self.model.objects.get(pk=obj.pk)
                    obj.approval_status = original.approval_status
                    obj.approved_by = original.approved_by
                else:
                    obj.approval_status = 'PENDING'
                    obj.approved_by = None
        else:
            # Superuser can approve and set themselves as approver
            if obj.approval_status in ['APPROVED', 'REJECTED'] and not obj.approved_by:
                obj.approved_by = request.user
        
        super().save_model(request, obj, form, change)

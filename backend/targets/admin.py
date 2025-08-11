from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Target, RentalContract


# RentalContractInline removed - RentalContract is independent of Target


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'target_period', 'target_amount', 'status', 
        'assigned_by', 'achievement_progress', 'created_by', 'created_at'
    ]
    list_filter = [
        'status', 'target_year', 'target_month', 'assigned_by'
    ]
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'assigned_by__email', 'description'
    ]
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    # No inlines - RentalContract is independent
    
    fieldsets = (
        ('Target Information', {
            'fields': ('user', 'target_amount', 'target_month', 'target_year')
        }),
        ('Assignment Details', {
            'fields': ('assigned_by', 'status', 'description')
        }),
        ('Audit Trail', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def target_period(self, obj):
        """Display formatted target period"""
        return obj.target_period
    target_period.short_description = "Target Period"

    def achievement_progress(self, obj):
        """Display achievement progress placeholder"""
        return format_html('<span style="color: gray;">N/A</span>')
    
    achievement_progress.short_description = "Progress"

    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related(
            'user', 'assigned_by'
        )

    def save_model(self, request, obj, form, change):
        """Auto-assign the current user for audit trail"""
        if not change:  # Only for new objects
            obj.created_by = request.user
            if not obj.assigned_by:
                obj.assigned_by = request.user
        else:  # For updates
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RentalContract)
class RentalContractAdmin(admin.ModelAdmin):
    list_display = [
        'customer_name', 'contract_date', 'total_amount', 'contract_type', 
        'living_num_people', 'created_at'
    ]
    list_filter = [
        'contract_type', 'cleaning_charge', 'created_at', 'updated_at'
    ]
    search_fields = [
        'customer_name', 'customer_number', 'building_address'
    ]
    readonly_fields = ('total_amount', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('customer_name', 'customer_number')
        }),
        ('Property Information', {
            'fields': ('building_address',)
        }),
        ('Contract Information', {
            'fields': ('contract_date',)
        }),
        ('Financial Information', {
            'fields': ('agent_fee', 'ad_fee')
        }),
        ('Contract Details', {
            'fields': ('contract_type', 'cancellation_notice_period', 'cancellation_period', 'cancellation_charge')
        }),
        ('Additional Charges', {
            'fields': ('deposit_fee', 'cleaning_charge', 'renew_fee')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_person', 'emergency_phone')
        }),
        ('Support & Living', {
            'fields': ('support_phone', 'living_num_people', 'rent_payment_date')
        }),
        ('Audit Trail', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related('created_by', 'updated_by')
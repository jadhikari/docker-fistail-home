from django.contrib import admin
from .models import Business, MunicipalShop, Staff, Dependent, Title, Transaction

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'registration_number', 'business_type', 'owner_name', 'office_rent', 'created_at']
    list_filter = ['business_type', 'industry_category', 'created_at']
    search_fields = ['name', 'registration_number', 'owner_name', 'email']
    readonly_fields = ['created_at', 'created_by', 'updated_at', 'updated_by']
    
    fieldsets = (
        ('Business Information', {
            'fields': ('name', 'registration_number', 'business_type', 'industry_category', 'email', 'phone', 'website', 'address', 'tax_number')
        }),
        ('Owner Information', {
            'fields': ('owner_name', 'owner_contact_number', 'owner_email', 'owner_address', 'office_rent')
        }),
        ('System Information', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(MunicipalShop)
class MunicipalShopAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'permit_id', 'shop_type', 'address', 'shop_rent', 'created_at']
    list_filter = ['shop_type', 'business', 'created_at']
    search_fields = ['name', 'permit_id', 'business__name']
    readonly_fields = ['created_at', 'created_by', 'updated_at', 'updated_by']
    
    fieldsets = (
        ('Shop Information', {
            'fields': ('business', 'name', 'permit_id', 'shop_type', 'address', 'shop_rent')
        }),
        ('System Information', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'role', 'employment_type', 'business', 'shop', 'salary', 'start_date', 'end_date', 'status', 'zairyucard_number']
    list_filter = ['employment_type', 'gender', 'role', 'business', 'shop', 'start_date', 'status']
    search_fields = ['full_name', 'zairyucard_number', 'contact_number', 'email']
    readonly_fields = ['created_at', 'created_by', 'updated_at', 'updated_by']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('full_name', 'dob', 'gender', 'contact_number', 'email', 'address')
        }),
        ('Employment Details', {
            'fields': ('role', 'employment_type', 'start_date', 'end_date', 'status', 'salary')
        }),
        ('Assignment', {
            'fields': ('business', 'shop'),
            'description': 'Staff can belong to either a business or a shop, but not both.'
        }),
        ('Zairyucard Information', {
            'fields': ('zairyucard_number', 'zairyucard_issue_date', 'zairyucard_expiry_date')
        }),
        ('System Information', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Dependent)
class DependentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'staff', 'relationship', 'dob', 'contact_number']
    list_filter = ['relationship', 'staff__business', 'staff__shop']
    search_fields = ['full_name', 'staff__full_name']
    readonly_fields = ['created_at', 'created_by', 'updated_at', 'updated_by']
    
    fieldsets = (
        ('Dependent Information', {
            'fields': ('staff', 'full_name', 'relationship', 'dob', 'contact_number', 'address')
        }),
        ('System Information', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'mode', 'is_active', 'created_at']
    list_filter = ['category', 'mode', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'created_by', 'updated_at', 'updated_by']
    
    fieldsets = (
        ('Title Information', {
            'fields': ('name', 'category', 'mode', 'description', 'is_active')
        }),
        ('System Information', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('category', 'mode', 'name')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_type', 'transaction_mode', 'title', 'period_display', 'amount', 'business', 'shop', 'created_at']
    list_filter = ['transaction_type', 'transaction_mode', 'title', 'year', 'month', 'business', 'shop', 'created_at']
    search_fields = ['business__name', 'shop__name', 'title__name', 'memo']
    readonly_fields = ['created_at', 'created_by', 'updated_at', 'updated_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('transaction_type', 'transaction_mode', 'title', 'year', 'month', 'amount', 'memo')
        }),
        ('Business & Shop Association', {
            'fields': ('business', 'shop'),
            'description': 'Transaction must be associated with a business. Shop is optional for business-level transactions.'
        }),
        ('System Information', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def period_display(self, obj):
        return f"{obj.get_month_display()} {obj.year}"
    period_display.short_description = 'Period'

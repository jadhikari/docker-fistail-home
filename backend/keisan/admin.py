from django.contrib import admin
from .models import Business, MunicipalShop, Staff, Dependent

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

from django.contrib import admin
from .models import Customer, BedAssignment


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

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_expired():
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_expired():
            return [f.name for f in self.model._meta.fields]
        return super().get_readonly_fields(request, obj)


@admin.register(BedAssignment)
class BedAssignmentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'bed', 'assigned_from', 'assigned_until', 'is_active_display']
    list_filter = ['assigned_from', 'assigned_until', 'bed__unit']
    search_fields = ['customer__name', 'bed__bed_num']

    def is_active_display(self, obj):
        return obj.is_active()
    is_active_display.boolean = True
    is_active_display.short_description = 'Currently Active'

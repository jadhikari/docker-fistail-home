from django.contrib import admin
from .models import Hostel, Unit, Bed, BedAssignmentHistory


@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'common_name',
        'hostel_type',
        'total_rooms',
        'contract_start_date',
        'contract_end_date',
        'hostel_manager',
        'deposit_fee',
        'initial_fee',
        'internet_fee',
        'utilities_fee',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
    )
    search_fields = ('name', 'common_name')
    list_filter = ('contract_start_date', 'contract_end_date')
    autocomplete_fields = ('hostel_manager', 'created_by', 'updated_by')
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('hostel_manager', 'created_by', 'updated_by')

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = (
        'hostel',
        'unit_type',
        'room_num',
        'num_of_beds',
        'unit_id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
    )
    list_filter = ('unit_type', 'hostel')
    search_fields = ('unit_id', 'hostel__name')
    autocomplete_fields = ('hostel', 'created_by', 'updated_by')
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('hostel', 'created_by', 'updated_by')


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = (
        'unit',
        'bed_num',
        'rent',
        'customer',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
    )
    readonly_fields = ('created_at', 'updated_at')

@admin.register(BedAssignmentHistory)
class BedAssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'bed',
        'customer',
        'assigned_date',
        'released_date',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
    )
    readonly_fields = ('created_at', 'updated_at')
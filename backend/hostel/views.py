from django.shortcuts import get_object_or_404, render,redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import Hostel, Unit, Bed, BedAssignmentHistory
from customer.models import Customer
from .forms import HostelForm, UnitForm, BedForm, BedAssignmentForm, EditReleasedDateForm
from django.contrib import messages
from finance.models import UtilityExpense
from datetime import datetime

def get_utility_payment_status():
    """
    Check utility bill payment status for all hostels for the previous 2 months only.
    Returns a dictionary with payment status information.
    """
    current_date = datetime.now().date()
    current_year = current_date.year
    current_month = current_date.month
    
    # Calculate previous 2 months (not current month)
    # Previous month
    prev_month = current_month - 1 if current_month > 1 else 12
    prev_month_year = current_year if current_month > 1 else current_year - 1
    
    # Month before previous month
    prev_prev_month = prev_month - 1 if prev_month > 1 else 12
    prev_prev_month_year = prev_month_year if prev_month > 1 else prev_month_year - 1
    
    # Get all hostels
    hostels = Hostel.objects.all()
    
    # Utility types that come monthly
    monthly_utilities = ['INTERNET', 'ELECTRICITY', 'GAS']
    
    unpaid_hostels = []
    all_paid = True
    
    for hostel in hostels:
        hostel_unpaid = {
            'hostel': hostel,
            'unpaid_bills': []
        }
        
        # Check monthly utilities for previous 2 months only
        for utility in monthly_utilities:
            for month_info in [
                {'month': prev_month, 'year': prev_month_year, 'label': f'{prev_month_year}/{prev_month} {utility.lower()}'},
                {'month': prev_prev_month, 'year': prev_prev_month_year, 'label': f'{prev_prev_month_year}/{prev_prev_month} {utility.lower()}'}
            ]:
                # Check if this utility bill is paid for this month
                paid = UtilityExpense.objects.filter(
                    hostel=hostel,
                    expense_type=utility,
                    billing_year=month_info['year'],
                    billing_month=month_info['month']
                ).exists()
                
                if not paid:
                    hostel_unpaid['unpaid_bills'].append(month_info['label'])
        
        # Check water utility with special 2-month billing logic
        # Water bills come every 2 months:
        # Jan+Feb bills come in Feb (month 2)
        # Mar+Apr bills come in Apr (month 4)
        # May+Jun bills come in Jun (month 6)
        # Jul+Aug bills come in Aug (month 8)
        # Sep+Oct bills come in Oct (month 10)
        # Nov+Dec bills come in Dec (month 12)
        
        def get_water_billing_month(check_month, check_year):
            """Get the month when water bill should be paid for the given month"""
            # Water bills are paid in even months (Feb, Apr, Jun, Aug, Oct, Dec)
            if check_month <= 2:
                return 2  # Jan+Feb bills come in Feb
            elif check_month <= 4:
                return 4  # Mar+Apr bills come in Apr
            elif check_month <= 6:
                return 6  # May+Jun bills come in Jun
            elif check_month <= 8:
                return 8  # Jul+Aug bills come in Aug
            elif check_month <= 10:
                return 10  # Sep+Oct bills come in Oct
            else:
                return 12  # Nov+Dec bills come in Dec
        
        def get_water_billing_period(check_month, check_year):
            """Get the billing period description for water"""
            if check_month <= 2:
                return f"{check_year}/1-2 water"  # Jan-Feb period
            elif check_month <= 4:
                return f"{check_year}/3-4 water"  # Mar-Apr period
            elif check_month <= 6:
                return f"{check_year}/5-6 water"  # May-Jun period
            elif check_month <= 8:
                return f"{check_year}/7-8 water"  # Jul-Aug period
            elif check_month <= 10:
                return f"{check_year}/9-10 water"  # Sep-Oct period
            else:
                return f"{check_year}/11-12 water"  # Nov-Dec period
        
        # Check water for previous 2 months (avoid duplicates)
        water_billing_periods = set()  # Track unique billing periods
        
        for month_info in [
            {'month': prev_month, 'year': prev_month_year},
            {'month': prev_prev_month, 'year': prev_prev_month_year}
        ]:
            billing_month = get_water_billing_month(month_info['month'], month_info['year'])
            billing_period = get_water_billing_period(month_info['month'], month_info['year'])
            
            # Only check each billing period once
            if billing_period not in water_billing_periods:
                water_billing_periods.add(billing_period)
                
                water_paid = UtilityExpense.objects.filter(
                    hostel=hostel,
                    expense_type='WATER',
                    billing_year=month_info['year'],
                    billing_month=billing_month
                ).exists()
                
                if not water_paid:
                    hostel_unpaid['unpaid_bills'].append(billing_period)
        
        # If there are unpaid bills, add to unpaid_hostels
        if hostel_unpaid['unpaid_bills']:
            # Format bills for better display
            hostel_unpaid['formatted_bills'] = format_unpaid_bills(hostel_unpaid['unpaid_bills'])
            unpaid_hostels.append(hostel_unpaid)
            all_paid = False
    
    return {
        'unpaid_hostels': unpaid_hostels,
        'total_unpaid_hostels': len(unpaid_hostels),
        'all_paid': all_paid
    }

def format_unpaid_bills(bills):
    """
    Format unpaid bills into a more meaningful single-line display.
    Example: ['2025/8 internet', '2025/7 internet', '2025/7 electricity'] 
    becomes: '2025/7, 2025/8 internet, 2025/7 electricity'
    """
    # Group bills by type
    bill_groups = {}
    for bill in bills:
        parts = bill.split(' ')
        if len(parts) >= 2:
            period = parts[0]  # e.g., '2025/8' or '2025/7-8'
            bill_type = ' '.join(parts[1:])  # e.g., 'internet' or 'electricity'
            
            if bill_type not in bill_groups:
                bill_groups[bill_type] = []
            bill_groups[bill_type].append(period)
    
    # Format each bill type
    formatted_parts = []
    for bill_type, periods in bill_groups.items():
        # Sort periods and remove duplicates
        unique_periods = sorted(set(periods))
        if len(unique_periods) == 1:
            formatted_parts.append(f"{unique_periods[0]} {bill_type}")
        else:
            # Group consecutive periods if possible
            formatted_periods = ", ".join(unique_periods)
            formatted_parts.append(f"{formatted_periods} {bill_type}")
    
    return ", ".join(formatted_parts)

@login_required(login_url='/accounts/login/')
def dashboard(request):
    query = request.GET.get('q', '')
    if query:
        hostels = Hostel.objects.filter(name__icontains=query).order_by('id')
    else:
        hostels = Hostel.objects.all().order_by('id')
    
    # Get utility payment status
    utility_status = get_utility_payment_status()
    
    context = {
        'hostels': hostels, 
        'query': query,
        'utility_status': utility_status
    }
    return render(request, 'hostel/dashboard.html', context)

@login_required(login_url='/accounts/login/')
def hostel_detail(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    units = hostel.units.all()  # related_name='units'
    return render(request, 'hostel/hostel_detail.html', {'hostel': hostel, 'units': units})

@login_required(login_url='/accounts/login/')
def hostel_create(request):
    if request.method == 'POST':
        form = HostelForm(request.POST, request.FILES)
        if form.is_valid():
            hostel = form.save(commit=False)
            hostel.created_by = request.user
            hostel.updated_by = request.user
            hostel.save()
            messages.success(request, "Created successfully.")
            return redirect('hostel:dashboard') # Change to your listing view name
    else:
        form = HostelForm()
    return render(request, 'hostel/hostel_form.html', {'form': form, 'title': 'Add Hostel'})

@login_required(login_url='/accounts/login/')
def hostel_update(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    if request.method == 'POST':
        form = HostelForm(request.POST, request.FILES, instance=hostel)
        if form.is_valid():
            hostel = form.save(commit=False)
            hostel.updated_by = request.user
            hostel.save()
            messages.success(request, "Updated successfully.")
            return redirect('hostel:dashboard')
    else:
        form = HostelForm(instance=hostel)
    return render(request, 'hostel/hostel_form.html', {'form': form, 'title': 'Edit Hostel'})


@login_required(login_url='/accounts/login/')
def unit_detail(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    return render(request, 'hostel/unit_detail.html', {'unit': unit})

@login_required(login_url='/accounts/login/')
def unit_create(request, hostel_id):
    hostel = get_object_or_404(Hostel, pk=hostel_id)
    if request.method == 'POST':
        form = UnitForm(request.POST, request.FILES, hostel=hostel)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.hostel = hostel  # Set FK explicitly
            unit.created_by = request.user
            unit.updated_by = request.user
            unit.save()
            return redirect('hostel:hostel_detail', pk=hostel.id)
    else:
        form = UnitForm(hostel=hostel)
    return render(request, 'hostel/unit_form.html', {'form': form, 'hostel': hostel, 'tit':'Add Unit'})


@login_required(login_url='/accounts/login/')
def unit_edit(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    hostel = unit.hostel
    if request.method == 'POST':
        form = UnitForm(request.POST, request.FILES, instance=unit, hostel=hostel)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.updated_by = request.user
            unit.save()
            return redirect('hostel:hostel_detail', pk=hostel.id)
    else:
        form = UnitForm(instance=unit, hostel=hostel)
    return render(request, 'hostel/unit_form.html', {'form': form, 'unit': unit, 'hostel': hostel, 'tit':'Edit Unit'})



@login_required(login_url='/accounts/login/')
def add_bed(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)
    
    if request.method == 'POST':
        form = BedForm(request.POST, unit=unit)
        
        if form.is_valid():
            bed_num = form.cleaned_data.get('bed_num')
            rent = form.cleaned_data.get('rent')

            if not bed_num or rent is None:
                form.add_error(None, "Both bed number and rent are required.")
            else:
                bed = form.save(commit=False)
                bed.unit = unit
                bed.save()

                # Optional: update unit tracking
                unit.updated_by = request.user
                unit.save()

                return redirect('hostel:unit_detail', unit.id)
    else:
        form = BedForm(unit=unit)

    return render(request, 'hostel/bed_form.html', {
        'form': form,
        'unit': unit,
        'title': 'Add Bed'
    })

@login_required(login_url='/accounts/login/')
def assign_bed(request, bed_id):
    bed = get_object_or_404(Bed, id=bed_id)

    if request.method == 'POST':
        form = BedAssignmentForm(request.POST, instance=bed)

        if form.is_valid():
            old_customer = bed.customer
            old_assigned_date = bed.assigned_date
            old_released_date = bed.released_date

            bed = form.save(commit=False)

            if form.fields['customer'].disabled:
                customer_id = request.POST.get('customer')
                if customer_id:
                    bed.customer = get_object_or_404(Customer, id=customer_id)

            if bed.released_date and bed.released_date <= timezone.now().date():
                if old_customer and old_assigned_date:
                    BedAssignmentHistory.objects.create(
                        bed=bed,
                        customer=old_customer,
                        assigned_date=old_assigned_date,
                        released_date=bed.released_date
                    )
                    old_customer.status = False
                    old_customer.save()

                bed.customer = None
                bed.assigned_date = None
                bed.released_date = None

            bed.save()
            bed.unit.updated_by = request.user
            bed.unit.save()

            return redirect('hostel:unit_detail', bed.unit.id)
    else:
        form = BedAssignmentForm(instance=bed)

    return render(request, 'hostel/assign_bed.html', {
        'form': form,
        'title': 'Assign Bed',
        'bed': bed
    })

@login_required(login_url='/accounts/login/')
def edit_released_date(request, bed_id):
    bed = get_object_or_404(Bed, id=bed_id)

    if not bed.customer or not bed.assigned_date:
        return redirect('hostel:unit_detail', bed.unit.id)

    if request.method == 'POST':
        form = EditReleasedDateForm(request.POST, instance=bed)
        if form.is_valid():
            bed = form.save(commit=False)

            if bed.customer:
                bed.customer.status = True
                bed.customer.save()

            bed.save()
            return redirect('hostel:unit_detail', bed.unit.id)
    else:
        form = EditReleasedDateForm(instance=bed)

    return render(request, 'hostel/edit_released_date.html', {
        'form': form,
        'title': 'Edit Released Date',
        'bed': bed
    })

@login_required(login_url='/accounts/login/')
def bed_edit(request, bed_id):
    bed = get_object_or_404(Bed, id=bed_id)
    
    if request.method == 'POST':
        form = BedForm(request.POST, instance=bed, unit=bed.unit)
        
        if form.is_valid():
            bed = form.save(commit=False)
            bed.updated_by = request.user
            bed.save()

            # Update unit tracking
            bed.unit.updated_by = request.user
            bed.unit.save()

            messages.success(request, "Bed updated successfully.")
            return redirect('hostel:unit_detail', bed.unit.id)
    else:
        form = BedForm(instance=bed, unit=bed.unit)

    return render(request, 'hostel/bed_form.html', {
        'form': form,
        'unit': bed.unit,
        'bed': bed,
        'title': 'Edit Bed'
    })
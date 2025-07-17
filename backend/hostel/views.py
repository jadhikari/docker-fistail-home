from django.shortcuts import get_object_or_404, render,redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import Hostel, Unit, Bed, BedAssignmentHistory
from customer.models import Customer
from .forms import HostelForm, UnitForm, BedForm, BedAssignmentForm, EditReleasedDateForm
from django.contrib import messages

@login_required(login_url='/accounts/login/')
def dashboard(request):
    query = request.GET.get('q', '')
    if query:
        hostels = Hostel.objects.filter(name__icontains=query).order_by('id')
    else:
        hostels = Hostel.objects.all().order_by('id')
    return render(request, 'hostel/dashboard.html', {'hostels': hostels, 'query': query})

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
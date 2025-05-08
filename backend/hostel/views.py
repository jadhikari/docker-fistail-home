from django.shortcuts import get_object_or_404, render,redirect
from .models import Hostel, Unit
from .forms import HostelForm, UnitForm
from django.contrib import messages

def dashboard(request):
    hostels = Hostel.objects.all()
    return render(request, 'hostel/dashboard.html', {'hostels': hostels})

def hostel_detail(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    units = hostel.units.all()  # related_name='units'
    return render(request, 'hostel/hostel_detail.html', {'hostel': hostel, 'units': units})


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



def unit_detail(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    return render(request, 'hostel/unit_detail.html', {'unit': unit})


def unit_create(request, hostel_id):
    hostel = get_object_or_404(Hostel, pk=hostel_id)
    if request.method == 'POST':
        form = UnitForm(request.POST, request.FILES, hostel=hostel)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.created_by = request.user
            unit.updated_by = request.user
            unit.save()
            return redirect('hostel:hostel_detail', pk=hostel.id)
    else:
        form = UnitForm(hostel=hostel)
    return render(request, 'hostel/unit_form.html', {'form': form, 'hostel': hostel})



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
    return render(request, 'hostel/unit_form.html', {'form': form, 'unit': unit, 'hostel': hostel})





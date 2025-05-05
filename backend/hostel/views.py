from django.shortcuts import get_object_or_404, render
from .models import Hostel, Unit

def dashboard(request):
    hostels = Hostel.objects.all()
    return render(request, 'hostel/dashboard.html', {'hostels': hostels})

def hostel_detail(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    units = hostel.units.all()  # related_name='units'
    return render(request, 'hostel/hostel_detail.html', {'hostel': hostel, 'units': units})

def unit_detail(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    return render(request, 'hostel/unit_detail.html', {'unit': unit})
from django.core.paginator import Paginator
from django.db.models import Q
from django_countries.fields import Country
from django_countries import countries
from django.shortcuts import render, redirect, get_object_or_404
from .models import Customer
from hostel.models import BedAssignmentHistory
from finance.models import Revenue  # Assuming app name is `finance`
from .forms import CustomerForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages



def dashboard(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    country_filter = request.GET.get('country', '')

    customers = Customer.objects.all().order_by('-id')

    if query:
        customers = customers.filter(
            Q(name__icontains=query) |
            Q(phone_number__icontains=query)
        )
    if status_filter == 'active':
        customers = customers.filter(status=True)
    elif status_filter == 'inactive':
        customers = customers.filter(status=False)

    if country_filter:
        customers = customers.filter(nationality=country_filter)

    paginator = Paginator(customers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_countries = sorted(set(c.nationality.code for c in Customer.objects.all() if c.nationality))
    country_choices = [(code, countries.name(code)) for code in all_countries]

    context = {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'country_filter': country_filter,
        'country_choices': country_choices,
    }
    return render(request, 'customer/dashboard.html', context)

@login_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.updated_by = request.user
            customer.save()
            messages.success(request, "Customer created successfully.")
            return redirect('customer:dashboard')
    else:
        form = CustomerForm()
    return render(request, 'customer/customer_form.html', {'form': form, 'is_edit': False})


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    # Prevent editing inactive customers
    if not customer.status:
        messages.warning(request, "This customer is inactive and cannot be edited.")
        return redirect('customer:dashboard')  # or return HttpResponseForbidden("Not allowed")

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.updated_by = request.user
            customer.save()
            messages.success(request, "Customer updated successfully.")
            return redirect('customer:dashboard')
    else:
        form = CustomerForm(instance=customer)
    
    return render(request, 'customer/customer_form.html', {'form': form, 'is_edit': True})

@login_required
def customer_detail(request, pk):
    h_customer = get_object_or_404(Customer, pk=pk)
    c_id = h_customer.id
    # Assigned bed (if any)
    assigned_bed = getattr(h_customer, 'bed_assignment', None)
    # Rent payment history
    rent_history = Revenue.objects.filter(id=c_id).order_by('-created_at')

    assigned_bed_history = None
    assigned_bed_history = BedAssignmentHistory.objects.filter(customer=c_id).all()

    context = {
        'customer': h_customer,
        'assigned_bed': assigned_bed,
        'rent_history': rent_history,
        'bed_history': assigned_bed_history,
    }
    return render(request, 'customer/customer_detail.html', context)
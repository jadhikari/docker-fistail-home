from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import date
from django.core.exceptions import ValidationError

from .models import Business, MunicipalShop, Staff, Dependent, Title, Transaction
from .forms import (
    BusinessForm, MunicipalShopForm, StaffForm, DependentForm, 
    BusinessSearchForm,
    RevenueForm, ExpenseForm
)





# Business Views
@login_required(login_url='/accounts/login/')
def business_list(request):
    """List all businesses with search and filtering - Main Dashboard"""
    form = BusinessSearchForm(request.GET)
    businesses = Business.objects.all()
    
    if form.is_valid():
        name = form.cleaned_data.get('name')
        business_type = form.cleaned_data.get('business_type')
        owner_name = form.cleaned_data.get('owner_name')
        
        if name:
            businesses = businesses.filter(name__icontains=name)
        if business_type:
            businesses = businesses.filter(business_type__icontains=business_type)
        if owner_name:
            businesses = businesses.filter(owner_name__icontains=owner_name)
    
    # Dashboard statistics
    total_businesses = Business.objects.count()
    total_shops = MunicipalShop.objects.count()
    total_staff = Staff.objects.count()
    total_dependents = Dependent.objects.count()
    
    # Salary statistics
    total_salary = Staff.objects.aggregate(total=Sum('salary'))['total'] or 0
    total_payroll = total_salary
    
    # Pagination
    paginator = Paginator(businesses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'total_count': businesses.count(),
        # Dashboard statistics
        'total_businesses': total_businesses,
        'total_shops': total_shops,
        'total_staff': total_staff,
        'total_dependents': total_dependents,
        'total_payroll': total_payroll,
    }
    
    return render(request, 'keisan/business_list.html', context)


@login_required(login_url='/accounts/login/')
def business_detail(request, pk):
    """Show business details"""
    business = get_object_or_404(Business, pk=pk)
    shops = business.shops.all()
    
    # Get status filter for staff
    staff_status = request.GET.get('staff_status', 'active')
    if staff_status == 'active':
        staff = business.staff.filter(status='Active')
    elif staff_status == 'inactive':
        staff = business.staff.filter(status__in=['Inactive', 'Terminated', 'Resigned'])
    else:
        staff = business.staff.all()
    
    context = {
        'business': business,
        'shops': shops,
        'staff': staff,
        'staff_status': staff_status,
    }
    
    return render(request, 'keisan/business_detail.html', context)


@login_required(login_url='/accounts/login/')
def business_create(request):
    """Create new business"""
    if request.method == 'POST':
        form = BusinessForm(request.POST)
        if form.is_valid():
            business = form.save(commit=False)
            business.created_by = request.user
            business.save()
            messages.success(request, f'Business "{business.name}" created successfully!')
            return redirect('keisan:business_list')
    else:
        form = BusinessForm()
    
    context = {'form': form, 'title': 'Create New Business'}
    return render(request, 'keisan/business_form.html', context)


@login_required(login_url='/accounts/login/')
def business_edit(request, pk):
    """Edit existing business"""
    business = get_object_or_404(Business, pk=pk)
    
    if request.method == 'POST':
        form = BusinessForm(request.POST, instance=business)
        if form.is_valid():
            business = form.save(commit=False)
            business.updated_by = request.user
            business.save()
            messages.success(request, f'Business "{business.name}" updated successfully!')
            return redirect('keisan:business_list')
    else:
        form = BusinessForm(instance=business)
    
    context = {'form': form, 'business': business, 'title': f'Edit Business: {business.name}'}
    return render(request, 'keisan/business_form.html', context)


# Municipal Shop Views
@login_required(login_url='/accounts/login/')
def shop_detail(request, pk):
    """Show shop details"""
    shop = get_object_or_404(MunicipalShop, pk=pk)
    
    # Get status filter for staff
    staff_status = request.GET.get('staff_status', 'active')
    if staff_status == 'active':
        staff = shop.staff.filter(status='Active')
    elif staff_status == 'inactive':
        staff = shop.staff.filter(status__in=['Inactive', 'Terminated', 'Resigned'])
    else:
        staff = shop.staff.all()
    
    context = {
        'shop': shop,
        'staff': staff,
        'staff_status': staff_status,
    }
    
    return render(request, 'keisan/shop_detail.html', context)


@login_required(login_url='/accounts/login/')
def shop_create(request):
    """Create new municipal shop"""
    # Get business from query parameter if coming from business details
    business_id = request.GET.get('business')
    initial_data = {}
    
    if business_id:
        try:
            business = Business.objects.get(pk=business_id)
            initial_data['business'] = business
        except Business.DoesNotExist:
            messages.error(request, 'Invalid business selected.')
            return redirect('keisan:business_list')
    
    if request.method == 'POST':
        form = MunicipalShopForm(request.POST)
        if form.is_valid():
            shop = form.save(commit=False)
            shop.created_by = request.user
            shop.save()
            messages.success(request, f'Shop "{shop.name}" created successfully!')
            # Redirect to business detail page if business_id is provided, otherwise to shop detail
            if business_id:
                return redirect('keisan:business_detail', pk=business_id)
            else:
                return redirect('keisan:shop_detail', pk=shop.pk)
    else:
        form = MunicipalShopForm(initial=initial_data)
    
    context = {
        'form': form, 
        'title': 'Create New Municipal Shop',
        'business': initial_data.get('business')
    }
    return render(request, 'keisan/shop_form.html', context)


@login_required(login_url='/accounts/login/')
def shop_edit(request, pk):
    """Edit existing municipal shop"""
    shop = get_object_or_404(MunicipalShop, pk=pk)
    
    if request.method == 'POST':
        form = MunicipalShopForm(request.POST, instance=shop)
        if form.is_valid():
            shop = form.save(commit=False)
            shop.updated_by = request.user
            shop.save()
            messages.success(request, f'Shop "{shop.name}" updated successfully!')
            # Redirect to business detail page since shop is always associated with a business
            return redirect('keisan:business_detail', pk=shop.business.pk)
    else:
        form = MunicipalShopForm(instance=shop)
    
    context = {'form': form, 'shop': shop, 'title': f'Edit Shop: {shop.name}'}
    return render(request, 'keisan/shop_form.html', context)


# Staff Views
@login_required(login_url='/accounts/login/')
def staff_detail(request, pk):
    """Show staff details"""
    staff = get_object_or_404(Staff, pk=pk)
    dependents = staff.dependents.all()
    
    context = {
        'staff': staff,
        'dependents': dependents,
    }
    
    return render(request, 'keisan/staff_detail.html', context)


@login_required(login_url='/accounts/login/')
def staff_create(request):
    """Create new staff member"""
    # Get business or shop from query parameters if coming from business/shop details
    business_id = request.GET.get('business')
    shop_id = request.GET.get('shop')
    initial_data = {}
    pre_selected_business = None
    pre_selected_shop = None
    
    if business_id:
        try:
            pre_selected_business = Business.objects.get(pk=business_id)
            initial_data['business'] = pre_selected_business
        except Business.DoesNotExist:
            messages.error(request, 'Invalid business selected.')
            return redirect('keisan:business_list')
    elif shop_id:
        try:
            pre_selected_shop = MunicipalShop.objects.get(pk=shop_id)
            pre_selected_business = pre_selected_shop.business
            initial_data['shop'] = pre_selected_shop
            initial_data['business'] = pre_selected_business
        except MunicipalShop.DoesNotExist:
            messages.error(request, 'Invalid shop selected.')
            return redirect('keisan:business_list')
    
    if request.method == 'POST':
        form = StaffForm(request.POST, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
        if form.is_valid():
            staff = form.save(commit=False)
            staff.created_by = request.user
            
            # Ensure proper business/shop relationship
            if staff.business and staff.shop:
                if staff.shop.business != staff.business:
                    messages.error(request, 'The selected shop does not belong to the selected business.')
                    context = {'form': form, 'business': pre_selected_business, 'shop': pre_selected_shop}
                    return render(request, 'keisan/staff_form.html', context)
            
            staff.save()
            messages.success(request, f'Staff member "{staff.full_name}" created successfully!')
            # Redirect based on whether staff is associated with business or shop
            if shop_id:
                return redirect('keisan:shop_detail', pk=shop_id)
            elif business_id:
                return redirect('keisan:business_detail', pk=business_id)
            else:
                return redirect('keisan:staff_detail', pk=staff.pk)
        else:
            # Form is not valid, show errors
            messages.error(request, 'Please correct the errors below.')
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
    else:
        form = StaffForm(initial=initial_data, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
    
    context = {
        'form': form,
        'business': pre_selected_business,
        'shop': pre_selected_shop,
    }
    return render(request, 'keisan/staff_form.html', context)


@login_required(login_url='/accounts/login/')
def staff_edit(request, pk):
    """Edit existing staff member"""
    staff = get_object_or_404(Staff, pk=pk)
    
    # Check if staff is active
    if staff.status != 'Active':
        messages.error(request, f'Cannot edit {staff.full_name} - Staff member is {staff.status}. Only active staff members can be edited.')
        return redirect('keisan:staff_detail', pk=staff.pk)
    
    # Get the current business and shop for pre-selection
    pre_selected_business = staff.business
    pre_selected_shop = staff.shop
    
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
        if form.is_valid():
            staff = form.save(commit=False)
            staff.updated_by = request.user
            
            # Ensure proper business/shop relationship
            if staff.business and staff.shop:
                if staff.shop.business != staff.business:
                    messages.error(request, 'The selected shop does not belong to the selected business.')
                    context = {'form': form, 'staff': staff, 'title': f'Edit Staff Member: {staff.full_name}'}
                    return render(request, 'keisan/staff_form.html', context)
            
            staff.save()
            messages.success(request, f'Staff member "{staff.full_name}" updated successfully!')
            # Redirect based on whether staff is associated with business or shop
            if staff.shop:
                return redirect('keisan:shop_detail', pk=staff.shop.pk)
            elif staff.business:
                return redirect('keisan:business_detail', pk=staff.business.pk)
            else:
                return redirect('keisan:staff_detail', pk=staff.pk)
    else:
        form = StaffForm(instance=staff, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
    
    context = {
        'form': form, 
        'staff': staff, 
        'title': f'Edit Staff Member: {staff.full_name}'
    }
    return render(request, 'keisan/staff_form.html', context)


# Dependent Views
@login_required(login_url='/accounts/login/')
def dependent_create(request, staff_id):
    """Create new dependent for a staff member"""
    staff = get_object_or_404(Staff, pk=staff_id)
    
    # Check if staff is active
    if staff.status != 'Active':
        messages.error(request, f'Cannot add dependent for {staff.full_name} - Staff member is {staff.status}. Only active staff members can have dependents.')
        return redirect('keisan:staff_detail', pk=staff_id)

    if request.method == 'POST':
        form = DependentForm(request.POST)
        if form.is_valid():
            dependent = form.save(commit=False)
            dependent.staff = staff
            dependent.created_by = request.user
            dependent.save()
            messages.success(request, f'Dependent "{dependent.full_name}" added successfully!')
            return redirect('keisan:staff_detail', pk=staff_id)
    else:
        form = DependentForm()
    
    context = {
        'form': form,
        'staff': staff,
        'title': f'Add Dependent for {staff.full_name}',
        'dependent': None  # Explicitly set dependent to None for new creation
    }
    
    return render(request, 'keisan/dependent_form.html', context)


@login_required(login_url='/accounts/login/')
def dependent_edit(request, pk):
    """Edit existing dependent"""
    dependent = get_object_or_404(Dependent, pk=pk)
    staff = dependent.staff
    
    # Check if staff is active
    if staff.status != 'Active':
        messages.error(request, f'Cannot edit dependent {dependent.full_name} - Staff member {staff.full_name} is {staff.status}. Only dependents of active staff members can be edited.')
        return redirect('keisan:staff_detail', pk=staff.pk)
    
    if request.method == 'POST':
        form = DependentForm(request.POST, instance=dependent)
        if form.is_valid():
            dependent = form.save(commit=False)
            dependent.updated_by = request.user
            dependent.save()
            messages.success(request, f'Dependent "{dependent.full_name}" updated successfully!')
            return redirect('keisan:staff_detail', pk=staff.pk)
    else:
        form = DependentForm(instance=dependent)
    
    context = {
        'form': form, 
        'dependent': dependent, 
        'staff': staff,
        'title': f'Edit Dependent: {dependent.full_name}'
    }
    return render(request, 'keisan/dependent_form.html', context)


# AJAX Views for dynamic functionality
@login_required(login_url='/accounts/login/')
def get_business_shops(request, business_id):
    """Get shops for a specific business (AJAX)"""
    try:
        business = Business.objects.get(pk=business_id)
        shops = business.shops.all()
        data = [{'id': shop.pk, 'name': shop.name} for shop in shops]
        return JsonResponse({'shops': data})
    except Business.DoesNotExist:
        return JsonResponse({'error': 'Business not found'}, status=404)


@login_required(login_url='/accounts/login/')
def get_staff_by_business(request, business_id):
    """Get staff for a specific business (AJAX)"""
    try:
        business = Business.objects.get(pk=business_id)
        staff = business.staff.all()
        data = [{'id': staff_member.pk, 'name': staff_member.full_name} for staff_member in staff]
        return JsonResponse({'staff': data})
    except Business.DoesNotExist:
        return JsonResponse({'error': 'Business not found'}, status=404)


@login_required(login_url='/accounts/login/')
def get_shops_for_business(request, business_id):
    """AJAX endpoint to get shops for a specific business"""
    try:
        business = get_object_or_404(Business, pk=business_id)
        shops = business.shops.all().values('id', 'name')
        return JsonResponse({'shops': list(shops)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# Transaction Views


@login_required(login_url='/accounts/login/')
def transaction_edit(request, pk):
    """Edit existing transaction - redirect to appropriate form based on transaction type"""
    transaction = get_object_or_404(Transaction, pk=pk)
    
    # Redirect to appropriate edit form based on transaction type
    if transaction.transaction_type == 'Revenue':
        return redirect('keisan:revenue_edit', pk=transaction.pk)
    else:  # Expense
        return redirect('keisan:expense_edit', pk=transaction.pk)


@login_required(login_url='/accounts/login/')
def revenue_edit(request, pk):
    """Edit existing revenue transaction"""
    transaction = get_object_or_404(Transaction, pk=pk, transaction_type='Revenue')
    
    # Get the current business and shop for pre-selection
    pre_selected_business = transaction.business
    pre_selected_shop = transaction.shop
    
    if request.method == 'POST':
        form = RevenueForm(request.POST, instance=transaction, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.updated_by = request.user
            transaction.save()
            messages.success(request, f'Revenue updated successfully!')
            # Redirect to appropriate financial summary based on transaction type
            if transaction.shop:
                return redirect('keisan:shop_financial_summary', pk=transaction.shop.pk)
            else:
                return redirect('keisan:business_financial_summary', pk=transaction.business.pk)
    else:
        # Create form with instance data to ensure proper binding
        initial_data = {
            'title': transaction.title.id if transaction.title else None,
            'transaction_mode': transaction.transaction_mode,
            'amount': transaction.amount,
            'memo': transaction.memo,
            'period': f"{transaction.year}-{transaction.month:02d}",
        }
        form = RevenueForm(instance=transaction, initial=initial_data, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
    
    context = {
        'form': form, 
        'transaction': transaction, 
        'title': f'Edit Revenue'
    }
    return render(request, 'keisan/revenue_form.html', context)


@login_required(login_url='/accounts/login/')
def expense_edit(request, pk):
    """Edit existing expense transaction"""
    transaction = get_object_or_404(Transaction, pk=pk, transaction_type='Expense')
    
    # Get the current business and shop for pre-selection
    pre_selected_business = transaction.business
    pre_selected_shop = transaction.shop
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=transaction, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.updated_by = request.user
            transaction.save()
            messages.success(request, f'Expense updated successfully!')
            # Redirect to appropriate financial summary based on transaction type
            if transaction.shop:
                return redirect('keisan:shop_financial_summary', pk=transaction.shop.pk)
            else:
                return redirect('keisan:business_financial_summary', pk=transaction.business.pk)
    else:
        # Create form with instance data to ensure proper binding
        initial_data = {
            'title': transaction.title.id if transaction.title else None,
            'transaction_mode': transaction.transaction_mode,
            'amount': transaction.amount,
            'memo': transaction.memo,
            'period': f"{transaction.year}-{transaction.month:02d}",
        }
        form = ExpenseForm(instance=transaction, initial=initial_data, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
    
    context = {
        'form': form, 
        'transaction': transaction, 
        'title': f'Edit Expense'
    }
    return render(request, 'keisan/expense_form.html', context)


@login_required(login_url='/accounts/login/')
def transaction_delete(request, pk):
    """Delete transaction"""
    transaction = get_object_or_404(Transaction, pk=pk)
    
    if request.method == 'POST':
        business_pk = transaction.business.pk
        shop_pk = transaction.shop.pk if transaction.shop else None
        transaction.delete()
        messages.success(request, 'Transaction deleted successfully!')
        
        # Redirect to appropriate financial summary based on transaction type
        if shop_pk:
            return redirect('keisan:shop_financial_summary', pk=shop_pk)
        else:
            return redirect('keisan:business_financial_summary', pk=business_pk)
    
    context = {
        'transaction': transaction,
    }
    return render(request, 'keisan/transaction_confirm_delete.html', context)


@login_required(login_url='/accounts/login/')
def business_financial_summary(request, pk):
    """Show financial summary for a specific business"""
    business = get_object_or_404(Business, pk=pk)
    
    # Get filter parameters
    year = request.GET.get('year', timezone.now().year)
    month = request.GET.get('month')
    
    # Base queryset for business transactions
    transactions = business.transactions.filter(year=year)
    if month:
        transactions = transactions.filter(month=month)
    
    # Calculate totals
    revenue_online = transactions.filter(transaction_type='Revenue', transaction_mode='Online').aggregate(total=Sum('amount'))['total'] or 0
    revenue_offline = transactions.filter(transaction_type='Revenue', transaction_mode='Offline').aggregate(total=Sum('amount'))['total'] or 0
    expense_online = transactions.filter(transaction_type='Expense', transaction_mode='Online').aggregate(total=Sum('amount'))['total'] or 0
    expense_offline = transactions.filter(transaction_type='Expense', transaction_mode='Offline').aggregate(total=Sum('amount'))['total'] or 0
    
    total_revenue = revenue_online + revenue_offline
    total_expense = expense_online + expense_offline
    net_profit = total_revenue - total_expense
    
    # Get transactions by shop
    shop_summaries = []
    for shop in business.shops.all():
        shop_transactions = transactions.filter(shop=shop)
        shop_revenue = shop_transactions.filter(transaction_type='Revenue').aggregate(total=Sum('amount'))['total'] or 0
        shop_expense = shop_transactions.filter(transaction_type='Expense').aggregate(total=Sum('amount'))['total'] or 0
        shop_profit = shop_revenue - shop_expense
        
        shop_summaries.append({
            'shop': shop,
            'revenue': shop_revenue,
            'expense': shop_expense,
            'profit': shop_profit,
            'transaction_count': shop_transactions.count()
        })
    
    # Get transaction lists for business and all shops
    business_revenues = transactions.filter(transaction_type='Revenue', shop__isnull=True).order_by('-year', '-month', '-created_at')
    business_expenses = transactions.filter(transaction_type='Expense', shop__isnull=True).order_by('-year', '-month', '-created_at')
    shop_revenues = transactions.filter(transaction_type='Revenue', shop__isnull=False).order_by('-year', '-month', '-created_at')
    shop_expenses = transactions.filter(transaction_type='Expense', shop__isnull=False).order_by('-year', '-month', '-created_at')
    
    # Calculate totals for each category
    business_revenue_total = business_revenues.aggregate(total=Sum('amount'))['total'] or 0
    business_expense_total = business_expenses.aggregate(total=Sum('amount'))['total'] or 0
    shop_revenue_total = shop_revenues.aggregate(total=Sum('amount'))['total'] or 0
    shop_expense_total = shop_expenses.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'business': business,
        'year': year,
        'month': month,
        'revenue_online': revenue_online,
        'revenue_offline': revenue_offline,
        'expense_online': expense_online,
        'expense_offline': expense_offline,
        'total_revenue': total_revenue,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'shop_summaries': shop_summaries,
        'transaction_count': transactions.count(),
        'business_revenues': business_revenues,
        'business_expenses': business_expenses,
        'shop_revenues': shop_revenues,
        'shop_expenses': shop_expenses,
        'business_revenue_total': business_revenue_total,
        'business_expense_total': business_expense_total,
        'shop_revenue_total': shop_revenue_total,
        'shop_expense_total': shop_expense_total,
    }
    
    return render(request, 'keisan/business_financial_summary.html', context)


@login_required(login_url='/accounts/login/')
def shop_financial_summary(request, pk):
    """Show financial summary for a specific shop"""
    shop = get_object_or_404(MunicipalShop, pk=pk)
    
    # Get filter parameters
    year = request.GET.get('year', timezone.now().year)
    month = request.GET.get('month')
    
    # Base queryset for shop transactions
    transactions = shop.transactions.filter(year=year)
    if month:
        transactions = transactions.filter(month=month)
    
    # Calculate totals
    revenue_online = transactions.filter(transaction_type='Revenue', transaction_mode='Online').aggregate(total=Sum('amount'))['total'] or 0
    revenue_offline = transactions.filter(transaction_type='Revenue', transaction_mode='Offline').aggregate(total=Sum('amount'))['total'] or 0
    expense_online = transactions.filter(transaction_type='Expense', transaction_mode='Online').aggregate(total=Sum('amount'))['total'] or 0
    expense_offline = transactions.filter(transaction_type='Expense', transaction_mode='Offline').aggregate(total=Sum('amount'))['total'] or 0
    
    total_revenue = revenue_online + revenue_offline
    total_expense = expense_online + expense_offline
    net_profit = total_revenue - total_expense
    
    # Get transaction lists for this shop only
    shop_revenues = transactions.filter(transaction_type='Revenue').order_by('-year', '-month', '-created_at')
    shop_expenses = transactions.filter(transaction_type='Expense').order_by('-year', '-month', '-created_at')
    
    # Calculate totals for shop transactions
    shop_revenue_total = shop_revenues.aggregate(total=Sum('amount'))['total'] or 0
    shop_expense_total = shop_expenses.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'shop': shop,
        'year': year,
        'month': month,
        'revenue_online': revenue_online,
        'revenue_offline': revenue_offline,
        'expense_online': expense_online,
        'expense_offline': expense_offline,
        'total_revenue': total_revenue,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'transaction_count': transactions.count(),
        'shop_revenues': shop_revenues,
        'shop_expenses': shop_expenses,
        'shop_revenue_total': shop_revenue_total,
        'shop_expense_total': shop_expense_total,
    }
    
    return render(request, 'keisan/shop_financial_summary.html', context)


# Revenue and Expense Views
@login_required(login_url='/accounts/login/')
def revenue_create(request):
    """Create new revenue transaction"""
    # Get business or shop from query parameters if coming from business/shop details
    business_id = request.GET.get('business')
    shop_id = request.GET.get('shop')
    initial_data = {}
    pre_selected_business = None
    pre_selected_shop = None
    
    if business_id:
        try:
            pre_selected_business = Business.objects.get(pk=business_id)
            initial_data['business'] = pre_selected_business
        except Business.DoesNotExist:
            messages.error(request, 'Invalid business selected.')
            return redirect('keisan:business_list')
    elif shop_id:
        try:
            pre_selected_shop = MunicipalShop.objects.get(pk=shop_id)
            pre_selected_business = pre_selected_shop.business
            initial_data['shop'] = pre_selected_shop
            initial_data['business'] = pre_selected_business
        except MunicipalShop.DoesNotExist:
            messages.error(request, 'Invalid shop selected.')
            return redirect('keisan:business_list')
    
    if request.method == 'POST':
        form = RevenueForm(request.POST, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user
            transaction.save()
            messages.success(request, f'Revenue transaction created successfully!')
            # Redirect based on whether transaction is associated with business or shop
            if shop_id:
                return redirect('keisan:shop_detail', pk=shop_id)
            elif business_id:
                return redirect('keisan:business_detail', pk=business_id)
            else:
                return redirect('keisan:transaction_detail', pk=transaction.pk)
        else:
            # Form is not valid, show errors
            messages.error(request, 'Please correct the errors below.')
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
    else:
        form = RevenueForm(initial=initial_data, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
    
    context = {
        'form': form,
        'business': pre_selected_business,
        'shop': pre_selected_shop,
        'title': 'Add Revenue',
        'transaction_type': 'Revenue'
    }
    return render(request, 'keisan/revenue_form.html', context)


@login_required(login_url='/accounts/login/')
def expense_create(request):
    """Create new expense transaction"""
    # Get business or shop from query parameters if coming from business/shop details
    business_id = request.GET.get('business')
    shop_id = request.GET.get('shop')
    initial_data = {}
    pre_selected_business = None
    pre_selected_shop = None
    
    if business_id:
        try:
            pre_selected_business = Business.objects.get(pk=business_id)
            initial_data['business'] = pre_selected_business
        except Business.DoesNotExist:
            messages.error(request, 'Invalid business selected.')
            return redirect('keisan:business_list')
    elif shop_id:
        try:
            pre_selected_shop = MunicipalShop.objects.get(pk=shop_id)
            pre_selected_business = pre_selected_shop.business
            initial_data['shop'] = pre_selected_shop
            initial_data['business'] = pre_selected_business
        except MunicipalShop.DoesNotExist:
            messages.error(request, 'Invalid shop selected.')
            return redirect('keisan:business_list')
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user
            transaction.save()
            messages.success(request, f'Expense transaction created successfully!')
            # Redirect based on whether transaction is associated with business or shop
            if shop_id:
                return redirect('keisan:shop_detail', pk=shop_id)
            elif business_id:
                return redirect('keisan:business_detail', pk=business_id)
            else:
                return redirect('keisan:transaction_detail', pk=transaction.pk)
        else:
            # Form is not valid, show errors
            messages.error(request, 'Please correct the errors below.')
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
    else:
        form = ExpenseForm(initial=initial_data, pre_selected_business=pre_selected_business, pre_selected_shop=pre_selected_shop)
    
    context = {
        'form': form,
        'business': pre_selected_business,
        'shop': pre_selected_shop,
        'title': 'Add Expense',
        'transaction_type': 'Expense'
    }
    return render(request, 'keisan/expense_form.html', context)

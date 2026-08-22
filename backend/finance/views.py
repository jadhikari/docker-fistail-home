from django.contrib.auth import get_user_model
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.utils import timezone
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from .models import HostelRevenue, HostelExpense, UtilityExpense, StaffExpense
from .forms import HostelExpenseForm, UtilityExpenseForm, StaffExpenseForm, AdFeeReceiptForm
from .utils import send_revenue_email
from .excel_exports import (
    export_revenues_to_excel,
    export_expenses_to_excel,
    export_staff_expenses_to_excel,
    export_pending_ad_fees_to_excel,
    export_real_estate_revenue_to_excel,
    export_unpaid_rent_to_excel,
)
from .finance_helpers.rent_defaulters import get_rent_defaulters
from hostel.models import Bed
from targets.models import RentalContract


@login_required(login_url='/accounts/login/')
def revenues(request):
    name = request.GET.get('name')
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    hostel = request.GET.get('hostel')
    record_type = request.GET.get('record_type', 'rent')  # Default to 'rent'
    today = timezone.now()
    query = Q()
    if name:
        query &= Q(customer__name__icontains=name)
    if hostel:
        query &= Q(customer__bed_assignment__unit__hostel__name__icontains=hostel)
    # Default filter by creation date instead of revenue year/month
    if from_date:
        from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
    else:
        from_date = today.replace(day=1)
    # Default = today
    if to_date:
        to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    else:
        to_date = today
    query &= Q(created_at__date__gte=from_date, created_at__date__lte=to_date)
    # Filter by record type (rent or registration)
    if record_type == 'registration':
        query &= Q(title='registration_fee')
    else:  # Default to 'rent'
        query &= Q(title='rent')
    # Get all revenues with the base query, ordered by creation date (newest first)
    all_revenues = HostelRevenue.objects.select_related('customer', 'created_by').filter(query).order_by('-created_at')
    # Separate registration and rent records based on filter
    if record_type == 'registration':
        registration_revenues = all_revenues
        rent_revenues = all_revenues.none()  # Empty queryset
    else:  # record_type == 'rent' (default)
        registration_revenues = all_revenues.none()  # Empty queryset
        rent_revenues = all_revenues
    registration_total = registration_revenues.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    rent_collection_total = rent_revenues.aggregate(total=Sum('collected_amount'))['total'] or Decimal('0')
    rent_total_amount = rent_revenues.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    # No pagination for registration revenues - display all records
    registration_page_obj = registration_revenues
    # Pagination for rent revenues (limit 20)
    rent_page = request.GET.get('rent_page', 1)
    rent_paginator = Paginator(rent_revenues, 20)
    rent_page_obj = rent_paginator.get_page(rent_page)
    # Calculate page totals
    registration_page_total = registration_revenues.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    rent_page_total_amount = rent_page_obj.object_list.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    rent_page_collection_total = rent_page_obj.object_list.aggregate(total=Sum('collected_amount'))['total'] or Decimal('0')
    # ✅ Only allow download if there are results
    if request.GET.get('download') == 'excel':
        if all_revenues.exists():
            return export_revenues_to_excel(all_revenues, record_type)
        else:
            messages.warning(request, "No data available to export.")
    if request.GET and not any([name, from_date, to_date, hostel]):
        messages.warning(request, "No filter parameters provided.")
    year_choices = HostelRevenue.objects.values_list('year', flat=True).distinct().order_by('-year')
    # Get all hostels for the filter dropdown
    from hostel.models import Hostel
    all_hostels = Hostel.objects.filter(status=True).order_by('name')
    return render(request, 'finance/revenues_dashboard.html', {
        'registration_revenues': registration_page_obj,
        'rent_revenues': rent_page_obj,
        'registration_total': registration_total,
        'registration_page_total': registration_page_total,
        'rent_collection_total': rent_collection_total,
        'rent_total_amount': rent_total_amount,
        'rent_page_total_amount': rent_page_total_amount,
        'rent_page_collection_total': rent_page_collection_total,
        'name': name,
        'from_date': from_date.strftime("%Y-%m-%d"),
        'to_date': to_date.strftime("%Y-%m-%d"),
        'selected_hostel': hostel,
        'selected_record_type': record_type,
        'year_choices': year_choices,
        'month_choices': [(i, i) for i in range(1, 13)],
        'all_hostels': all_hostels,
    })


@login_required(login_url='/accounts/login/')
def real_estate_revenue(request):
    """Display real estate revenue generated by rental contracts."""
    if not (request.user.is_superuser or request.user.has_perm('targets.view_rentalcontract')):
        raise PermissionDenied
    today = timezone.now().date()
    customer_name = request.GET.get('customer_name', '').strip()
    management_company = request.GET.get('management_company', '').strip()
    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()

    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date() if from_date_str else today.replace(day=1)
    except ValueError:
        from_date = today.replace(day=1)
    try:
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date() if to_date_str else today
    except ValueError:
        to_date = today

    contracts = RentalContract.objects.select_related('created_by', 'ad_fee_confirmed_by', 'target_to', 'target_to__target_to')
    if customer_name:
        contracts = contracts.filter(customer_name__icontains=customer_name)
    if management_company:
        contracts = contracts.filter(management_company_name=management_company)
    management_companies = RentalContract.objects.exclude(management_company_name='').values_list('management_company_name', flat=True).distinct().order_by('management_company_name')
    agent_contracts = contracts.filter(contract_date__range=(from_date, to_date))
    received_ad_fees = contracts.filter(ad_fee_confirmed_at__isnull=False, ad_fee_received_date__range=(from_date, to_date))
    pending_ad_fees = contracts.filter(ad_fee__gt=0, ad_fee_confirmed_at__isnull=True).order_by('contract_date')
    total_agent_fee = agent_contracts.aggregate(total=Sum('agent_fee'))['total'] or Decimal('0')
    total_ad_fee = received_ad_fees.aggregate(total=Sum('ad_fee_received_amount'))['total'] or Decimal('0')
    revenue_contracts = contracts.filter(Q(contract_date__range=(from_date, to_date)) | Q(ad_fee_confirmed_at__isnull=False, ad_fee_received_date__range=(from_date, to_date))).distinct().order_by('-created_at')
    export_type = request.GET.get('export')
    if export_type == 'pending':
        return export_pending_ad_fees_to_excel(pending_ad_fees)
    if export_type == 'revenue':
        return export_real_estate_revenue_to_excel(revenue_contracts, from_date, to_date)
    paginator = Paginator(revenue_contracts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    for contract in page_obj:
        contract.period_agent_fee = contract.agent_fee if from_date <= contract.contract_date <= to_date else Decimal('0')
        contract.period_ad_fee = contract.ad_fee_received_amount if contract.ad_fee_received_date and from_date <= contract.ad_fee_received_date <= to_date else Decimal('0')
        contract.period_revenue = contract.period_agent_fee + (contract.period_ad_fee or Decimal('0'))
    page_total_revenue = sum((contract.period_revenue for contract in page_obj), Decimal('0'))
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    if 'export' in query_params:
        query_params.pop('export')

    return render(request, 'finance/real_estate_revenue.html', {
        'contracts': page_obj, 'total_count': revenue_contracts.count(), 'total_agent_fee': total_agent_fee,
        'total_ad_fee': total_ad_fee, 'total_revenue': total_agent_fee + total_ad_fee,
        'page_total_revenue': page_total_revenue,
        'customer_name': customer_name, 'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'), 'query_string': query_params.urlencode(),
        'management_companies': management_companies, 'selected_management_company': management_company,
        'can_confirm_ad_fee': request.user.is_superuser or request.user.has_perm('targets.change_rentalcontract'),
        'pending_ad_fees': pending_ad_fees[:20], 'pending_ad_fee_count': pending_ad_fees.count(),
    })


@login_required(login_url='/accounts/login/')
def confirm_ad_fee_receipt(request, pk):
    """Manually confirm the single AD fee receipt for a rental contract."""
    if not (request.user.is_superuser or request.user.has_perm('targets.change_rentalcontract')):
        raise PermissionDenied
    contract = get_object_or_404(RentalContract, pk=pk)
    if contract.ad_fee_confirmed_at:
        messages.info(request, 'The AD fee receipt for this contract has already been confirmed.')
        return redirect('finance:real_estate_revenue')

    if request.method == 'POST':
        form = AdFeeReceiptForm(request.POST, instance=contract)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.ad_fee_confirmed_by = request.user
            receipt.ad_fee_confirmed_at = timezone.now()
            receipt.updated_by = request.user
            receipt.save(update_fields=['ad_fee_received_amount', 'ad_fee_transfer_fee', 'ad_fee_received_date', 'ad_fee_memo', 'ad_fee_confirmed_by', 'ad_fee_confirmed_at', 'updated_by', 'updated_at'])
            messages.success(request, f'AD fee receipt for {contract.customer_name} was confirmed successfully.')
            return redirect('finance:real_estate_revenue')
    else:
        form = AdFeeReceiptForm(instance=contract, initial={'ad_fee_received_date': timezone.now().date()})
    return render(request, 'finance/confirm_ad_fee_receipt.html', {'contract': contract, 'form': form})


@login_required(login_url='/accounts/login/')
def revenue_detail(request, pk):
    revenue = get_object_or_404(HostelRevenue, pk=pk)
    return render(request, 'finance/revenue_detail.html', {'revenue': revenue})


@login_required(login_url='/accounts/login/')
def get_previous_prepaid_amount(customer, year, month):
    """
    Get the prepaid amount from the previous month's rent payment.
    Returns the prepaid amount if the previous month had a prepaid payment.
    """
    # Calculate previous month
    prev_month = month - 1
    prev_year = year
    if prev_month <= 0:
        prev_month = 12
        prev_year = year - 1
    try:
        prev_revenue = HostelRevenue.objects.get(title='rent', customer=customer, year=prev_year, month=prev_month)
        # Return prepaid amount if it exists and payment type is prepaid
        if prev_revenue.payment_type == 'prepaid' and prev_revenue.prepaid_amount:
            return prev_revenue.prepaid_amount
        return Decimal('0')
    except HostelRevenue.DoesNotExist:
        return Decimal('0')

@login_required(login_url='/accounts/login/')
def monthly_rent(request, customer_id):
    """
    Handle monthly rent payment processing with comprehensive validation:
    - Ensures customer has registration fee
    - Validates rent payment chronology (sequential months, no duplicates)
    - Calculates prepaid/postpaid amounts
    - Handles rent discounts with memo requirements
    """
    customer_details = get_object_or_404(Bed.objects.select_related('unit', 'unit__hostel', 'customer'), customer=customer_id)
    # Stage 1: Validate required bed fees are set
    missing_fees = []
    if not customer_details.rent or customer_details.rent == 0:
        missing_fees.append("Base Rent")
    if not customer_details.utilities_fee or customer_details.utilities_fee == 0:
        missing_fees.append("Utilities Fee")
    if missing_fees:
        messages.error(request, f"Please add {', '.join(missing_fees)} in bed details. You cannot process without these fees.")
        return redirect('customer:customer_detail', customer_id)
    if request.method == "POST":
        # Parse payment month from form
        month_input = request.POST.get("rent_month")
        if not month_input:
            messages.error(request, "Payment month is required.")
            return redirect(request.path)
        year, month = map(int, month_input.split("-"))
        # Stage 2: Validate registration fee payment requirement
        registration_payment = HostelRevenue.objects.filter(title='registration_fee', customer=customer_details.customer).first()
        if not registration_payment:
            messages.error(request, "Customer must pay registration fee before making rent payments.")
            return redirect(request.path)
        # Stage 3: Check for duplicate payment
        existing_rent_payments = HostelRevenue.objects.filter(title='rent', customer=customer_details.customer).order_by('year', 'month')
        duplicate_payment = existing_rent_payments.filter(year=year, month=month).first()
        if duplicate_payment:
            messages.error(request, f"Payment for {year}-{month:02d} already exists. Please select a different month.")
            return redirect(request.path)
        # Stage 4: Validate sequential month payment
        if not existing_rent_payments.exists():
            # First rent payment must be in registration month
            reg_year = registration_payment.year
            reg_month = registration_payment.month
            if year != reg_year or month != reg_month:
                messages.error(request, f"First rent payment must be in the registration month. Customer registered in {reg_year}-{reg_month:02d}. First rent payment should be for {reg_year}-{reg_month:02d}.")
                return redirect(request.path)
        else:
            # Subsequent payments must follow previous payment sequentially
            last_payment = existing_rent_payments.last()
            last_year = last_payment.year
            last_month = last_payment.month
            expected_month = last_month + 1
            expected_year = last_year
            if expected_month > 12:
                expected_month = 1
                expected_year += 1
            if year < last_year or (year == last_year and month < last_month):
                messages.error(request, f"Cannot pay rent for a month before the last payment. Last payment was for {last_year}-{last_month:02d}.")
                return redirect(request.path)
            if year != expected_year or month != expected_month:
                messages.error(request, f"Cannot skip months. Last payment was for {last_year}-{last_month:02d}. Next payment should be for {expected_year}-{expected_month:02d}.")
                return redirect(request.path)
        # Stage 5: Parse and validate numeric payment amounts
        try:
            base_rent = Decimal(request.POST.get("rent", "0"))
            internet_fee = Decimal(request.POST.get("internet", "0"))
            utilities_fee = Decimal(request.POST.get("utilities", "0"))
            rent_discount_percent = Decimal(request.POST.get("rent_discount_percent", "0"))
            payment_type = request.POST.get("payment_type", "")
            collected_amount_str = request.POST.get("collected_amount", "").strip()
            collected_amount = Decimal(collected_amount_str) if collected_amount_str and collected_amount_str not in ("", "NaN") else Decimal("0")
            prepaid_amount_str = request.POST.get("prepaid_amount", "").strip()
            prepaid_amount = Decimal(prepaid_amount_str) if prepaid_amount_str and prepaid_amount_str not in ("", "NaN") else Decimal("0")
        except InvalidOperation as e:
            messages.error(request, f"Invalid numeric values in the form. Please check all amount fields. Error: {str(e)}")
            return redirect(request.path)
        # Calculate rent components
        rent_after_discount = base_rent * (Decimal(1) - rent_discount_percent / Decimal(100))
        total_amount = rent_after_discount + internet_fee + utilities_fee
        # Validate memo requirement for discounted rent
        memo = request.POST.get("memo", "").strip()
        if rent_discount_percent > 0 and not memo:
            messages.error(request, "Memo is required when a discount is applied.")
            return redirect(request.path)
        # Stage 6: Calculate prepaid/postpaid from previous month
        previous_prepaid = Decimal('0')
        previous_postpaid = Decimal('0')
        prev_month = month - 1
        prev_year = year
        if prev_month <= 0:
            prev_month = 12
            prev_year = year - 1
        had_postpaid_last_month = False
        try:
            prev_revenue = HostelRevenue.objects.get(title='rent', customer=customer_details.customer, year=prev_year, month=prev_month)
            if prev_revenue.payment_type == 'prepaid' and prev_revenue.prepaid_amount:
                previous_prepaid = prev_revenue.prepaid_amount
            elif prev_revenue.payment_type == 'postpaid' and prev_revenue.prepaid_amount:
                previous_postpaid = prev_revenue.prepaid_amount
                had_postpaid_last_month = True
        except HostelRevenue.DoesNotExist:
            had_postpaid_last_month = False
        # Adjust total based on previous month's prepaid/postpaid
        adjusted_total = total_amount - previous_prepaid + previous_postpaid
        # Stage 7: Validate postpaid consecutive restriction
        if had_postpaid_last_month and payment_type == 'postpaid':
            messages.error(request, "Customer cannot make postpaid payment this month as they had postpaid payment last month. Please pay the full amount including the previous postpaid amount.")
            return redirect(request.path)
        # Stage 8: Validate prepaid/postpaid/normal payment types
        if payment_type == 'prepaid':
            # Prepaid: collected must exceed adjusted total
            if collected_amount < adjusted_total:
                messages.error(request, f"For prepaid payment, collected amount must be greater than or equal to adjusted total rent amount (¥{adjusted_total}).")
                return redirect(request.path)
            expected_prepaid = collected_amount - adjusted_total
            if abs(prepaid_amount - expected_prepaid) > Decimal("0.01"):
                messages.error(request, f"Prepaid amount should be {expected_prepaid} (excess of collected amount over adjusted total rent).")
                return redirect(request.path)
        elif payment_type == 'postpaid':
            # Postpaid: collected must be less than adjusted total
            if collected_amount >= adjusted_total:
                messages.error(request, f"For postpaid payment, collected amount must be less than adjusted total rent amount (¥{adjusted_total}).")
                return redirect(request.path)
            expected_postpaid = adjusted_total - collected_amount
            if abs(prepaid_amount - expected_postpaid) > Decimal("0.01"):
                messages.error(request, f"Postpaid amount should be {expected_postpaid} (shortfall of adjusted total rent over collected amount).")
                return redirect(request.path)
        elif payment_type == '' and collected_amount == 0:
            # Normal payment: set collected to adjusted total
            collected_amount = adjusted_total
        elif payment_type == '' and abs(collected_amount - adjusted_total) > Decimal("0.01"):
            messages.error(request, f"For normal payment, collected amount must equal amount to collect (¥{adjusted_total}).")
            return redirect(request.path)
        # Stage 9: Create/update revenue record
        revenue, created = HostelRevenue.objects.get_or_create(
            title="rent", customer=customer_details.customer, year=year, month=month,
            defaults={"rent": base_rent, "rent_discount_percent": rent_discount_percent, "rent_after_discount": rent_after_discount, "internet": internet_fee, "utilities": utilities_fee, "total_amount": total_amount, "payment_type": payment_type, "collected_amount": collected_amount, "prepaid_amount": prepaid_amount if payment_type else None, "memo": memo, "created_by": request.user, "updated_by": request.user,}
        )
        if not created:
            messages.warning(request, "Rent payment for this month already exists.")
        else:
            customer = revenue.customer
            if customer and customer.email:
                try:
                    send_revenue_email(request, revenue, subject='Rent Payment Notification - TNA  Group Limited')
                except Exception as e:
                    print("EMAIL ERROR (view level):", e)
            messages.success(request, "Monthly rent payment recorded successfully.")
        return redirect("finance:revenues")
    can_edit_fees = request.user.has_perm('finance.change_hostelrevenue') or request.user.is_superuser
    if request.method == "GET":
        previous_prepaid = Decimal('0')
        previous_postpaid = Decimal('0')
    else:
        previous_prepaid = get_previous_prepaid_amount(customer_details.customer, year, month)
        previous_postpaid = Decimal('0')
        prev_month = month - 1
        prev_year = year
        if prev_month <= 0:
            prev_month = 12
            prev_year = year - 1
        try:
            prev_revenue = HostelRevenue.objects.get(title='rent', customer=customer_details.customer, year=prev_year, month=prev_month)
            if prev_revenue.payment_type == 'postpaid' and prev_revenue.prepaid_amount:
                previous_postpaid = prev_revenue.prepaid_amount
        except HostelRevenue.DoesNotExist:
            previous_postpaid = Decimal('0')
    had_postpaid_last_month = False
    registration_payment = HostelRevenue.objects.filter(title='registration_fee', customer=customer_details.customer).first()
    existing_rent_payments = HostelRevenue.objects.filter(title='rent', customer=customer_details.customer).order_by('year', 'month')
    last_rent_payment = existing_rent_payments.last() if existing_rent_payments.exists() else None
    return render(request, 'finance/monthly_rent.html', {
        'customer_details': customer_details,
        'can_edit_fees': can_edit_fees,
        'previous_prepaid_amount': previous_prepaid,
        'previous_postpaid_amount': previous_postpaid,
        'had_postpaid_last_month': had_postpaid_last_month,
        'registration_payment': registration_payment,
        'existing_rent_payments': existing_rent_payments,
        'last_rent_payment': last_rent_payment
    })


@login_required(login_url='/accounts/login/')
def get_prepaid_amount_for_month(request, customer_id):
    """AJAX endpoint to get previous month's prepaid/postpaid for a selected month"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            year = int(data.get('year'))
            month = int(data.get('month'))
            # Calculate previous month
            prev_month = month - 1
            prev_year = year
            if prev_month <= 0:
                prev_month = 12
                prev_year = year - 1
            # Get customer
            customer = get_object_or_404(Bed.objects.select_related('customer'), customer=customer_id).customer
            previous_prepaid = Decimal('0')
            previous_postpaid = Decimal('0')
            had_postpaid_last_month = False
            try:
                prev_revenue = HostelRevenue.objects.get(title='rent', customer=customer, year=prev_year, month=prev_month)
                if prev_revenue.payment_type == 'prepaid' and prev_revenue.prepaid_amount:
                    previous_prepaid = prev_revenue.prepaid_amount
                elif prev_revenue.payment_type == 'postpaid' and prev_revenue.prepaid_amount:
                    previous_postpaid = prev_revenue.prepaid_amount
                    had_postpaid_last_month = True
            except HostelRevenue.DoesNotExist:
                pass
            return JsonResponse({'success': True, 'previous_prepaid': float(previous_prepaid), 'previous_postpaid': float(previous_postpaid), 'had_postpaid_last_month': had_postpaid_last_month, 'previous_month': f"{prev_year}-{prev_month:02d}"})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required(login_url='/accounts/login/')
def validate_rent_month(request, customer_id):
    """AJAX endpoint to validate rent payment month selection"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            year = int(data.get('year'))
            month = int(data.get('month'))
            # Get customer
            customer = get_object_or_404(Bed.objects.select_related('customer'), customer=customer_id).customer
            # 1. Registration Fee Validation
            registration_payment = HostelRevenue.objects.filter(title='registration_fee', customer=customer).first()
            if not registration_payment:
                return JsonResponse({'success': False, 'error': 'Customer must pay registration fee before making rent payments.', 'error_type': 'registration_required'})
            # 2. Get all existing rent payments for this customer
            existing_rent_payments = HostelRevenue.objects.filter(title='rent', customer=customer).order_by('year', 'month')
            # 3. Check for duplicate payment
            duplicate_payment = existing_rent_payments.filter(year=year, month=month).first()
            if duplicate_payment:
                return JsonResponse({'success': False, 'error': f'Payment for {year}-{month:02d} already exists. Please select a different month.', 'error_type': 'duplicate_payment'})
            # 4. First rent payment validation
            if not existing_rent_payments.exists():
                reg_year = registration_payment.year
                reg_month = registration_payment.month
                if year != reg_year or month != reg_month:
                    return JsonResponse({'success': False, 'error': f'First rent payment must be in the registration month. Customer registered in {reg_year}-{reg_month:02d}. First rent payment should be for {reg_year}-{reg_month:02d}.', 'error_type': 'wrong_first_month', 'suggested_month': f'{reg_year}-{reg_month:02d}'})
            else:
                # Not first payment - validate sequential payment
                last_payment = existing_rent_payments.last()
                last_year = last_payment.year
                last_month = last_payment.month
                # Calculate expected next month
                expected_month = last_month + 1
                expected_year = last_year
                if expected_month > 12:
                    expected_month = 1
                    expected_year += 1
                # Check if trying to pay for a month before the last payment
                if year < last_year or (year == last_year and month < last_month):
                    return JsonResponse({'success': False, 'error': f'Cannot pay rent for a month before the last payment. Last payment was for {last_year}-{last_month:02d}.', 'error_type': 'backward_payment', 'last_payment': f'{last_year}-{last_month:02d}'})
                # Check if trying to skip months
                if year != expected_year or month != expected_month:
                    return JsonResponse({'success': False, 'error': f'Cannot skip months. Last payment was for {last_year}-{last_month:02d}. Next payment should be for {expected_year}-{expected_month:02d}.', 'error_type': 'skip_months', 'last_payment': f'{last_year}-{last_month:02d}', 'suggested_month': f'{expected_year}-{expected_month:02d}'})
            # If we get here, validation passed
            return JsonResponse({'success': True, 'message': 'Month selection is valid.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Validation error: {str(e)}', 'error_type': 'system_error'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required(login_url='/accounts/login/')
def registration_fee(request, customer_id):
    """
    Handle initial registration fee payment with deposit and initial fee components.
    Validates required hostel fees and manages discount/memo requirements.
    """
    customer_details = get_object_or_404(Bed.objects.select_related('unit', 'unit__hostel', 'customer'), customer=customer_id)
    # Validate required hostel fees are configured
    missing_fees = []
    if not customer_details.unit.hostel.deposit_fee or customer_details.unit.hostel.deposit_fee == 0:
        missing_fees.append("Deposit Fee")
    if not customer_details.unit.hostel.initial_fee or customer_details.unit.hostel.initial_fee == 0:
        missing_fees.append("Initial Fee")
    if missing_fees:
        messages.error(request, f"Please add {', '.join(missing_fees)} in hostel details. You cannot process without these fees.")
        return redirect('customer:customer_detail', customer_id)
    if request.method == "POST":
        # Parse registration month
        month_input = request.POST.get("reg_month")
        if not month_input:
            messages.error(request, "Payment month is required.")
            return redirect(request.path)
        try:
            year, month = map(int, month_input.split("-"))
        except ValueError:
            messages.error(request, "Invalid month format.")
            return redirect(request.path)
        # Parse numeric amounts
        try:
            deposit = Decimal(request.POST.get("deposit", "0"))
            deposit_discount = Decimal(request.POST.get("deposit_discount_percent", "0"))
            initial = Decimal(request.POST.get("initial_fee", "0"))
            initial_discount = Decimal(request.POST.get("initial_fee_discount_percent", "0"))
        except InvalidOperation:
            messages.error(request, "Invalid numeric values.")
            return redirect(request.path)
        # Calculate deposit and initial fee after discounts
        deposit_after = deposit * (Decimal(1) - deposit_discount / Decimal(100))
        initial_after = initial * (Decimal(1) - initial_discount / Decimal(100))
        total = deposit_after + initial_after
        # Validate memo requirement for discounted amounts
        memo = request.POST.get("memo", "").strip()
        if (deposit_discount > 0 or initial_discount > 0) and not memo:
            messages.error(request, "Memo is required when a discount is applied.")
            return redirect(request.path)
        # Create registration fee revenue record
        revenue, created = HostelRevenue.objects.get_or_create(
            title="registration_fee", customer=customer_details.customer, year=year, month=month,
            defaults={"deposit": deposit, "deposit_discount_percent": deposit_discount, "deposit_after_discount": deposit_after, "initial_fee": initial, "initial_fee_discount_percent": initial_discount, "initial_fee_after_discount": initial_after, "total_amount": total, "memo": memo, "created_by": request.user, "updated_by": request.user,}
        )
        if not created:
            messages.warning(request, "Registration fee for this month already exists.")
        else:
            customer = revenue.customer
            if customer and customer.email:
                try:
                    send_revenue_email(request, revenue, subject='Registration Fee Notification - TNA  Group Limited')
                except Exception as e:
                    print("EMAIL ERROR (view level):", e)
            messages.success(request, "Registration fee payment recorded successfully.")
        return redirect("finance:revenues")
    can_edit_fees = request.user.has_perm('finance.change_hostelrevenue') or request.user.is_superuser
    return render(request, 'finance/registration_fee.html', {'customer_details': customer_details, 'can_edit_fees': can_edit_fees})


@login_required(login_url='/accounts/login/')
def notification(request):
    """
    Rent defaulters dashboard - shows customers with unpaid rent months.
    Allows searching by customer name and downloading unpaid rent report to Excel.
    """
    search_name = request.GET.get('name', '').strip().lower()
    # Get all rent defaulters from helper function
    defaulters = get_rent_defaulters()
    # Filter by search name if provided
    if search_name:
        defaulters = [d for d in defaulters if search_name in d['customer'].name.lower()]
    # Handle Excel export
    if 'download' in request.GET:
        return export_unpaid_rent_to_excel(defaulters)
    return render(request, 'finance/notification.html', {'defaulters': defaulters, 'search_name': request.GET.get('name', ''), 'today': date.today()})


@login_required(login_url='/accounts/login/')
@permission_required(('finance.view_hostelexpense', 'finance.view_utilityexpense'), raise_exception=True)
def expenses(request):
    """
    Unified expenses dashboard combining hostel and utility expenses.
    Supports filtering by date, status, expense type, hostel, and Excel export.
    """
    # Parse filter parameters
    year_month = request.GET.get('year_month')
    status = request.GET.get('status')
    expense_type = request.GET.get('expense_type')
    hostel_filter = request.GET.get('hostel')
    export = request.GET.get('export')
    # Get base querysets
    hostel_expenses = HostelExpense.objects.select_related('hostel', 'created_by', 'updated_by', 'approved_by')
    utility_expenses = UtilityExpense.objects.select_related('hostel', 'paid_by', 'approved_by')
    # Default to current month if no filter provided
    if not year_month and not status and not hostel_filter and not export:
        current_date = date.today()
        year_month = current_date.strftime('%Y-%m')
    # Filter by year/month
    if year_month:
        try:
            filter_year, filter_month = map(int, year_month.split('-'))
            hostel_expenses = hostel_expenses.filter(purchased_date__year=filter_year, purchased_date__month=filter_month)
            utility_expenses = utility_expenses.filter(paid_date__year=filter_year, paid_date__month=filter_month)
        except (ValueError, TypeError):
            current_date = date.today()
            filter_year, filter_month = current_date.year, current_date.month
            hostel_expenses = hostel_expenses.filter(purchased_date__year=filter_year, purchased_date__month=filter_month)
            utility_expenses = utility_expenses.filter(paid_date__year=filter_year, paid_date__month=filter_month)
    # Filter by approval status
    if status in ['approved', 'pending', 'rejected']:
        hostel_expenses = hostel_expenses.filter(status=status)
        utility_expenses = utility_expenses.filter(approval_status=status.upper())
    # Filter by expense type (hostel vs utility)
    if expense_type == 'hostel':
        utility_expenses = utility_expenses.none()
    elif expense_type == 'utility':
        hostel_expenses = hostel_expenses.none()
    # Filter by hostel name
    if hostel_filter:
        hostel_expenses = hostel_expenses.filter(hostel__name__icontains=hostel_filter)
        utility_expenses = utility_expenses.filter(hostel__name__icontains=hostel_filter)
    # Combine hostel and utility expenses into unified list
    combined_expenses = []
    for expense in hostel_expenses:
        combined_expenses.append({'id': expense.id, 'type': 'hostel', 'transaction_code': expense.transaction_code, 'date': expense.purchased_date, 'date_display': expense.purchased_date.strftime('%b %d, %Y') if expense.purchased_date else 'N/A', 'hostel': expense.hostel.name if expense.hostel else "ALL", 'purchased_by': expense.purchased_by, 'memo': expense.memo, 'amount': expense.amount, 'status': expense.status, 'approved_by': expense.approved_by, 'created_by': expense.created_by, 'created_at': expense.created_at, 'updated_by': expense.updated_by, 'updated_at': expense.updated_at,})
    for expense in utility_expenses:
        # Build date display with utility billing period information
        billing_date = date(expense.billing_year, expense.billing_month, 1) if expense.billing_year and expense.billing_month else None
        date_display = f"{expense.paid_date.strftime('%b %d, %Y') if expense.paid_date else 'N/A'}<br><small class='text-muted mb-0'>(Bill of {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][expense.billing_month-1]} {expense.billing_year})</small>" if expense.paid_date and expense.billing_year and expense.billing_month else (expense.paid_date.strftime('%b %d, %Y') if expense.paid_date else 'N/A')
        combined_expenses.append({'id': expense.id, 'type': expense.expense_type, 'transaction_code': f"UTIL-{expense.id:06d}", 'date': billing_date, 'date_display': date_display, 'hostel': expense.hostel.name, 'purchased_by': expense.paid_by.first_name if expense.paid_by else "N/A", 'memo': expense.description, 'amount': expense.amount, 'status': expense.approval_status.lower(), 'approved_by': expense.approved_by, 'created_by': expense.created_by, 'created_at': expense.created_at, 'updated_by': expense.updated_by, 'updated_at': expense.updated_at,})
    # Sort by date descending
    combined_expenses.sort(key=lambda x: x['date'] if x['date'] else date.min, reverse=True)
    # Calculate totals
    total_amount = sum([expense['amount'] if expense['amount'] is not None else Decimal('0') for expense in combined_expenses], Decimal('0'))
    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(combined_expenses, 25)
    page_obj = paginator.get_page(page_number)
    expenses_page = page_obj.object_list
    page_total_amount = sum([expense['amount'] if expense['amount'] is not None else Decimal('0') for expense in expenses_page], Decimal('0'))
    # Build query string for pagination links (without page parameter)
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    query_string = query_params.urlencode()
    # Handle Excel export
    if export == 'excel':
        return export_expenses_to_excel(combined_expenses)
    # Get all hostels for filter dropdown
    from hostel.models import Hostel
    all_hostels = Hostel.objects.filter(status=True).order_by('name')
    # Format month display
    display_month = ""
    if year_month:
        try:
            filter_year, filter_month = map(int, year_month.split('-'))
            from datetime import datetime
            display_month = datetime(filter_year, filter_month, 1).strftime('%B %Y')
        except (ValueError, TypeError):
            display_month = "Current Month"
    return render(request, 'finance/expenses_dashboard.html', {
        'expenses': expenses_page,
        'year_month': year_month,
        'display_month': display_month,
        'status': status,
        'expense_type': expense_type,
        'hostel_filter': hostel_filter,
        'all_hostels': all_hostels,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_records': paginator.count,
        'total_amount': total_amount,
        'page_total_amount': page_total_amount,
        'query_string': query_string,
    })

@login_required(login_url='/accounts/login/')
@permission_required('finance.add_hostelexpense', raise_exception=True)
def hostel_expense_create(request):
    """Create a new hostel expense record"""
    if request.method == 'POST':
        form = HostelExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Expense created successfully.")
            return redirect('finance:expenses')
    else:
        form = HostelExpenseForm()
    return render(request, 'finance/hostel_expense_form.html', {'form': form})


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_hostelexpense', raise_exception=True)
def hostel_expense_edit(request, pk):
    """Edit hostel expense - prevent editing approved expenses"""
    expense = get_object_or_404(HostelExpense, pk=pk)
    if expense.status == 'approved':
        messages.warning(request, "Approved expenses cannot be edited.")
        return redirect('finance:expenses')
    if request.method == 'POST':
        form = HostelExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Expense updated successfully.")
            return redirect('finance:expenses')
    else:
        form = HostelExpenseForm(instance=expense)
    return render(request, 'finance/hostel_expense_form.html', {'form': form})


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda u: u.is_superuser)
def hostel_expense_detail(request, pk):
    """View and update hostel expense approval status"""
    expense = get_object_or_404(HostelExpense, pk=pk)
    if request.method == 'POST':
        if expense.status == 'approved':
            messages.warning(request, "Approved hostel expenses cannot have their status changed.")
            return redirect('finance:hostel_expense_detail', pk=expense.pk)
        new_status = request.POST.get('status')
        if new_status in dict(HostelExpense.STATUS_CHOICES):
            expense.status = new_status
            if new_status == 'approved':
                expense.updated_by = request.user
                expense.approved_by = request.user
            else:
                expense.approved_by = None
            expense.save()
            messages.success(request, "Status updated successfully.")
            return redirect('finance:expenses')
    return render(request, 'finance/hostel_expense_detail.html', {'expense': expense})


@login_required(login_url='/accounts/login/')
@permission_required('finance.add_utilityexpense', raise_exception=True)
def utility_expense_create(request):
    """Create a new utility expense record with file upload"""
    if request.method == 'POST':
        form = UtilityExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.paid_by = request.user
            expense.created_by = request.user
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Utility expense created successfully.")
            return redirect('finance:expenses')
    else:
        form = UtilityExpenseForm()
    return render(request, 'finance/utility_expense_form.html', {'form': form})


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_utilityexpense', raise_exception=True)
def utility_expense_edit(request, pk):
    """Edit utility expense - prevent editing approved expenses"""
    expense = get_object_or_404(UtilityExpense, pk=pk)
    if expense.approval_status == 'APPROVED':
        messages.warning(request, "Approved utility expenses cannot be edited.")
        return redirect('finance:expenses')
    if request.method == 'POST':
        form = UtilityExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Utility expense updated successfully.")
            return redirect('finance:expenses')
    else:
        form = UtilityExpenseForm(instance=expense)
    return render(request, 'finance/utility_expense_form.html', {'form': form})


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda u: u.is_superuser)
def utility_expense_detail(request, pk):
    """View and update utility expense approval status"""
    expense = get_object_or_404(UtilityExpense, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('approval_status')
        if new_status in dict(UtilityExpense.ApprovalStatus.choices):
            expense.approval_status = new_status
            if new_status == 'APPROVED':
                expense.approved_by = request.user
            else:
                expense.approved_by = None
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Status updated successfully.")
            return redirect('finance:expenses')
    return render(request, 'finance/utility_expense_detail.html', {'expense': expense})





@login_required(login_url='/accounts/login/')
def staff_expense_list(request):
    """List all staff expenses for the logged-in employee."""
    transaction_code = request.GET.get("transaction_code", "").strip().upper()
    from_date_str = request.GET.get("from_date")
    to_date_str = request.GET.get("to_date")
    status = request.GET.get("status")
    today = timezone.now().date()
    search_by_code = bool(transaction_code)
    search_ignores_dates = search_by_code or status in {"pending", "approved", "rejected"}

    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date() if from_date_str else today.replace(day=1)
    except ValueError:
        from_date = today.replace(day=1)
    try:
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date() if to_date_str else today
    except ValueError:
        to_date = today

    query = Q(employee=request.user)
    if search_by_code:
        query &= Q(transaction_code__icontains=transaction_code)
    if not search_ignores_dates:
        query &= Q(start_date__gte=from_date, start_date__lte=to_date)
    if status == "pending":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.PENDING)
    elif status == "approved":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.APPROVED)
    elif status == "rejected":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.REJECTED)

    expenses = StaffExpense.objects.select_related("approved_by").filter(query).order_by("-created_at")
    return render(request, "finance/staff_expense_list.html", {
        "expenses": expenses,
        "total_count": expenses.count(),
        "transaction_code": transaction_code,
        "search_by_code": search_by_code,
        "search_ignores_dates": search_ignores_dates,
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "status": status,
    })

@login_required(login_url='/accounts/login/')
def staff_expense_create(request):
    """Create a new staff expense request."""
    if request.method == "POST":
        form = StaffExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.employee = request.user
            expense.created_by = request.user
            expense.updated_by = request.user
            expense.approval_status = StaffExpense.ApprovalStatus.PENDING
            expense.save()
            messages.success(request, "Staff expense submitted successfully.")
            return redirect("finance:staff_expense_list")
    else:
        form = StaffExpenseForm()
    return render(request, "finance/staff_expense_form.html", {"form": form})


@login_required(login_url='/accounts/login/')
def staff_expense_edit(request, pk):
    """Edit a staff expense only while it is pending."""
    expense = get_object_or_404(StaffExpense, pk=pk, employee=request.user)
    if expense.approval_status != StaffExpense.ApprovalStatus.PENDING:
        messages.error(request, "This staff expense has already been processed and cannot be edited.")
        return redirect("finance:staff_expense_list")
    if request.method == "POST":
        form = StaffExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Staff expense updated successfully.")
            return redirect("finance:staff_expense_list")
    else:
        form = StaffExpenseForm(instance=expense)
    return render(request, "finance/staff_expense_form.html", {"form": form})


@login_required(login_url='/accounts/login/')
def staff_expense_dashboard(request):
    """Admin dashboard showing all staff expense requests with search and export."""
    can_view_staff_expenses = (
        request.user.is_superuser
        or request.user.has_perm("finance.view_staffexpense")
        or request.user.has_perm("finance.change_staffexpense")
    )
    if not can_view_staff_expenses:
        raise PermissionDenied

    employee_id = request.GET.get("employee", "").strip()
    transaction_code = request.GET.get("transaction_code", "").strip().upper()
    expense_type = request.GET.get("expense_type", "").strip().upper()
    from_date_str = request.GET.get("from_date")
    to_date_str = request.GET.get("to_date")
    status = request.GET.get("status")
    export = request.GET.get("export")
    today = timezone.now().date()
    User = get_user_model()
    employees = User.objects.filter(is_active=True).order_by("first_name", "last_name", "email")
    search_by_code = bool(transaction_code)
    search_ignores_dates = search_by_code or status in {"pending", "approved", "rejected"}

    if from_date_str:
        try:
            from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        except ValueError:
            from_date = today.replace(day=1)
    else:
        from_date = today.replace(day=1)
    if to_date_str:
        try:
            to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
        except ValueError:
            to_date = today
    else:
        to_date = today

    query = Q()
    if search_by_code:
        query &= Q(transaction_code__icontains=transaction_code)
    if not search_ignores_dates:
        query &= Q(start_date__gte=from_date, start_date__lte=to_date)
    if employee_id:
        try:
            query &= Q(employee_id=int(employee_id))
        except ValueError:
            pass
    valid_expense_types = {choice.value for choice in StaffExpense.ExpenseType}
    if expense_type in valid_expense_types:
        query &= Q(expense_type=expense_type)
    if status == "pending":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.PENDING)
    elif status == "approved":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.APPROVED)
    elif status == "rejected":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.REJECTED)

    expenses = (
        StaffExpense.objects.select_related("employee", "approved_by", "created_by", "updated_by")
        .filter(query)
        .order_by("-created_at")
    )

    total_count = expenses.count()
    overall_total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    query_params = request.GET.copy()
    if "export" in query_params:
        query_params.pop("export")
    if "page" in query_params:
        query_params.pop("page")
    query_string = query_params.urlencode()

    if export == "excel":
        if expenses.exists():
            return export_staff_expenses_to_excel(expenses)
        messages.warning(request, "No data available to export.")

    expenses_page = Paginator(expenses, 20).get_page(request.GET.get("page"))
    page_total_amount = expenses_page.object_list.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    context = {
        "expenses": expenses_page,
        "total_count": total_count,
        "page_total_amount": page_total_amount,
        "overall_total_amount": overall_total_amount,
        "employees": employees,
        "selected_employee": employee_id,
        "expense_types": StaffExpense.ExpenseType.choices,
        "selected_expense_type": expense_type,
        "transaction_code": transaction_code,
        "search_by_code": search_by_code,
        "search_ignores_dates": search_ignores_dates,
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "status": status,
        "query_string": query_string,
        "can_change_staff_expenses": (
            request.user.is_superuser
            or request.user.has_perm("finance.change_staffexpense")
        ),
    }
    return render(request, "finance/staff_expense_dashboard.html", context)


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_staffexpense', raise_exception=True)
def staff_expense_update_status(request, pk):
    """Display and update only the approval status of a staff expense."""
    expense = get_object_or_404(StaffExpense, pk=pk)

    if expense.created_by_id == request.user.id or expense.employee_id == request.user.id:
        messages.error(request, "You cannot approve or reject a staff expense that you created.")
        return redirect("finance:staff_expense_dashboard")

    if request.method == "POST" and expense.approval_status != StaffExpense.ApprovalStatus.PENDING:
        messages.info(request, "Approved or rejected staff expenses cannot be updated.")
        return redirect("finance:staff_expense_dashboard")

    if request.method == "POST":
        new_status = request.POST.get("approval_status")
        valid_statuses = set(StaffExpense.ApprovalStatus.values)
        status_memo = request.POST.get("status_memo", "").strip()

        if new_status not in valid_statuses:
            messages.error(request, "Please select a valid approval status.")
        elif new_status == expense.approval_status:
            messages.info(request, "The staff expense already has that status.")
        elif not status_memo:
            messages.error(request, "Please enter a memo for this status change.")
        else:
            expense.approval_status = new_status
            expense.status_memo = status_memo
            expense.updated_by = request.user
            if new_status == StaffExpense.ApprovalStatus.PENDING:
                expense.approved_by = None
            else:
                expense.approved_by = request.user
            expense.save(update_fields=["approval_status", "status_memo", "approved_by", "updated_by", "updated_at"])
            messages.success(request, "Staff expense status updated successfully.")
        return redirect("finance:staff_expense_dashboard")

    return render(request, "finance/staff_expense_status_form.html", {"expense": expense})

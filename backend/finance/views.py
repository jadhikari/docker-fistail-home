from django.shortcuts import render, get_object_or_404,redirect
from .models import HostelRevenue, HostelExpense, UtilityExpense
from hostel.models import Bed
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from .utils import send_revenue_email
from django.contrib.auth.decorators import login_required, permission_required
from django.utils import timezone
from django.db.models import Q
import openpyxl #type: ignore
from django.http import HttpResponse

from .finance_helpers.rent_defaulters import get_rent_defaulters
from datetime import date, datetime
from .forms import HostelExpenseForm, UtilityExpenseForm
from django.contrib.auth.decorators import login_required, user_passes_test

def export_revenues_to_excel(queryset):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Revenues"

    headers = [
        'Customer', 'Hostel', 'Unit', 'Bed',
        'Type', 'Year', 'Month',
        'Initial Fee', 'I. F. Discount (%)', 'I. F. A. D.',
        'Deposit', 'D. Discount (%)', 'D. A. D.',
        'Internet', 'Utilities', 'Rent', 'R. Discount (%)', 'R. A. D.',
        'Total'
    ]
    ws.append(headers)

    for rev in queryset:
        customer = getattr(rev, 'customer', None)
        bed = getattr(customer, 'bed_assignment', None) if customer else None
        unit = getattr(bed, 'unit', None) if bed else None
        hostel = getattr(unit, 'hostel', None) if unit else None

        ws.append([
            customer.name if customer else '',
            hostel.name if hostel else '',
            unit.room_num if unit else '',
            bed.bed_num if bed else '',
            rev.get_title_display(),
            rev.year,
            rev.month,
            rev.initial_fee or '',
            rev.initial_fee_discount_percent or '',
            rev.initial_fee_after_discount or '',
            rev.deposit or '',
            rev.deposit_discount_percent or '',
            rev.deposit_after_discount or '',
            rev.internet or '',
            rev.utilities or '',
            rev.rent or '',
            rev.rent_discount_percent or '',
            rev.rent_after_discount or '',
            rev.total_amount or '',
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename=\"revenues.xlsx\"'
    wb.save(response)
    return response


@login_required(login_url='/accounts/login/')
def revenues(request):
    name = request.GET.get('name')
    year = request.GET.get('year')
    month = request.GET.get('month')
    title = request.GET.get('title')

    today = timezone.now()
    default_year = today.year
    default_month = today.month

    query = Q()

    if name:
        query &= Q(customer__name__icontains=name) | Q(title__icontains=name)

    if title:
        query &= Q(title=title)

    try:
        selected_year = int(year)
    except (ValueError, TypeError):
        selected_year = default_year
    query &= Q(year=selected_year)

    try:
        selected_month = int(month)
    except (ValueError, TypeError):
        selected_month = default_month
    query &= Q(month=selected_month)

    revenues = HostelRevenue.objects.select_related('customer').filter(query).order_by('-id')

    # ✅ Only allow download if there are results
    if request.GET.get('download') == 'excel':
        if revenues.exists():
            return export_revenues_to_excel(revenues)
        else:
            messages.warning(request, "No data available to export.")

    if request.GET and not any([name, year, month, title]):
        messages.warning(request, "No filter parameters provided.")

    year_choices = HostelRevenue.objects.values_list('year', flat=True).distinct().order_by('-year')

    return render(request, 'finance/revenues_dashboard.html', {
        'revenues': revenues,
        'name': name,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_title': title,
        'year_choices': year_choices,
        'month_choices': [(i, i) for i in range(1, 13)],
        'title_choices': HostelRevenue.REVENUE_TYPE_CHOICES,
    })

@login_required(login_url='/accounts/login/')
def revenue_detail(request, pk):
    revenue = get_object_or_404(HostelRevenue, pk=pk)
    return render(request, 'finance/revenue_detail.html', {'revenue': revenue})


@login_required(login_url='/accounts/login/')
def monthly_rent(request, customer_id):
    customer_details = get_object_or_404(
        Bed.objects.select_related('unit', 'unit__hostel', 'customer'),
        customer=customer_id
    )

    # Validation: Check if required fees are set in bed details
    missing_fees = []
    if not customer_details.rent or customer_details.rent == 0:
        missing_fees.append("Base Rent")
    if not customer_details.internet_fee or customer_details.internet_fee == 0:
        missing_fees.append("Internet Fee")
    if not customer_details.utilities_fee or customer_details.utilities_fee == 0:
        missing_fees.append("Utilities Fee")
    
    if missing_fees:
        messages.error(request, f"Please add {', '.join(missing_fees)} in bed details. You cannot process without these fees.")
        return redirect('customer:customer_detail', customer_id)

    if request.method == "POST":
        month_input = request.POST.get("rent_month")
        if not month_input:
            messages.error(request, "Payment month is required.")
            return redirect(request.path)

        year, month = map(int, month_input.split("-"))

        try:
            base_rent = Decimal(request.POST.get("rent", "0"))
            internet_fee = Decimal(request.POST.get("internet", "0"))
            utilities_fee = Decimal(request.POST.get("utilities", "0"))
            rent_discount_percent = Decimal(request.POST.get("rent_discount_percent", "0"))
        except InvalidOperation:
            messages.error(request, "Invalid numeric values in the form.")
            return redirect(request.path)

        rent_after_discount = base_rent * (Decimal(1) - rent_discount_percent / Decimal(100))
        total_amount = rent_after_discount + internet_fee + utilities_fee

        memo = request.POST.get("memo", "").strip()

        if rent_discount_percent > 0 and not memo:
            messages.error(request, "Memo is required when a discount is applied.")
            return redirect(request.path)

        revenue, created = HostelRevenue.objects.get_or_create(
            title="rent",
            customer=customer_details.customer,
            year=year,
            month=month,
            defaults={
                "rent": base_rent,
                "rent_discount_percent": rent_discount_percent,
                "rent_after_discount": rent_after_discount,
                "internet": internet_fee,
                "utilities": utilities_fee,
                "total_amount": total_amount,
                "memo": memo,
                "created_by": request.user,
                "updated_by": request.user,
            }
        )

        if not created:
            messages.warning(request, "Rent payment for this month already exists.")
        else:
            customer = revenue.customer
            if customer and customer.email:
                send_revenue_email(request, revenue, subject='Rent Payment Notification - Fishtail')

            messages.success(request, "Monthly rent payment recorded successfully.")
        return redirect("finance:revenues")

    # Check user privileges for editing fees
    can_edit_fees = request.user.has_perm('finance.change_hostelrevenue') or request.user.is_superuser

    return render(request, 'finance/monthly_rent.html', {
        'customer_details': customer_details,
        'can_edit_fees': can_edit_fees
    })


@login_required(login_url='/accounts/login/')
def registration_fee(request, customer_id):
    customer_details = get_object_or_404(
        Bed.objects.select_related('unit', 'unit__hostel', 'customer'),
        customer=customer_id
    )

    # Validation: Check if required fees are set in hostel details
    missing_fees = []
    if not customer_details.unit.hostel.deposit_fee or customer_details.unit.hostel.deposit_fee == 0:
        missing_fees.append("Deposit Fee")
    if not customer_details.unit.hostel.initial_fee or customer_details.unit.hostel.initial_fee == 0:
        missing_fees.append("Initial Fee")
    
    if missing_fees:
        messages.error(request, f"Please add {', '.join(missing_fees)} in hostel details. You cannot process without these fees.")
        return redirect('customer:customer_detail', customer_id)

    if request.method == "POST":
        month_input = request.POST.get("reg_month")
        if not month_input:
            messages.error(request, "Payment month is required.")
            return redirect(request.path)

        try:
            year, month = map(int, month_input.split("-"))
        except ValueError:
            messages.error(request, "Invalid month format.")
            return redirect(request.path)

        try:
            deposit = Decimal(request.POST.get("deposit", "0"))
            deposit_discount = Decimal(request.POST.get("deposit_discount_percent", "0"))
            initial = Decimal(request.POST.get("initial_fee", "0"))
            initial_discount = Decimal(request.POST.get("initial_fee_discount_percent", "0"))
        except InvalidOperation:
            messages.error(request, "Invalid numeric values.")
            return redirect(request.path)

        deposit_after = deposit * (Decimal(1) - deposit_discount / Decimal(100))
        initial_after = initial * (Decimal(1) - initial_discount / Decimal(100))
        total = deposit_after + initial_after

        memo = request.POST.get("memo", "").strip()
        if (deposit_discount > 0 or initial_discount > 0) and not memo:
            messages.error(request, "Memo is required when a discount is applied.")
            return redirect(request.path)

        # Prevent duplicate
        revenue, created = HostelRevenue.objects.get_or_create(
            title="registration_fee",
            customer=customer_details.customer,
            year=year,
            month=month,
            defaults={
                "deposit": deposit,
                "deposit_discount_percent": deposit_discount,
                "deposit_after_discount": deposit_after,
                "initial_fee": initial,
                "initial_fee_discount_percent": initial_discount,
                "initial_fee_after_discount": initial_after,
                "total_amount": total,
                "memo": memo,
                "created_by": request.user,
                "updated_by": request.user,
            }
        )

        if not created:
            messages.warning(request, "Registration fee for this month already exists.")
        else:
            customer = revenue.customer
            if customer and customer.email:
                send_revenue_email(request, revenue, subject='Registration Fee Notification - Fishtail')

            messages.success(request, "Registration fee payment recorded successfully.")

        return redirect("finance:revenues")

    # Check user privileges for editing fees
    can_edit_fees = request.user.has_perm('finance.change_hostelrevenue') or request.user.is_superuser

    return render(request, 'finance/registration_fee.html', {
        'customer_details': customer_details,
        'can_edit_fees': can_edit_fees
    })


@login_required(login_url='/accounts/login/')
def notification(request):
    search_name = request.GET.get('name', '').strip().lower()
    defaulters = get_rent_defaulters()

    if search_name:
        defaulters = [
            d for d in defaulters
            if search_name in d['customer'].name.lower()
        ]

    # Handle Excel download
    if 'download' in request.GET:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = 'Unpaid Rent'

        # Header
        sheet.append(['Customer Name', 'Stay Type', 'Assigned Date', 'Released/End Date', 'Unpaid Months'])

        for entry in defaulters:
            unpaid_str = ", ".join(f"{y}-{m:02d}" for y, m in entry['unpaid_months'])
            sheet.append([
                entry['customer'].name,
                entry['type'].capitalize(),
                entry['assigned_date'],
                entry['end_date'],
                unpaid_str
            ])

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="unpaid_rent.xlsx"'
        workbook.save(response)
        return response

    return render(request, 'finance/notification.html', {
        'defaulters': defaulters,
        'search_name': request.GET.get('name', ''),
        'today': date.today()
        
    })


@login_required(login_url='/accounts/login/')
@permission_required(('finance.view_hostelexpense', 'finance.view_utilityexpense'), raise_exception=True)
def expenses(request):
    # Get filters from request
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    status = request.GET.get('status')
    expense_type = request.GET.get('expense_type')
    hostel_filter = request.GET.get('hostel')
    export = request.GET.get('export')

    # Get both types of expenses
    hostel_expenses = HostelExpense.objects.select_related('hostel', 'created_by', 'updated_by', 'approved_by')
    utility_expenses = UtilityExpense.objects.select_related('hostel', 'paid_by', 'approved_by')

    # If no filters are provided, show current month's expenses by default
    if not from_date and not to_date and not status and not hostel_filter and not export:
        current_date = date.today()
        from_date = current_date.replace(day=1).strftime('%Y-%m-%d')
        to_date = current_date.strftime('%Y-%m-%d')

    # Filter by date range (if specified)
    if from_date or to_date:
        
        # For hostel expenses: use purchased_date
        if from_date:
            hostel_expenses = hostel_expenses.filter(purchased_date__gte=from_date)
        if to_date:
            hostel_expenses = hostel_expenses.filter(purchased_date__lte=to_date)
        
        # For utility expenses: use billing_year and billing_month
        if from_date:
            from_datetime = datetime.strptime(from_date, '%Y-%m-%d')
            from_year = from_datetime.year
            from_month = from_datetime.month
            
            # Filter utility expenses where billing_year > from_year OR (billing_year = from_year AND billing_month >= from_month)
            utility_expenses = utility_expenses.filter(
                Q(billing_year__gt=from_year) | 
                Q(billing_year=from_year, billing_month__gte=from_month)
            )
        
        if to_date:
            to_datetime = datetime.strptime(to_date, '%Y-%m-%d')
            to_year = to_datetime.year
            to_month = to_datetime.month
            
            # Filter utility expenses where billing_year < to_year OR (billing_year = to_year AND billing_month <= to_month)
            utility_expenses = utility_expenses.filter(
                Q(billing_year__lt=to_year) | 
                Q(billing_year=to_year, billing_month__lte=to_month)
            )

    # Filter by status
    if status in ['approved', 'pending', 'rejected']:
        hostel_expenses = hostel_expenses.filter(status=status)
        utility_expenses = utility_expenses.filter(approval_status=status.upper())

    # Filter by expense type
    if expense_type == 'hostel':
        utility_expenses = utility_expenses.none()
    elif expense_type == 'utility':
        hostel_expenses = hostel_expenses.none()

    # Filter by hostel
    if hostel_filter:
        hostel_expenses = hostel_expenses.filter(hostel__name__icontains=hostel_filter)
        utility_expenses = utility_expenses.filter(hostel__name__icontains=hostel_filter)

    # Combine and sort expenses
    combined_expenses = []
    
    # Add hostel expenses
    print(f"DEBUG: Found {hostel_expenses.count()} hostel expenses")
    for expense in hostel_expenses:
        print(f"DEBUG: Processing hostel expense ID {expense.id}")
        combined_expenses.append({
            'id': expense.id,
            'type': 'hostel',
            'transaction_code': expense.transaction_code,
            'date': expense.purchased_date,
            'date_display': expense.purchased_date.strftime('%b %d, %Y') if expense.purchased_date else 'N/A',
            'hostel': expense.hostel.name if expense.hostel else "ALL",
            'purchased_by': expense.purchased_by,
            'memo': expense.memo,
            'bill_url': expense.bill_url,
            'amount': expense.amount_total,
            'status': expense.status,
            'approved_by': expense.approved_by,
            'created_by': expense.created_by,
            'created_at': expense.created_at,
            'updated_by': expense.updated_by,
            'updated_at': expense.updated_at,
        })
    
    # Add utility expenses
    print(f"DEBUG: Found {utility_expenses.count()} utility expenses")
    for expense in utility_expenses:
        print(f"DEBUG: Processing utility expense ID {expense.id}")
        # Create a date object for sorting (first day of billing month)
        billing_date = date(expense.billing_year, expense.billing_month, 1) if expense.billing_year and expense.billing_month else None
        
        combined_expenses.append({
            'id': expense.id,
            'type': expense.expense_type,
            'transaction_code': f"UTIL-{expense.id:06d}",
            'date': billing_date,  # For sorting
            'date_display': f"{expense.billing_year}-{expense.billing_month:02d}" if expense.billing_year and expense.billing_month else 'N/A',
            'hostel': expense.hostel.name,
            'purchased_by': expense.paid_by.first_name if expense.paid_by else "N/A",
            'memo': expense.description,
            'bill_url': expense.receipt.url if expense.receipt else None,
            'amount': expense.amount,
            'status': expense.approval_status.lower(),
            'approved_by': expense.approved_by,
            'created_by': expense.created_by,
            'created_at': expense.created_at,
            'updated_by': expense.updated_by,
            'updated_at': expense.updated_at,
        })

    # Sort by date (newest first)
    combined_expenses.sort(key=lambda x: x['date'] if x['date'] else date.min, reverse=True)
    print(f"DEBUG: Total combined expenses: {len(combined_expenses)}")

    # Export to Excel
    if export == 'excel':
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "All Expenses"

        ws.append([
            "Type", "ID", "Date", "Hostel", "Purchased By", "Approved By", "Amount", "Status", "Memo",
            "Created By", "Created At", "Updated By", "Updated At"
        ])

        for e in combined_expenses:
            approved_name = "-"
            if e['approved_by']:
                approved_name = e['approved_by'].first_name or e['approved_by'].email

            ws.append([
                e['type'].title(),
                e['transaction_code'],
                e['date_display'],
                e['hostel'],
                e['purchased_by'],
                approved_name,
                float(e['amount']),
                e['status'],
                e['memo'] or "-",
                str(e['created_by']) if e['created_by'] else "-",
                e['created_at'].strftime('%Y-%m-%d %H:%M:%S') if e['created_at'] else "-",
                str(e['updated_by']) if e['updated_by'] else "-",
                e['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if e['updated_at'] else "-",
            ])

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=all_expenses.xlsx'
        wb.save(response)
        return response

    # Get all hostels for the filter dropdown
    from hostel.models import Hostel
    all_hostels = Hostel.objects.all().order_by('name')
    print(combined_expenses)
    return render(request, 'finance/expenses_dashboard.html', {
        'expenses': combined_expenses,
        'from_date': from_date,
        'to_date': to_date,
        'status': status,
        'expense_type': expense_type,
        'hostel_filter': hostel_filter,
        'all_hostels': all_hostels
    })

@login_required(login_url='/accounts/login/')
@permission_required('finance.add_hostelexpense', raise_exception=True)
def hostel_expense_create(request):
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
    expense = get_object_or_404(HostelExpense, pk=pk)

    if request.method == 'POST':
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


# Utility Expense Views
@login_required(login_url='/accounts/login/')
@permission_required('finance.add_utilityexpense', raise_exception=True)
def utility_expense_create(request):
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

from django.shortcuts import render, get_object_or_404,redirect
from .models import HostelRevenue, HostelExpense
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
from datetime import date
from .forms import HostelExpenseForm
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

    return render(request, 'finance/monthly_rent.html', {'customer_details': customer_details})


@login_required(login_url='/accounts/login/')
def registration_fee(request, customer_id):
    customer_details = get_object_or_404(
        Bed.objects.select_related('unit', 'unit__hostel', 'customer'),
        customer=customer_id
    )

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

    return render(request, 'finance/registration_fee.html', {'customer_details': customer_details})


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


from django.utils import timezone
from datetime import datetime

@login_required(login_url='/accounts/login/')
@permission_required('finance.view_hostelexpense', raise_exception=True)
def expenses(request):
    expenses_qs = HostelExpense.objects.select_related('hostel').order_by('-purchased_date')

    # Get filters from request
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    status = request.GET.get('status')
    export = request.GET.get('export')

    # If no filters are provided, default to current month
    if not from_date and not to_date and not status and not export:
        today = timezone.now().date()
        first_day = today.replace(day=1)
        expenses_qs = expenses_qs.filter(purchased_date__gte=first_day, purchased_date__lte=today)
        from_date = first_day.strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')

    # Filter by date range (if specified)
    if from_date:
        expenses_qs = expenses_qs.filter(purchased_date__gte=from_date)
    if to_date:
        expenses_qs = expenses_qs.filter(purchased_date__lte=to_date)

    # Filter by status
    if status in ['approved', 'pending', 'rejected']:
        expenses_qs = expenses_qs.filter(status=status)

    # Export to Excel
    if export == 'excel':
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Hostel Expenses"

        ws.append([
            "ID", "Date", "Hostel", "Purchased By", "Approved By", "Before tax","Tax","Amount", "Status", "Memo",
            "Created By", "Created At", "Updated By", "Updated At"
        ])

        for e in expenses_qs:
            ws.append([
                e.transaction_code,
                e.purchased_date.strftime('%Y-%m-%d'),
                e.hostel.name if e.hostel else "ALL",
                e.purchased_by,
                e.approved_by if e.approved_by else "-",
                float(e.amount_before_tax),
                float(e.amount_tax),
                float(e.amount_total),
                e.status,
                e.memo,
                str(e.created_by) if e.created_by else "-",
                e.created_at.strftime('%Y-%m-%d %H:%M:%S') if e.created_at else "-",
                str(e.updated_by) if e.updated_by else "-",
                e.updated_at.strftime('%Y-%m-%d %H:%M:%S') if e.updated_at else "-",
            ])

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=expenses.xlsx'
        wb.save(response)
        return response

    return render(request, 'finance/expenses_dashboard.html', {
        'expenses': expenses_qs,
        'from_date': from_date,
        'to_date': to_date,
        'status': status
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
                user = request.user
                expense.updated_by = request.user
                if user.first_name:
                    expense.approved_by = user.first_name
                else:
                    expense.approved_by = user.email
            else:
                expense.approved_by = None
            expense.save()
            messages.success(request, "Status updated successfully.")
            return redirect('finance:expenses')

    return render(request, 'finance/hostel_expense_detail.html', {'expense': expense})

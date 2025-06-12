from django.shortcuts import render, get_object_or_404,redirect
from .models import Revenue
from hostel.models import Bed
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from .utils import send_revenue_email
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
import openpyxl #type: ignore
from django.http import HttpResponse

from .finance_helpers.rent_defaulters import get_rent_defaulters
from datetime import date


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

    revenues = Revenue.objects.select_related('customer').filter(query).order_by('-id')

    # ✅ Only allow download if there are results
    if request.GET.get('download') == 'excel':
        if revenues.exists():
            return export_revenues_to_excel(revenues)
        else:
            messages.warning(request, "No data available to export.")

    if request.GET and not any([name, year, month, title]):
        messages.warning(request, "No filter parameters provided.")

    year_choices = Revenue.objects.values_list('year', flat=True).distinct().order_by('-year')

    return render(request, 'finance/revenues_dashboard.html', {
        'revenues': revenues,
        'name': name,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_title': title,
        'year_choices': year_choices,
        'month_choices': [(i, i) for i in range(1, 13)],
        'title_choices': Revenue.REVENUE_TYPE_CHOICES,
    })

@login_required(login_url='/accounts/login/')
def revenue_detail(request, pk):
    revenue = get_object_or_404(Revenue, pk=pk)
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

        revenue, created = Revenue.objects.get_or_create(
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
        revenue, created = Revenue.objects.get_or_create(
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
def expenses(request):
    return render(request, 'finance/expenses_dashboard.html')

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
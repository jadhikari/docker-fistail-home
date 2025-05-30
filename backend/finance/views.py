from django.shortcuts import render, get_object_or_404,redirect
from .models import Revenue
from customer.models import Customer
from hostel.models import Bed
from .forms import RevenueForm
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from .utils import send_revenue_email



def revenues(request):
    query = request.GET.get('q')
    revenues = Revenue.objects.select_related('customer').order_by('-id')

    if query:
        revenues = revenues.filter(customer__name__icontains=query)
    # print(revenues.internet)
    return render(request, 'finance/revenues_dashboard.html', {
        'revenues': revenues,
        'q': query,
    })

def revenue_detail(request, pk):
    revenue = get_object_or_404(Revenue, pk=pk)
    return render(request, 'finance/revenue_detail.html', {'revenue': revenue})


def expenses(request):
    return render(request, 'finance/expenses_dashboard.html')


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
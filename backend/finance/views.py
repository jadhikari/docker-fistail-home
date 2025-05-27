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

def revenue_add(request):
    if request.method == 'POST':
        form = RevenueForm(request.POST)
        if form.is_valid():
            revenue = form.save(commit=False)
            revenue.created_by = request.user
            revenue.updated_by = request.user
            revenue.save()
            # ✅ START: Email sending block
            customer = revenue.customer
            if customer and customer.email:
                subject = 'Payment Notification From Fishtail'
                from_email = 'no-reply@yourdomain.com'
                to_email = customer.email

                # Build customer link
                customer_url = request.build_absolute_uri(
                    reverse('customer:customer_detail', args=[customer.id])
                )

                html_content = render_to_string('email/revenue_email.html', {
                    'revenue': revenue,
                    'customer_url': customer_url,
                })
                text_content = f'Dear {customer.name}, your revenue record has been added.'

                msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
                msg.attach_alternative(html_content, "text/html")
                msg.send()

            return redirect('finance:revenues')
    else:
        form = RevenueForm()

    return render(request, 'finance/revenue_add.html', {'form': form})


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
                subject = 'Rent Payment Notification - Fishtail'
                from_email = 'no-reply@yourdomain.com'
                to_email = customer.email

                customer_url = request.build_absolute_uri(
                    reverse('customer:customer_detail', args=[customer.id])
                )

                html_content = render_to_string('email/revenue_email.html', {
                    'revenue': revenue,
                    'customer_url': customer_url,
                })
                text_content = f"Dear {customer.name}, your rent payment for {month}/{year} has been recorded."

                msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
                msg.attach_alternative(html_content, "text/html")
                msg.send()

            messages.success(request, "Monthly rent payment recorded successfully.")
        return redirect("finance:revenues")

    return render(request, 'finance/monthly_rent.html', {'customer_details': customer_details})
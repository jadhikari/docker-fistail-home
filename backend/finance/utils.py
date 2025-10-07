from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from decimal import Decimal

def send_revenue_email(request, revenue, subject):
    customer = revenue.customer
    if customer and customer.email:
        from_email = 'no-reply@yourdomain.com'
        to_email = customer.email

        customer_url = request.build_absolute_uri(
            reverse('customer:customer_detail', args=[customer.id])
        )

        # Get previous month's prepaid/postpaid balance (only from immediate previous month)
        previous_prepaid = Decimal('0')
        previous_postpaid = Decimal('0')
        previous_month_display = None
        adjusted_amount_to_pay = None
        
        if revenue.title == 'rent':
            # Calculate previous month
            prev_month = revenue.month - 1
            prev_year = revenue.year
            if prev_month <= 0:
                prev_month = 12
                prev_year = revenue.year - 1
            
            previous_month_display = f"{prev_year}/{prev_month:02d}"
            
            try:
                from finance.models import HostelRevenue
                prev_revenue = HostelRevenue.objects.get(
                    title='rent',
                    customer=customer,
                    year=prev_year,
                    month=prev_month
                )
                # Get prepaid or postpaid amount from previous month only
                if prev_revenue.payment_type == 'prepaid' and prev_revenue.prepaid_amount:
                    previous_prepaid = prev_revenue.prepaid_amount
                    # Calculate adjusted amount (current total - previous prepaid)
                    adjusted_amount_to_pay = revenue.total_amount - previous_prepaid
                elif prev_revenue.payment_type == 'postpaid' and prev_revenue.prepaid_amount:
                    previous_postpaid = prev_revenue.prepaid_amount
                    # Calculate adjusted amount (current total + previous postpaid)
                    adjusted_amount_to_pay = revenue.total_amount + previous_postpaid
            except:
                pass

        html_content = render_to_string('email/revenue_email.html', {
            'revenue': revenue,
            'customer_url': customer_url,
            'previous_prepaid': previous_prepaid,
            'previous_postpaid': previous_postpaid,
            'previous_month_display': previous_month_display,
            'adjusted_amount_to_pay': adjusted_amount_to_pay,
        })
        text_content = f"Dear {customer.name}, your {revenue.get_title_display()} for {revenue.month}/{revenue.year} has been recorded."

        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()

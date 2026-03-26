from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from decimal import Decimal
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_revenue_email(request, revenue, subject):
    try:
        customer = revenue.customer

        if not (customer and customer.email):
            return  # nothing to send

        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = customer.email

        customer_url = request.build_absolute_uri(
            reverse('customer:customer_detail', args=[customer.id])
        )

        previous_prepaid = Decimal('0')
        previous_postpaid = Decimal('0')
        previous_month_display = None
        adjusted_amount_to_pay = None

        if revenue.title == 'rent':
            prev_month = revenue.month - 1
            prev_year = revenue.year

            if prev_month <= 0:
                prev_month = 12
                prev_year -= 1

            previous_month_display = f"{prev_year}/{prev_month:02d}"

            try:
                from finance.models import HostelRevenue

                prev_revenue = HostelRevenue.objects.get(
                    title='rent',
                    customer=customer,
                    year=prev_year,
                    month=prev_month
                )

                if prev_revenue.payment_type == 'prepaid' and prev_revenue.prepaid_amount:
                    previous_prepaid = prev_revenue.prepaid_amount
                    adjusted_amount_to_pay = revenue.total_amount - previous_prepaid

                elif prev_revenue.payment_type == 'postpaid' and prev_revenue.prepaid_amount:
                    previous_postpaid = prev_revenue.prepaid_amount
                    adjusted_amount_to_pay = revenue.total_amount + previous_postpaid

            except Exception as e:
                logger.warning(f"Previous month fetch failed: {e}")

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

        # 🔥 Try sending email
        msg.send(fail_silently=False)

    except Exception as e:
        # ✅ DO NOT crash app — just log and continue
        logger.error(f"Email sending failed: {e}", exc_info=True)
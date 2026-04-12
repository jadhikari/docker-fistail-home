from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from hostel.models import Hostel, Bed
import logging

logger = logging.getLogger(__name__)


def dashboard(request):
    hostels = Hostel.objects.all()

    if request.method == 'POST':
        hostel_value = request.POST.get('hostel')
        subject = request.POST.get('subject')
        body = request.POST.get('body')

        # ✅ Get active customers via Bed
        beds = Bed.objects.filter(
            customer__isnull=False,
            customer__status=True
        )

        if hostel_value != 'all':
            beds = beds.filter(unit__hostel_id=hostel_value)

        customers = beds.select_related('customer').values_list('customer', flat=False)

        emails_sent = 0

        for bed in beds.select_related('customer'):
            customer = bed.customer

            if not customer or not customer.email:
                continue

            try:
                from_email = settings.DEFAULT_FROM_EMAIL
                to_email = customer.email

                # ✅ HTML template (optional but recommended)
                html_content = render_to_string('email/send_mail.html', {
                    'customer': customer,
                    'body': body,
                })

                text_content = body

                msg = EmailMultiAlternatives(
                    subject,
                    text_content,
                    from_email,
                    [to_email]
                )

                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=False)

                emails_sent += 1

            except Exception as e:
                logger.error(f"Failed to send email to {customer.email}: {e}", exc_info=True)

        # ✅ UI Messages (short & clean)
        if emails_sent > 0:
            messages.success(request, f"✅ Email sent to {emails_sent} users.")
        else:
            messages.error(request, "❌ No emails sent. Check configuration.")

        return redirect('send_mail:dashboard')

    return render(request, 'send_mail/dashboard.html', {
        'hostels': hostels
    })
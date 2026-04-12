from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string, TemplateDoesNotExist
from hostel.models import Hostel, Bed
import logging
import re

logger = logging.getLogger(__name__)


def dashboard(request):
    hostels = Hostel.objects.all()

    if request.method == 'POST':
        hostel_value = request.POST.get('hostel')
        subject = request.POST.get('subject')
        body = request.POST.get('body')  # HTML from editor

        # ✅ Get active customers
        beds = Bed.objects.filter(
            customer__isnull=False,
            customer__status=True
        )

        # ✅ Filter by hostel
        if hostel_value != 'all':
            beds = beds.filter(unit__hostel_id=hostel_value)

        # ✅ Collect emails
        emails = list(
            beds.select_related('customer')
                .values_list('customer__email', flat=True)
                .distinct()
        )

        emails = [email for email in emails if email]

        if not emails:
            messages.error(request, "❌ No valid emails found.")
            return redirect('send_mail:dashboard')

        try:
            from_email = settings.DEFAULT_FROM_EMAIL

            # ✅ Convert HTML → clean plain text
            plain_text = re.sub('<br\\s*/?>', '\n', body)
            plain_text = re.sub('</p>', '\n\n', plain_text)
            plain_text = re.sub('<[^<]+?>', '', plain_text)

            # ✅ Create email
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_text,   # ✅ plain text version
                from_email=from_email,
                to=[from_email],
                bcc=emails
            )

            # ✅ Attach HTML (this is what users see)
            try:
                html_content = render_to_string('email/send_mail.html', {
                    'body': body,
                })
            except TemplateDoesNotExist:
                html_content = body  # fallback

            msg.attach_alternative(html_content, "text/html")

            # ✅ Send
            msg.send(fail_silently=False)

            messages.success(request, f"✅ Email sent to {len(emails)} users.")

        except Exception as e:
            logger.error(f"Bulk email failed: {e}", exc_info=True)

            error_msg = str(e)

            if "Username and Password not accepted" in error_msg:
                messages.error(request, "❌ Invalid email credentials.")
            elif "timed out" in error_msg:
                messages.error(request, "❌ Email server timeout. Try again.")
            else:
                messages.error(request, "❌ Failed to send emails.")

        return redirect('send_mail:dashboard')

    return render(request, 'send_mail/dashboard.html', {
        'hostels': hostels
    })
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

def send_revenue_email(request, revenue, subject):
    customer = revenue.customer
    if customer and customer.email:
        from_email = 'no-reply@yourdomain.com'
        to_email = customer.email

        customer_url = request.build_absolute_uri(
            reverse('customer:customer_detail', args=[customer.id])
        )

        html_content = render_to_string('email/revenue_email.html', {
            'revenue': revenue,
            'customer_url': customer_url,
        })
        text_content = f"Dear {customer.name}, your {revenue.get_title_display()} for {revenue.month}/{revenue.year} has been recorded."

        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()

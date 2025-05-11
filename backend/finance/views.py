from django.shortcuts import render, get_object_or_404,redirect
from .models import Revenue
from .forms import RevenueForm
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


def revenues(request):
    query = request.GET.get('q')
    revenues = Revenue.objects.select_related('customer').order_by('-year', '-month')

    if query:
        revenues = revenues.filter(customer__name__icontains=query)

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
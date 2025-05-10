from django.shortcuts import render, get_object_or_404,redirect
from .models import Revenue
from .forms import RevenueForm


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
            return redirect('finance:revenues')
    else:
        form = RevenueForm()

    return render(request, 'finance/revenue_add.html', {'form': form})


def expenses(request):
    return render(request, 'finance/expenses_dashboard.html')
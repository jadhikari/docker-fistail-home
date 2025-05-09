from django.shortcuts import render

def revenues(request):
    return render(request, 'finance/revenues_dashboard.html')

def expenses(request):
    return render(request, 'finance/expenses_dashboard.html')
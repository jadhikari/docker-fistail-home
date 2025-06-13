from datetime import date
from django.utils.timezone import now
from finance.models import HostelRevenue
from hostel.models import Bed, BedAssignmentHistory

def get_month_range(start_date, end_date):
    months = []
    current = date(start_date.year, start_date.month, 1)
    end = date(end_date.year, end_date.month, 1)
    while current <= end:
        months.append((current.year, current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months

def get_rent_defaulters():
    defaulters = []

    # Customers currently assigned to a bed
    for bed in Bed.objects.select_related('customer').filter(customer__isnull=False):
        customer = bed.customer
        if not customer.status:
            continue
        assigned_date = bed.assigned_date
        end_date = now().date()
        all_months = get_month_range(assigned_date, end_date)
        paid_months = HostelRevenue.objects.filter(
            customer=customer,
            title='rent'
        ).values_list('year', 'month')
        unpaid_months = [m for m in all_months if m not in paid_months]
        if unpaid_months:
            defaulters.append({
                'customer': customer,
                'type': 'current',
                'assigned_date': assigned_date,
                'end_date': end_date,
                'unpaid_months': unpaid_months
            })

    # Customers who already left
    for history in BedAssignmentHistory.objects.select_related('customer'):
        customer = history.customer
        assigned_date = history.assigned_date
        released_date = history.released_date
        all_months = get_month_range(assigned_date, released_date)
        paid_months = HostelRevenue.objects.filter(
            customer=customer,
            title='rent'
        ).values_list('year', 'month')
        unpaid_months = [m for m in all_months if m not in paid_months]
        if unpaid_months:
            defaulters.append({
                'customer': customer,
                'type': 'left',
                'assigned_date': assigned_date,
                'end_date': released_date,
                'unpaid_months': unpaid_months
            })

    return defaulters

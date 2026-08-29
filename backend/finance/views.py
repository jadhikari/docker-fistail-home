from django.contrib.auth import get_user_model
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.utils import timezone
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from datetime import date, datetime, timedelta
from calendar import monthrange
from decimal import Decimal, InvalidOperation
import json
from .models import (HostelRevenue, HostelExpense, UtilityExpense, StaffExpense, ThirdPartyServiceRecord,
                     OfficeExpense, OfficeBankAccount, OfficeCreditCard, CreditCardSettlement)
from .forms import (HostelExpenseForm, UtilityExpenseForm, StaffExpenseForm, AdFeeReceiptForm,
                    ThirdPartyServiceRecordCreateForm, ThirdPartyServiceRecordUpdateForm,
                    ThirdPartyServiceRemittanceForm, OfficeExpenseForm,
                    CreditCardSettlementForm, OfficeBankAccountForm, OfficeCreditCardForm)
from .utils import send_revenue_email
from .excel_exports import (
    export_revenues_to_excel,
    export_expenses_to_excel,
    export_staff_expenses_to_excel,
    export_pending_ad_fees_to_excel,
    export_real_estate_revenue_to_excel,
    export_unpaid_rent_to_excel,
    export_third_party_services_to_excel,
    export_office_expenses_to_excel,
    export_card_settlements_to_excel,
    export_cash_flow_to_excel,
)
from .finance_helpers.rent_defaulters import get_rent_defaulters
from hostel.models import Bed, Hostel
from customer.models import Customer
from targets.models import RentalContract


def _cash_flow_entries(start_date, end_date):
    """Return normalized cash movements for the requested inclusive period."""
    entries = []

    def local_date(value):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()

    def add_entry(entry_date, source, category, reference, description, inflow=Decimal("0"), outflow=Decimal("0")):
        inflow = inflow or Decimal("0")
        outflow = outflow or Decimal("0")
        if inflow == 0 and outflow == 0:
            return
        entries.append({
            "date": entry_date,
            "source": source,
            "category": category,
            "reference": reference,
            "description": description,
            "inflow": inflow,
            "outflow": outflow,
        })

    hostel_revenues = HostelRevenue.objects.select_related("customer").filter(
        created_at__date__range=(start_date, end_date),
    )
    for revenue in hostel_revenues:
        revenue_date = local_date(revenue.created_at)
        revenue_amount = (
            revenue.total_amount
            if revenue.title == 'registration_fee'
            else revenue.collected_amount
        )
        add_entry(
            revenue_date, "Hostel Revenue", revenue.get_title_display(),
            f"HR-{revenue.pk}", str(revenue.customer), inflow=revenue_amount,
        )

    contracts = RentalContract.objects.filter(contract_date__range=(start_date, end_date))
    for contract in contracts:
        add_entry(
            contract.contract_date, "Real Estate Revenue", "Agent Fee",
            f"RC-{contract.pk}", contract.customer_name, inflow=contract.agent_fee,
        )
    confirmed_ad_fees = RentalContract.objects.filter(
        ad_fee_confirmed_at__isnull=False,
        ad_fee_received_date__range=(start_date, end_date),
    )
    for contract in confirmed_ad_fees:
        add_entry(
            contract.ad_fee_received_date, "Real Estate Revenue", "AD Fee",
            f"RC-{contract.pk}", contract.customer_name,
            inflow=contract.ad_fee_received_amount,
        )

    services = ThirdPartyServiceRecord.objects.filter(collected_date__range=(start_date, end_date))
    for service in services:
        add_entry(
            service.collected_date, "Third-party Service", service.get_service_type_display(),
            service.transaction_code, service.applicant_name, inflow=service.collected_amount,
        )
    remittances = ThirdPartyServiceRecord.objects.filter(
        remitted_date__range=(start_date, end_date), remitted_amount__gt=0,
    )
    for service in remittances:
        add_entry(
            service.remitted_date, "Third-party Service", f"{service.get_service_type_display()} Remittance",
            service.transaction_code, service.company_name, outflow=service.remitted_amount,
        )

    for expense in HostelExpense.objects.filter(
        status="approved", purchased_date__range=(start_date, end_date),
    ):
        add_entry(
            expense.purchased_date, "Hostel Expense", "Hostel Expense",
            expense.transaction_code, expense.memo, outflow=expense.amount,
        )
    for expense in UtilityExpense.objects.select_related("hostel").filter(
        approval_status=UtilityExpense.ApprovalStatus.APPROVED,
        paid_date__range=(start_date, end_date),
    ):
        add_entry(
            expense.paid_date, "Utility Expense", expense.get_expense_type_display(),
            f"UTIL-{expense.pk:06d}", str(expense.hostel), outflow=expense.amount,
        )
    for expense in StaffExpense.objects.filter(
        approval_status=StaffExpense.ApprovalStatus.APPROVED,
        updated_at__date__range=(start_date, end_date),
    ):
        add_entry(
            local_date(expense.updated_at), "Staff Expense", expense.get_expense_type_display(),
            expense.transaction_code, expense.memo, outflow=expense.amount,
        )
    # Credit-card purchases are recognized as expenses when entered, but they do
    # not move money out of a bank account at that point.  Their cash movement is
    # recorded once, below, when the card bill is actually paid.
    for expense in OfficeExpense.objects.exclude(
        payment_mode=OfficeExpense.PaymentMode.CREDIT_CARD,
    ).filter(
        approval_status=OfficeExpense.ApprovalStatus.APPROVED,
        updated_at__date__range=(start_date, end_date),
    ):
        amount_field = "inflow" if expense.transaction_kind == OfficeExpense.TransactionKind.REFUND else "outflow"
        add_entry(
            local_date(expense.updated_at), "Office Expense", expense.get_category_display(),
            expense.transaction_code, expense.description, **{amount_field: expense.amount},
        )

    for settlement in CreditCardSettlement.objects.select_related(
        "credit_card", "bank_account",
    ).filter(
        approval_status=CreditCardSettlement.ApprovalStatus.APPROVED,
        settlement_date__range=(start_date, end_date),
    ):
        add_entry(
            settlement.settlement_date,
            "Credit-card Bill Payment",
            "Card bill settlement",
            settlement.transaction_code,
            f"{settlement.credit_card} paid from {settlement.bank_account}",
            outflow=settlement.amount,
        )

    entries.sort(key=lambda item: (item["date"], item["source"], item["reference"]))
    running_balance = Decimal("0")
    for entry in entries:
        running_balance += entry["inflow"] - entry["outflow"]
        entry["balance"] = running_balance
    return entries


@login_required(login_url="/accounts/login/")
def cash_flow_report(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    period_type = request.GET.get("period_type", "")
    month_value = request.GET.get("month", "")
    year_value = request.GET.get("year", "")
    entries = None
    start_date = end_date = None
    error = ""

    if period_type == "monthly":
        try:
            selected_month = datetime.strptime(month_value, "%Y-%m")
            start_date = date(selected_month.year, selected_month.month, 1)
            end_date = date(selected_month.year, selected_month.month, monthrange(selected_month.year, selected_month.month)[1])
        except (TypeError, ValueError):
            error = "Select a valid month."
    elif period_type == "yearly":
        try:
            selected_year = int(year_value)
            if selected_year < 2000 or selected_year > 9999:
                raise ValueError
            start_date, end_date = date(selected_year, 1, 1), date(selected_year, 12, 31)
        except (TypeError, ValueError):
            error = "Enter a valid year."
    elif period_type:
        error = "Select monthly or yearly reporting."

    if start_date and end_date:
        entries = _cash_flow_entries(start_date, end_date)
        if request.GET.get("export") == "excel":
            return export_cash_flow_to_excel(entries, start_date, end_date)

    total_inflow = sum((item["inflow"] for item in entries or []), Decimal("0"))
    total_outflow = sum((item["outflow"] for item in entries or []), Decimal("0"))
    return render(request, "finance/cash_flow_report.html", {
        "period_type": period_type, "month_value": month_value, "year_value": year_value,
        "entries": entries, "start_date": start_date, "end_date": end_date, "error": error,
        "total_inflow": total_inflow, "total_outflow": total_outflow,
        "net_cash_flow": total_inflow - total_outflow,
    })


@login_required(login_url="/accounts/login/")
def financial_analytics(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    period_type = request.GET.get("period_type", "")
    month_value = request.GET.get("month", "")
    year_value = request.GET.get("year", "")
    today = timezone.localdate()
    error = ""
    comparison_label = ""
    previous_start = previous_end = None

    if period_type == "monthly":
        try:
            selected = datetime.strptime(month_value, "%Y-%m")
            start_date = date(selected.year, selected.month, 1)
            end_date = date(selected.year, selected.month, monthrange(selected.year, selected.month)[1])
            previous_end = start_date - timedelta(days=1)
            previous_start = date(previous_end.year, previous_end.month, 1)
            comparison_label = "previous month"
        except (TypeError, ValueError):
            error = "Select a valid month. Showing all available data."
            period_type = ""
    elif period_type == "yearly":
        try:
            selected_year = int(year_value)
            if selected_year < 1900 or selected_year > 9999:
                raise ValueError
            start_date, end_date = date(selected_year, 1, 1), date(selected_year, 12, 31)
            previous_start, previous_end = date(selected_year - 1, 1, 1), date(selected_year - 1, 12, 31)
            comparison_label = "previous year"
        except (TypeError, ValueError):
            error = "Enter a valid year. Showing all available data."
            period_type = ""
    elif period_type:
        error = "Select monthly or yearly reporting. Showing all available data."
        period_type = ""

    if not period_type:
        start_date, end_date = date(1900, 1, 1), date(9999, 12, 31)

    entries = _cash_flow_entries(start_date, end_date)
    total_inflow = sum((entry["inflow"] for entry in entries), Decimal("0"))
    total_outflow = sum((entry["outflow"] for entry in entries), Decimal("0"))
    net_cash_flow = total_inflow - total_outflow
    outflow_percentage = (total_outflow / total_inflow * Decimal("100")) if total_inflow else Decimal("0")
    profit_margin = (net_cash_flow / total_inflow * Decimal("100")) if total_inflow else Decimal("0")

    # Card purchases are liabilities until the bank pays the statement.  Show
    # the selected month's approved net card spend as the following month's
    # expected bill, without adding it to this period's cash outflow.
    if period_type == "monthly":
        card_bill_start, card_bill_end = start_date, end_date
    else:
        card_bill_start = date(today.year, today.month, 1)
        card_bill_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    next_bill_month = (card_bill_end + timedelta(days=1)).strftime("%B %Y")
    card_due_sources = {}
    card_transactions = OfficeExpense.objects.select_related("credit_card").filter(
        payment_mode=OfficeExpense.PaymentMode.CREDIT_CARD,
        approval_status=OfficeExpense.ApprovalStatus.APPROVED,
        expense_date__range=(card_bill_start, card_bill_end),
    )
    for expense in card_transactions:
        card_label = str(expense.credit_card)
        signed_amount = (
            -expense.amount
            if expense.transaction_kind == OfficeExpense.TransactionKind.REFUND
            else expense.amount
        )
        card_due_sources[card_label] = card_due_sources.get(card_label, Decimal("0")) + signed_amount
    card_due_sources = {
        label: max(amount, Decimal("0"))
        for label, amount in card_due_sources.items()
        if amount > 0
    }
    next_card_bill_total = sum(card_due_sources.values(), Decimal("0"))

    revenue_sources = {}
    expense_sources = {}
    timeline = {}
    for entry in entries:
        if period_type == "monthly":
            key = entry["date"].isoformat()
            label = entry["date"].strftime("%b %d")
        else:
            key = entry["date"].strftime("%Y-%m")
            label = entry["date"].strftime("%b %Y")
        bucket = timeline.setdefault(key, {
            "label": label, "inflow": Decimal("0"), "outflow": Decimal("0"),
        })
        bucket["inflow"] += entry["inflow"]
        bucket["outflow"] += entry["outflow"]
        if entry["inflow"]:
            revenue_label = (
                "Hostel Registration"
                if entry["source"] == "Hostel Revenue" and entry["category"] == "Registration Fee"
                else "Hostel Rent"
                if entry["source"] == "Hostel Revenue"
                else entry["source"]
            )
            revenue_sources[revenue_label] = revenue_sources.get(revenue_label, Decimal("0")) + entry["inflow"]
        if entry["outflow"]:
            expense_sources[entry["source"]] = expense_sources.get(entry["source"], Decimal("0")) + entry["outflow"]

    sorted_timeline = [timeline[key] for key in sorted(timeline)]
    chart_data = {
        "timeline": {
            "labels": [item["label"] for item in sorted_timeline],
            "inflow": [float(item["inflow"]) for item in sorted_timeline],
            "outflow": [float(item["outflow"]) for item in sorted_timeline],
            "net": [float(item["inflow"] - item["outflow"]) for item in sorted_timeline],
        },
        "revenue": {"labels": list(revenue_sources), "values": [float(value) for value in revenue_sources.values()]},
        "expense": {"labels": list(expense_sources), "values": [float(value) for value in expense_sources.values()]},
        "card_due": {"labels": list(card_due_sources), "values": [float(value) for value in card_due_sources.values()]},
        "position": [float(total_inflow), float(total_outflow)],
    }

    previous_net = comparison_percent = None
    if previous_start and previous_end:
        previous_entries = _cash_flow_entries(previous_start, previous_end)
        previous_net = sum((entry["inflow"] - entry["outflow"] for entry in previous_entries), Decimal("0"))
        if previous_net:
            comparison_percent = ((net_cash_flow - previous_net) / abs(previous_net)) * Decimal("100")

    new_hostels = Hostel.objects.filter(created_at__date__range=(start_date, end_date)).count()
    inactive_hostels = Hostel.objects.filter(status=False, updated_at__date__range=(start_date, end_date)).count()
    new_customers = Customer.objects.filter(created_at__date__range=(start_date, end_date)).count()
    inactive_customers = Customer.objects.filter(status=False, updated_at__date__range=(start_date, end_date)).count()

    return render(request, "finance/financial_analytics.html", {
        "period_type": period_type, "month_value": month_value, "year_value": year_value,
        "start_date": start_date, "end_date": end_date, "error": error,
        "entries_count": len(entries), "total_inflow": total_inflow,
        "total_outflow": total_outflow, "net_cash_flow": net_cash_flow,
        "entries_count_display": f"{len(entries):,}",
        "total_inflow_display": f"{total_inflow:,.0f}",
        "total_outflow_display": f"{total_outflow:,.0f}",
        "net_cash_flow_display": f"{net_cash_flow:,.0f}",
        "outflow_percentage": outflow_percentage, "profit_margin": profit_margin,
        "next_card_bill_total": next_card_bill_total,
        "next_card_bill_display": f"{next_card_bill_total:,.0f}",
        "next_bill_month": next_bill_month,
        "card_bill_start": card_bill_start, "card_bill_end": card_bill_end,
        "previous_net": previous_net, "comparison_percent": comparison_percent,
        "comparison_label": comparison_label, "new_hostels": new_hostels,
        "inactive_hostels": inactive_hostels, "new_customers": new_customers,
        "inactive_customers": inactive_customers, "chart_data": chart_data,
        "all_data": not period_type,
    })


def _credit_card_period_expenses(credit_card_id, period_start, period_end):
    records = OfficeExpense.objects.filter(
        credit_card_id=credit_card_id,
        payment_mode=OfficeExpense.PaymentMode.CREDIT_CARD,
        approval_status=OfficeExpense.ApprovalStatus.APPROVED,
        expense_date__range=(period_start, period_end),
    ).order_by('expense_date', 'created_at')
    expense_total = records.filter(
        transaction_kind=OfficeExpense.TransactionKind.EXPENSE
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    refund_total = records.filter(
        transaction_kind=OfficeExpense.TransactionKind.REFUND
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    return records, expense_total - refund_total


@login_required(login_url='/accounts/login/')
@permission_required('finance.view_officeexpense', raise_exception=True)
def office_expense_list(request):
    today = timezone.localdate()
    transaction_code = request.GET.get('transaction_code', '').strip().upper()
    status = request.GET.get('status', '').strip().upper()
    payment_mode = request.GET.get('payment_mode', '').strip().upper()
    search_ignores_dates = bool(transaction_code)
    try:
        from_date = datetime.strptime(request.GET.get('from_date', ''), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        from_date = today.replace(day=1)
    try:
        to_date = datetime.strptime(request.GET.get('to_date', ''), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        to_date = today
    expenses = OfficeExpense.objects.select_related(
        'bank_account', 'credit_card', 'created_by', 'updated_by', 'approved_by', 'original_expense'
    ).all()
    if transaction_code:
        expenses = expenses.filter(transaction_code__iexact=transaction_code)
    else:
        expenses = expenses.filter(expense_date__range=(from_date, to_date))
    if status in OfficeExpense.ApprovalStatus.values:
        expenses = expenses.filter(approval_status=status)
    if payment_mode in OfficeExpense.PaymentMode.values:
        expenses = expenses.filter(payment_mode=payment_mode)
    if request.GET.get('export') == 'excel':
        return export_office_expenses_to_excel(expenses)
    overall_expense_total = expenses.filter(
        transaction_kind=OfficeExpense.TransactionKind.EXPENSE
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    overall_refund_total = expenses.filter(
        transaction_kind=OfficeExpense.TransactionKind.REFUND
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    page_obj = Paginator(expenses, 25).get_page(request.GET.get('page'))
    page_records = list(page_obj.object_list)
    page_expense_total = sum(
        (item.amount for item in page_records if item.transaction_kind == OfficeExpense.TransactionKind.EXPENSE),
        Decimal('0'),
    )
    page_refund_total = sum(
        (item.amount for item in page_records if item.transaction_kind == OfficeExpense.TransactionKind.REFUND),
        Decimal('0'),
    )
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'finance/office_expense_list.html', {
        'expenses': page_obj, 'page_obj': page_obj, 'total_count': page_obj.paginator.count,
        'transaction_code': transaction_code, 'status': status,
        'payment_mode': payment_mode, 'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'), 'search_ignores_dates': search_ignores_dates,
        'status_choices': OfficeExpense.ApprovalStatus.choices,
        'payment_mode_choices': OfficeExpense.PaymentMode.choices,
        'query_string': query_params.urlencode(),
        'page_expense_total': page_expense_total, 'page_refund_total': page_refund_total,
        'page_net_total': page_expense_total - page_refund_total,
        'overall_expense_total': overall_expense_total, 'overall_refund_total': overall_refund_total,
        'overall_net_total': overall_expense_total - overall_refund_total,
    })


@login_required(login_url='/accounts/login/')
@permission_required('finance.view_creditcardsettlement', raise_exception=True)
def card_settlement_list(request):
    today = timezone.localdate()
    transaction_code = request.GET.get('transaction_code', '').strip().upper()
    status = request.GET.get('status', '').strip().upper()
    search_ignores_dates = bool(transaction_code)
    try:
        from_date = datetime.strptime(request.GET.get('from_date', ''), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        from_date = today.replace(day=1)
    try:
        to_date = datetime.strptime(request.GET.get('to_date', ''), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        to_date = today
    settlements = CreditCardSettlement.objects.select_related(
        'credit_card', 'bank_account', 'created_by', 'updated_by', 'approved_by'
    )
    if transaction_code:
        settlements = settlements.filter(transaction_code__iexact=transaction_code)
    else:
        settlements = settlements.filter(settlement_date__range=(from_date, to_date))
    if status in CreditCardSettlement.ApprovalStatus.values:
        settlements = settlements.filter(approval_status=status)
    if request.GET.get('export') == 'excel':
        return export_card_settlements_to_excel(settlements)
    overall_total = settlements.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    page_obj = Paginator(settlements, 25).get_page(request.GET.get('page'))
    page_total = sum((item.amount for item in page_obj.object_list), Decimal('0'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'finance/card_settlement_list.html', {
        'settlements': page_obj, 'page_obj': page_obj, 'total_count': page_obj.paginator.count,
        'transaction_code': transaction_code, 'status': status,
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'), 'search_ignores_dates': search_ignores_dates,
        'status_choices': CreditCardSettlement.ApprovalStatus.choices,
        'query_string': query_params.urlencode(),
        'page_total': page_total, 'overall_total': overall_total,
    })


@login_required(login_url='/accounts/login/')
def card_settlement_preview(request):
    if not (
        request.user.has_perm('finance.view_creditcardsettlement')
        or request.user.has_perm('finance.add_creditcardsettlement')
        or request.user.has_perm('finance.change_creditcardsettlement')
    ):
        raise PermissionDenied
    credit_card_id = request.GET.get('credit_card', '').strip()
    try:
        period_start = datetime.strptime(request.GET.get('period_start', ''), '%Y-%m-%d').date()
        period_end = datetime.strptime(request.GET.get('period_end', ''), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Select the credit card and both card bill period dates.'}, status=400)
    if not credit_card_id.isdigit():
        return JsonResponse({'error': 'Select the credit card being paid.'}, status=400)
    if period_end < period_start:
        return JsonResponse({'error': 'Card bill period to cannot be before card bill period from.'}, status=400)
    if not OfficeCreditCard.objects.filter(pk=credit_card_id).exists():
        return JsonResponse({'error': 'The selected credit card was not found.'}, status=404)
    records, calculated_total = _credit_card_period_expenses(credit_card_id, period_start, period_end)
    return JsonResponse({
        'calculated_total': str(calculated_total),
        'record_count': records.count(),
        'transactions': [
            {
                'id': item.transaction_code,
                'date': item.expense_date.isoformat(),
                'kind': item.get_transaction_kind_display(),
                'amount': str(item.amount),
            }
            for item in records
        ],
    })


@login_required(login_url='/accounts/login/')
@permission_required('finance.add_officeexpense', raise_exception=True)
def office_expense_create(request):
    form = OfficeExpenseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        expense = form.save(commit=False)
        expense.created_by = expense.updated_by = request.user
        expense.save()
        messages.success(request, 'Office expense submitted for approval.')
        return redirect('finance:office_expenses')
    return render(request, 'finance/office_expense_form.html', {'form': form, 'title': 'Add Office Expense'})


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_officeexpense', raise_exception=True)
def office_expense_edit(request, pk):
    expense = get_object_or_404(OfficeExpense, pk=pk)
    if expense.approval_status != OfficeExpense.ApprovalStatus.PENDING:
        messages.error(request, 'Only pending office expenses can be edited.')
        return redirect('finance:office_expenses')
    form = OfficeExpenseForm(request.POST or None, instance=expense)
    if request.method == 'POST' and form.is_valid():
        expense = form.save(commit=False)
        expense.updated_by = request.user
        expense.save()
        messages.success(request, 'Office expense updated.')
        return redirect('finance:office_expenses')
    return render(request, 'finance/office_expense_form.html', {'form': form, 'title': 'Edit Office Expense'})


@login_required(login_url='/accounts/login/')
@permission_required('finance.view_officeexpense', raise_exception=True)
def office_expense_detail(request, pk):
    expense = get_object_or_404(
        OfficeExpense.objects.select_related(
            'bank_account', 'credit_card', 'original_expense', 'created_by',
            'updated_by', 'approved_by'
        ),
        pk=pk,
    )
    return render(request, 'finance/office_expense_detail.html', {'expense': expense})


@login_required(login_url='/accounts/login/')
@permission_required('finance.view_officeexpense', raise_exception=True)
def office_expense_lookup(request):
    transaction_code = request.GET.get('transaction_code', '').strip().upper()
    if not transaction_code:
        return JsonResponse({'error': 'Enter an expense transaction ID.'}, status=400)
    expense = OfficeExpense.objects.select_related('bank_account', 'credit_card').filter(
        transaction_code__iexact=transaction_code,
        transaction_kind=OfficeExpense.TransactionKind.EXPENSE,
        approval_status=OfficeExpense.ApprovalStatus.APPROVED,
    ).first()
    if not expense:
        return JsonResponse({'error': 'No approved expense was found with this ID.'}, status=404)
    previous_refunds = expense.refunds.exclude(
        approval_status=OfficeExpense.ApprovalStatus.REJECTED
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    remaining_amount = expense.amount - previous_refunds
    if remaining_amount <= 0:
        return JsonResponse({'error': 'This expense has already been fully refunded.'}, status=400)
    return JsonResponse({
        'id': expense.pk, 'transaction_code': expense.transaction_code,
        'category': expense.category, 'other_category': expense.other_category,
        'vendor': expense.vendor, 'description': expense.description,
        'amount': str(remaining_amount), 'original_amount': str(expense.amount),
        'payment_mode': expense.payment_mode,
        'bank_account': expense.bank_account_id or '',
        'bank_account_label': str(expense.bank_account) if expense.bank_account else '',
        'credit_card': expense.credit_card_id or '',
        'credit_card_label': str(expense.credit_card) if expense.credit_card else '',
        'frequency': expense.frequency,
        'service_period_start': expense.service_period_start.isoformat() if expense.service_period_start else '',
        'service_period_end': expense.service_period_end.isoformat() if expense.service_period_end else '',
        'memo': expense.memo,
    })


def _decide_record(request, record, pending_value, approved_value, rejected_value, redirect_name):
    if record.created_by_id == request.user.id:
        messages.error(request, 'You cannot approve or reject a transaction that you created.')
        return redirect(redirect_name)
    if request.method != 'POST':
        return render(request, 'finance/office_approval_form.html', {'record': record, 'cancel_url_name': redirect_name})
    if record.approval_status != pending_value:
        messages.error(request, 'This record has already been decided.')
        return redirect(redirect_name)
    decision = request.POST.get('decision')
    status_memo = request.POST.get('status_memo', '').strip()
    if decision not in (approved_value, rejected_value):
        messages.error(request, 'Select Approve or Reject.')
    elif decision == rejected_value and not status_memo:
        messages.error(request, 'A rejection reason is required.')
    else:
        record.approval_status = decision
        record.status_memo = status_memo
        record.approved_by = request.user
        record.decided_at = timezone.now()
        record.updated_by = request.user
        record.save()
        messages.success(request, f'{record.transaction_code} was {decision.lower()}.')
        return redirect(redirect_name)
    return render(request, 'finance/office_approval_form.html', {
        'record': record, 'status_memo': status_memo, 'cancel_url_name': redirect_name,
    })


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_officeexpense', raise_exception=True)
def office_expense_decide(request, pk):
    record = get_object_or_404(OfficeExpense, pk=pk)
    return _decide_record(request, record, OfficeExpense.ApprovalStatus.PENDING,
                          OfficeExpense.ApprovalStatus.APPROVED, OfficeExpense.ApprovalStatus.REJECTED,
                          'finance:office_expenses')


@login_required(login_url='/accounts/login/')
@permission_required('finance.add_creditcardsettlement', raise_exception=True)
def card_settlement_create(request):
    form = CreditCardSettlementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        settlement = form.save(commit=False)
        settlement.created_by = settlement.updated_by = request.user
        matched_expenses, calculated_total = _credit_card_period_expenses(
            settlement.credit_card_id, settlement.statement_period_start, settlement.statement_period_end
        )
        settlement.calculated_expense_total = calculated_total
        settlement.save()
        settlement.matched_expenses.set(matched_expenses)
        messages.success(request, 'Credit-card settlement submitted for approval. It was not recorded as an expense.')
        return redirect('finance:card_settlements')
    return render(request, 'finance/office_expense_form.html', {'form': form, 'title': 'Add Credit Card Settlement'})


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_creditcardsettlement', raise_exception=True)
def card_settlement_edit(request, pk):
    settlement = get_object_or_404(CreditCardSettlement, pk=pk)
    if settlement.approval_status != CreditCardSettlement.ApprovalStatus.PENDING:
        messages.error(request, 'Only pending settlements can be edited.')
        return redirect('finance:card_settlements')
    form = CreditCardSettlementForm(request.POST or None, instance=settlement)
    if request.method == 'POST' and form.is_valid():
        settlement = form.save(commit=False)
        settlement.updated_by = request.user
        matched_expenses, calculated_total = _credit_card_period_expenses(
            settlement.credit_card_id, settlement.statement_period_start, settlement.statement_period_end
        )
        settlement.calculated_expense_total = calculated_total
        settlement.save()
        settlement.matched_expenses.set(matched_expenses)
        messages.success(request, 'Credit-card settlement updated.')
        return redirect('finance:card_settlements')
    return render(request, 'finance/office_expense_form.html', {'form': form, 'title': 'Edit Credit Card Settlement'})


@login_required(login_url='/accounts/login/')
@permission_required('finance.view_creditcardsettlement', raise_exception=True)
def card_settlement_detail(request, pk):
    settlement = get_object_or_404(
        CreditCardSettlement.objects.select_related(
            'credit_card', 'bank_account', 'created_by', 'updated_by', 'approved_by'
        ).prefetch_related('matched_expenses'),
        pk=pk,
    )
    return render(request, 'finance/card_settlement_detail.html', {'settlement': settlement})


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_creditcardsettlement', raise_exception=True)
def card_settlement_decide(request, pk):
    record = get_object_or_404(CreditCardSettlement, pk=pk)
    if record.created_by_id == request.user.id:
        messages.error(request, 'You cannot approve or reject a transaction that you created.')
        return redirect('finance:card_settlements')
    if not record.is_amount_matched:
        messages.error(
            request,
            'This card bill payment cannot be reviewed because the bank deduction does not match the approved expense total.'
        )
        return redirect('finance:card_settlements')
    return _decide_record(request, record, CreditCardSettlement.ApprovalStatus.PENDING,
                          CreditCardSettlement.ApprovalStatus.APPROVED, CreditCardSettlement.ApprovalStatus.REJECTED,
                          'finance:card_settlements')


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda user: user.is_superuser)
def office_payment_accounts(request):
    return render(request, 'finance/office_payment_accounts.html', {
        'bank_accounts': OfficeBankAccount.objects.all(), 'credit_cards': OfficeCreditCard.objects.all(),
    })


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda user: user.is_superuser)
def office_bank_account_create(request):
    form = OfficeBankAccountForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        account = form.save(commit=False)
        account.created_by = account.updated_by = request.user
        account.save()
        return redirect('finance:office_payment_accounts')
    return render(request, 'finance/office_expense_form.html', {'form': form, 'title': 'Add Bank Account'})


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda user: user.is_superuser)
def office_bank_account_edit(request, pk):
    account = get_object_or_404(OfficeBankAccount, pk=pk)
    form = OfficeBankAccountForm(request.POST or None, instance=account)
    if request.method == 'POST' and form.is_valid():
        account = form.save(commit=False)
        account.updated_by = request.user
        account.save()
        return redirect('finance:office_payment_accounts')
    return render(request, 'finance/office_expense_form.html', {'form': form, 'title': 'Edit Bank Account'})


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda user: user.is_superuser)
def office_credit_card_create(request):
    form = OfficeCreditCardForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        card = form.save(commit=False)
        card.created_by = card.updated_by = request.user
        card.save()
        return redirect('finance:office_payment_accounts')
    return render(request, 'finance/office_expense_form.html', {'form': form, 'title': 'Add Credit Card'})


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda user: user.is_superuser)
def office_credit_card_edit(request, pk):
    card = get_object_or_404(OfficeCreditCard, pk=pk)
    form = OfficeCreditCardForm(request.POST or None, instance=card)
    if request.method == 'POST' and form.is_valid():
        card = form.save(commit=False)
        card.updated_by = request.user
        card.save()
        return redirect('finance:office_payment_accounts')
    return render(request, 'finance/office_expense_form.html', {'form': form, 'title': 'Edit Credit Card'})


@login_required(login_url='/accounts/login/')
def revenues(request):
    name = request.GET.get('name')
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    hostel = request.GET.get('hostel')
    record_type = request.GET.get('record_type', 'rent')  # Default to 'rent'
    today = timezone.now()
    query = Q()
    if name:
        query &= Q(customer__name__icontains=name)
    if hostel:
        query &= Q(customer__bed_assignment__unit__hostel__name__icontains=hostel)
    # Default filter by creation date instead of revenue year/month
    if from_date:
        from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
    else:
        from_date = today.replace(day=1)
    # Default = today
    if to_date:
        to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    else:
        to_date = today
    query &= Q(created_at__date__gte=from_date, created_at__date__lte=to_date)
    # Filter by record type (rent or registration)
    if record_type == 'registration':
        query &= Q(title='registration_fee')
    else:  # Default to 'rent'
        query &= Q(title='rent')
    # Get all revenues with the base query, ordered by creation date (newest first)
    all_revenues = HostelRevenue.objects.select_related('customer', 'created_by').filter(query).order_by('-created_at')
    # Separate registration and rent records based on filter
    if record_type == 'registration':
        registration_revenues = all_revenues
        rent_revenues = all_revenues.none()  # Empty queryset
    else:  # record_type == 'rent' (default)
        registration_revenues = all_revenues.none()  # Empty queryset
        rent_revenues = all_revenues
    registration_total = registration_revenues.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    rent_collection_total = rent_revenues.aggregate(total=Sum('collected_amount'))['total'] or Decimal('0')
    rent_total_amount = rent_revenues.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    # No pagination for registration revenues - display all records
    registration_page_obj = registration_revenues
    # Pagination for rent revenues (limit 20)
    rent_page = request.GET.get('rent_page', 1)
    rent_paginator = Paginator(rent_revenues, 20)
    rent_page_obj = rent_paginator.get_page(rent_page)
    # Calculate page totals
    registration_page_total = registration_revenues.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    rent_page_total_amount = rent_page_obj.object_list.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    rent_page_collection_total = rent_page_obj.object_list.aggregate(total=Sum('collected_amount'))['total'] or Decimal('0')
    # ✅ Only allow download if there are results
    if request.GET.get('download') == 'excel':
        if all_revenues.exists():
            return export_revenues_to_excel(all_revenues, record_type)
        else:
            messages.warning(request, "No data available to export.")
    if request.GET and not any([name, from_date, to_date, hostel]):
        messages.warning(request, "No filter parameters provided.")
    year_choices = HostelRevenue.objects.values_list('year', flat=True).distinct().order_by('-year')
    # Get all hostels for the filter dropdown
    from hostel.models import Hostel
    all_hostels = Hostel.objects.filter(status=True).order_by('name')
    return render(request, 'finance/revenues_dashboard.html', {
        'registration_revenues': registration_page_obj,
        'rent_revenues': rent_page_obj,
        'registration_total': registration_total,
        'registration_page_total': registration_page_total,
        'rent_collection_total': rent_collection_total,
        'rent_total_amount': rent_total_amount,
        'rent_page_total_amount': rent_page_total_amount,
        'rent_page_collection_total': rent_page_collection_total,
        'name': name,
        'from_date': from_date.strftime("%Y-%m-%d"),
        'to_date': to_date.strftime("%Y-%m-%d"),
        'selected_hostel': hostel,
        'selected_record_type': record_type,
        'year_choices': year_choices,
        'month_choices': [(i, i) for i in range(1, 13)],
        'all_hostels': all_hostels,
    })


@login_required(login_url='/accounts/login/')
def real_estate_revenue(request):
    """Display real estate revenue generated by rental contracts."""
    if not (request.user.is_superuser or request.user.has_perm('targets.view_rentalcontract')):
        raise PermissionDenied
    today = timezone.now().date()
    customer_name = request.GET.get('customer_name', '').strip()
    management_company = request.GET.get('management_company', '').strip()
    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()

    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date() if from_date_str else today.replace(day=1)
    except ValueError:
        from_date = today.replace(day=1)
    try:
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date() if to_date_str else today
    except ValueError:
        to_date = today

    contracts = RentalContract.objects.select_related('created_by', 'ad_fee_confirmed_by', 'target_to', 'target_to__target_to')
    if customer_name:
        contracts = contracts.filter(customer_name__icontains=customer_name)
    if management_company:
        contracts = contracts.filter(management_company_name=management_company)
    management_companies = RentalContract.objects.exclude(management_company_name='').values_list('management_company_name', flat=True).distinct().order_by('management_company_name')
    agent_contracts = contracts.filter(contract_date__range=(from_date, to_date))
    received_ad_fees = contracts.filter(ad_fee_confirmed_at__isnull=False, ad_fee_received_date__range=(from_date, to_date))
    pending_ad_fees = contracts.filter(ad_fee__gt=0, ad_fee_confirmed_at__isnull=True).order_by('contract_date')
    total_agent_fee = agent_contracts.aggregate(total=Sum('agent_fee'))['total'] or Decimal('0')
    total_ad_fee = received_ad_fees.aggregate(total=Sum('ad_fee_received_amount'))['total'] or Decimal('0')
    revenue_contracts = contracts.filter(Q(contract_date__range=(from_date, to_date)) | Q(ad_fee_confirmed_at__isnull=False, ad_fee_received_date__range=(from_date, to_date))).distinct().order_by('-created_at')
    export_type = request.GET.get('export')
    if export_type == 'pending':
        return export_pending_ad_fees_to_excel(pending_ad_fees)
    if export_type == 'revenue':
        return export_real_estate_revenue_to_excel(revenue_contracts, from_date, to_date)
    paginator = Paginator(revenue_contracts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    for contract in page_obj:
        contract.period_agent_fee = contract.agent_fee if from_date <= contract.contract_date <= to_date else Decimal('0')
        contract.period_ad_fee = contract.ad_fee_received_amount if contract.ad_fee_received_date and from_date <= contract.ad_fee_received_date <= to_date else Decimal('0')
        contract.period_revenue = contract.period_agent_fee + (contract.period_ad_fee or Decimal('0'))
    page_total_revenue = sum((contract.period_revenue for contract in page_obj), Decimal('0'))
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    if 'export' in query_params:
        query_params.pop('export')

    return render(request, 'finance/real_estate_revenue.html', {
        'contracts': page_obj, 'total_count': revenue_contracts.count(), 'total_agent_fee': total_agent_fee,
        'total_ad_fee': total_ad_fee, 'total_revenue': total_agent_fee + total_ad_fee,
        'page_total_revenue': page_total_revenue,
        'customer_name': customer_name, 'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'), 'query_string': query_params.urlencode(),
        'management_companies': management_companies, 'selected_management_company': management_company,
        'can_confirm_ad_fee': request.user.is_superuser or request.user.has_perm('targets.change_rentalcontract'),
        'pending_ad_fees': pending_ad_fees[:20], 'pending_ad_fee_count': pending_ad_fees.count(),
    })


@login_required(login_url='/accounts/login/')
def confirm_ad_fee_receipt(request, pk):
    """Manually confirm the single AD fee receipt for a rental contract."""
    if not (request.user.is_superuser or request.user.has_perm('targets.change_rentalcontract')):
        raise PermissionDenied
    contract = get_object_or_404(RentalContract, pk=pk)
    if contract.ad_fee_confirmed_at:
        messages.info(request, 'The AD fee receipt for this contract has already been confirmed.')
        return redirect('finance:real_estate_revenue')

    if request.method == 'POST':
        form = AdFeeReceiptForm(request.POST, instance=contract)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.ad_fee_confirmed_by = request.user
            receipt.ad_fee_confirmed_at = timezone.now()
            receipt.updated_by = request.user
            receipt.save(update_fields=['ad_fee_received_amount', 'ad_fee_transfer_fee', 'ad_fee_received_date', 'ad_fee_memo', 'ad_fee_confirmed_by', 'ad_fee_confirmed_at', 'updated_by', 'updated_at'])
            messages.success(request, f'AD fee receipt for {contract.customer_name} was confirmed successfully.')
            return redirect('finance:real_estate_revenue')
    else:
        form = AdFeeReceiptForm(instance=contract, initial={'ad_fee_received_date': timezone.now().date()})
    return render(request, 'finance/confirm_ad_fee_receipt.html', {'contract': contract, 'form': form})


@login_required(login_url='/accounts/login/')
def revenue_detail(request, pk):
    revenue = get_object_or_404(HostelRevenue, pk=pk)
    return render(request, 'finance/revenue_detail.html', {'revenue': revenue})


@login_required(login_url='/accounts/login/')
def get_previous_prepaid_amount(customer, year, month):
    """
    Get the prepaid amount from the previous month's rent payment.
    Returns the prepaid amount if the previous month had a prepaid payment.
    """
    # Calculate previous month
    prev_month = month - 1
    prev_year = year
    if prev_month <= 0:
        prev_month = 12
        prev_year = year - 1
    try:
        prev_revenue = HostelRevenue.objects.get(title='rent', customer=customer, year=prev_year, month=prev_month)
        # Return prepaid amount if it exists and payment type is prepaid
        if prev_revenue.payment_type == 'prepaid' and prev_revenue.prepaid_amount:
            return prev_revenue.prepaid_amount
        return Decimal('0')
    except HostelRevenue.DoesNotExist:
        return Decimal('0')

@login_required(login_url='/accounts/login/')
def monthly_rent(request, customer_id):
    """
    Handle monthly rent payment processing with comprehensive validation:
    - Ensures customer has registration fee
    - Validates rent payment chronology (sequential months, no duplicates)
    - Calculates prepaid/postpaid amounts
    - Handles rent discounts with memo requirements
    """
    customer_details = get_object_or_404(Bed.objects.select_related('unit', 'unit__hostel', 'customer'), customer=customer_id)
    # Stage 1: Validate required bed fees are set
    missing_fees = []
    if not customer_details.rent or customer_details.rent == 0:
        missing_fees.append("Base Rent")
    if not customer_details.utilities_fee or customer_details.utilities_fee == 0:
        missing_fees.append("Utilities Fee")
    if missing_fees:
        messages.error(request, f"Please add {', '.join(missing_fees)} in bed details. You cannot process without these fees.")
        return redirect('customer:customer_detail', customer_id)
    if request.method == "POST":
        # Parse payment month from form
        month_input = request.POST.get("rent_month")
        if not month_input:
            messages.error(request, "Payment month is required.")
            return redirect(request.path)
        year, month = map(int, month_input.split("-"))
        # Stage 2: Validate registration fee payment requirement
        registration_payment = HostelRevenue.objects.filter(title='registration_fee', customer=customer_details.customer).first()
        if not registration_payment:
            messages.error(request, "Customer must pay registration fee before making rent payments.")
            return redirect(request.path)
        # Stage 3: Check for duplicate payment
        existing_rent_payments = HostelRevenue.objects.filter(title='rent', customer=customer_details.customer).order_by('year', 'month')
        duplicate_payment = existing_rent_payments.filter(year=year, month=month).first()
        if duplicate_payment:
            messages.error(request, f"Payment for {year}-{month:02d} already exists. Please select a different month.")
            return redirect(request.path)
        # Stage 4: Validate sequential month payment
        if not existing_rent_payments.exists():
            # First rent payment must be in registration month
            reg_year = registration_payment.year
            reg_month = registration_payment.month
            if year != reg_year or month != reg_month:
                messages.error(request, f"First rent payment must be in the registration month. Customer registered in {reg_year}-{reg_month:02d}. First rent payment should be for {reg_year}-{reg_month:02d}.")
                return redirect(request.path)
        else:
            # Subsequent payments must follow previous payment sequentially
            last_payment = existing_rent_payments.last()
            last_year = last_payment.year
            last_month = last_payment.month
            expected_month = last_month + 1
            expected_year = last_year
            if expected_month > 12:
                expected_month = 1
                expected_year += 1
            if year < last_year or (year == last_year and month < last_month):
                messages.error(request, f"Cannot pay rent for a month before the last payment. Last payment was for {last_year}-{last_month:02d}.")
                return redirect(request.path)
            if year != expected_year or month != expected_month:
                messages.error(request, f"Cannot skip months. Last payment was for {last_year}-{last_month:02d}. Next payment should be for {expected_year}-{expected_month:02d}.")
                return redirect(request.path)
        # Stage 5: Parse and validate numeric payment amounts
        try:
            base_rent = Decimal(request.POST.get("rent", "0"))
            internet_fee = Decimal(request.POST.get("internet", "0"))
            utilities_fee = Decimal(request.POST.get("utilities", "0"))
            rent_discount_percent = Decimal(request.POST.get("rent_discount_percent", "0"))
            payment_type = request.POST.get("payment_type", "")
            collected_amount_str = request.POST.get("collected_amount", "").strip()
            collected_amount = Decimal(collected_amount_str) if collected_amount_str and collected_amount_str not in ("", "NaN") else Decimal("0")
            prepaid_amount_str = request.POST.get("prepaid_amount", "").strip()
            prepaid_amount = Decimal(prepaid_amount_str) if prepaid_amount_str and prepaid_amount_str not in ("", "NaN") else Decimal("0")
        except InvalidOperation as e:
            messages.error(request, f"Invalid numeric values in the form. Please check all amount fields. Error: {str(e)}")
            return redirect(request.path)
        # Calculate rent components
        rent_after_discount = base_rent * (Decimal(1) - rent_discount_percent / Decimal(100))
        total_amount = rent_after_discount + internet_fee + utilities_fee
        # Validate memo requirement for discounted rent
        memo = request.POST.get("memo", "").strip()
        if rent_discount_percent > 0 and not memo:
            messages.error(request, "Memo is required when a discount is applied.")
            return redirect(request.path)
        # Stage 6: Calculate prepaid/postpaid from previous month
        previous_prepaid = Decimal('0')
        previous_postpaid = Decimal('0')
        prev_month = month - 1
        prev_year = year
        if prev_month <= 0:
            prev_month = 12
            prev_year = year - 1
        had_postpaid_last_month = False
        try:
            prev_revenue = HostelRevenue.objects.get(title='rent', customer=customer_details.customer, year=prev_year, month=prev_month)
            if prev_revenue.payment_type == 'prepaid' and prev_revenue.prepaid_amount:
                previous_prepaid = prev_revenue.prepaid_amount
            elif prev_revenue.payment_type == 'postpaid' and prev_revenue.prepaid_amount:
                previous_postpaid = prev_revenue.prepaid_amount
                had_postpaid_last_month = True
        except HostelRevenue.DoesNotExist:
            had_postpaid_last_month = False
        # Adjust total based on previous month's prepaid/postpaid
        adjusted_total = total_amount - previous_prepaid + previous_postpaid
        # Stage 7: Validate postpaid consecutive restriction
        if had_postpaid_last_month and payment_type == 'postpaid':
            messages.error(request, "Customer cannot make postpaid payment this month as they had postpaid payment last month. Please pay the full amount including the previous postpaid amount.")
            return redirect(request.path)
        # Stage 8: Validate prepaid/postpaid/normal payment types
        if payment_type == 'prepaid':
            # Prepaid: collected must exceed adjusted total
            if collected_amount < adjusted_total:
                messages.error(request, f"For prepaid payment, collected amount must be greater than or equal to adjusted total rent amount (¥{adjusted_total}).")
                return redirect(request.path)
            expected_prepaid = collected_amount - adjusted_total
            if abs(prepaid_amount - expected_prepaid) > Decimal("0.01"):
                messages.error(request, f"Prepaid amount should be {expected_prepaid} (excess of collected amount over adjusted total rent).")
                return redirect(request.path)
        elif payment_type == 'postpaid':
            # Postpaid: collected must be less than adjusted total
            if collected_amount >= adjusted_total:
                messages.error(request, f"For postpaid payment, collected amount must be less than adjusted total rent amount (¥{adjusted_total}).")
                return redirect(request.path)
            expected_postpaid = adjusted_total - collected_amount
            if abs(prepaid_amount - expected_postpaid) > Decimal("0.01"):
                messages.error(request, f"Postpaid amount should be {expected_postpaid} (shortfall of adjusted total rent over collected amount).")
                return redirect(request.path)
        elif payment_type == '' and collected_amount == 0:
            # Normal payment: set collected to adjusted total
            collected_amount = adjusted_total
        elif payment_type == '' and abs(collected_amount - adjusted_total) > Decimal("0.01"):
            messages.error(request, f"For normal payment, collected amount must equal amount to collect (¥{adjusted_total}).")
            return redirect(request.path)
        # Stage 9: Create/update revenue record
        revenue, created = HostelRevenue.objects.get_or_create(
            title="rent", customer=customer_details.customer, year=year, month=month,
            defaults={"rent": base_rent, "rent_discount_percent": rent_discount_percent, "rent_after_discount": rent_after_discount, "internet": internet_fee, "utilities": utilities_fee, "total_amount": total_amount, "payment_type": payment_type, "collected_amount": collected_amount, "prepaid_amount": prepaid_amount if payment_type else None, "memo": memo, "created_by": request.user, "updated_by": request.user,}
        )
        if not created:
            messages.warning(request, "Rent payment for this month already exists.")
        else:
            customer = revenue.customer
            if customer and customer.email:
                try:
                    send_revenue_email(request, revenue, subject='Rent Payment Notification - TNA  Group Limited')
                except Exception as e:
                    print("EMAIL ERROR (view level):", e)
            messages.success(request, "Monthly rent payment recorded successfully.")
        return redirect("finance:revenues")
    can_edit_fees = request.user.has_perm('finance.change_hostelrevenue') or request.user.is_superuser
    if request.method == "GET":
        previous_prepaid = Decimal('0')
        previous_postpaid = Decimal('0')
    else:
        previous_prepaid = get_previous_prepaid_amount(customer_details.customer, year, month)
        previous_postpaid = Decimal('0')
        prev_month = month - 1
        prev_year = year
        if prev_month <= 0:
            prev_month = 12
            prev_year = year - 1
        try:
            prev_revenue = HostelRevenue.objects.get(title='rent', customer=customer_details.customer, year=prev_year, month=prev_month)
            if prev_revenue.payment_type == 'postpaid' and prev_revenue.prepaid_amount:
                previous_postpaid = prev_revenue.prepaid_amount
        except HostelRevenue.DoesNotExist:
            previous_postpaid = Decimal('0')
    had_postpaid_last_month = False
    registration_payment = HostelRevenue.objects.filter(title='registration_fee', customer=customer_details.customer).first()
    existing_rent_payments = HostelRevenue.objects.filter(title='rent', customer=customer_details.customer).order_by('year', 'month')
    last_rent_payment = existing_rent_payments.last() if existing_rent_payments.exists() else None
    return render(request, 'finance/monthly_rent.html', {
        'customer_details': customer_details,
        'can_edit_fees': can_edit_fees,
        'previous_prepaid_amount': previous_prepaid,
        'previous_postpaid_amount': previous_postpaid,
        'had_postpaid_last_month': had_postpaid_last_month,
        'registration_payment': registration_payment,
        'existing_rent_payments': existing_rent_payments,
        'last_rent_payment': last_rent_payment
    })


@login_required(login_url='/accounts/login/')
def get_prepaid_amount_for_month(request, customer_id):
    """AJAX endpoint to get previous month's prepaid/postpaid for a selected month"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            year = int(data.get('year'))
            month = int(data.get('month'))
            # Calculate previous month
            prev_month = month - 1
            prev_year = year
            if prev_month <= 0:
                prev_month = 12
                prev_year = year - 1
            # Get customer
            customer = get_object_or_404(Bed.objects.select_related('customer'), customer=customer_id).customer
            previous_prepaid = Decimal('0')
            previous_postpaid = Decimal('0')
            had_postpaid_last_month = False
            try:
                prev_revenue = HostelRevenue.objects.get(title='rent', customer=customer, year=prev_year, month=prev_month)
                if prev_revenue.payment_type == 'prepaid' and prev_revenue.prepaid_amount:
                    previous_prepaid = prev_revenue.prepaid_amount
                elif prev_revenue.payment_type == 'postpaid' and prev_revenue.prepaid_amount:
                    previous_postpaid = prev_revenue.prepaid_amount
                    had_postpaid_last_month = True
            except HostelRevenue.DoesNotExist:
                pass
            return JsonResponse({'success': True, 'previous_prepaid': float(previous_prepaid), 'previous_postpaid': float(previous_postpaid), 'had_postpaid_last_month': had_postpaid_last_month, 'previous_month': f"{prev_year}-{prev_month:02d}"})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required(login_url='/accounts/login/')
def validate_rent_month(request, customer_id):
    """AJAX endpoint to validate rent payment month selection"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            year = int(data.get('year'))
            month = int(data.get('month'))
            # Get customer
            customer = get_object_or_404(Bed.objects.select_related('customer'), customer=customer_id).customer
            # 1. Registration Fee Validation
            registration_payment = HostelRevenue.objects.filter(title='registration_fee', customer=customer).first()
            if not registration_payment:
                return JsonResponse({'success': False, 'error': 'Customer must pay registration fee before making rent payments.', 'error_type': 'registration_required'})
            # 2. Get all existing rent payments for this customer
            existing_rent_payments = HostelRevenue.objects.filter(title='rent', customer=customer).order_by('year', 'month')
            # 3. Check for duplicate payment
            duplicate_payment = existing_rent_payments.filter(year=year, month=month).first()
            if duplicate_payment:
                return JsonResponse({'success': False, 'error': f'Payment for {year}-{month:02d} already exists. Please select a different month.', 'error_type': 'duplicate_payment'})
            # 4. First rent payment validation
            if not existing_rent_payments.exists():
                reg_year = registration_payment.year
                reg_month = registration_payment.month
                if year != reg_year or month != reg_month:
                    return JsonResponse({'success': False, 'error': f'First rent payment must be in the registration month. Customer registered in {reg_year}-{reg_month:02d}. First rent payment should be for {reg_year}-{reg_month:02d}.', 'error_type': 'wrong_first_month', 'suggested_month': f'{reg_year}-{reg_month:02d}'})
            else:
                # Not first payment - validate sequential payment
                last_payment = existing_rent_payments.last()
                last_year = last_payment.year
                last_month = last_payment.month
                # Calculate expected next month
                expected_month = last_month + 1
                expected_year = last_year
                if expected_month > 12:
                    expected_month = 1
                    expected_year += 1
                # Check if trying to pay for a month before the last payment
                if year < last_year or (year == last_year and month < last_month):
                    return JsonResponse({'success': False, 'error': f'Cannot pay rent for a month before the last payment. Last payment was for {last_year}-{last_month:02d}.', 'error_type': 'backward_payment', 'last_payment': f'{last_year}-{last_month:02d}'})
                # Check if trying to skip months
                if year != expected_year or month != expected_month:
                    return JsonResponse({'success': False, 'error': f'Cannot skip months. Last payment was for {last_year}-{last_month:02d}. Next payment should be for {expected_year}-{expected_month:02d}.', 'error_type': 'skip_months', 'last_payment': f'{last_year}-{last_month:02d}', 'suggested_month': f'{expected_year}-{expected_month:02d}'})
            # If we get here, validation passed
            return JsonResponse({'success': True, 'message': 'Month selection is valid.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Validation error: {str(e)}', 'error_type': 'system_error'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required(login_url='/accounts/login/')
def registration_fee(request, customer_id):
    """
    Handle initial registration fee payment with deposit and initial fee components.
    Validates required hostel fees and manages discount/memo requirements.
    """
    customer_details = get_object_or_404(Bed.objects.select_related('unit', 'unit__hostel', 'customer'), customer=customer_id)
    # Validate required hostel fees are configured
    missing_fees = []
    if not customer_details.unit.hostel.deposit_fee or customer_details.unit.hostel.deposit_fee == 0:
        missing_fees.append("Deposit Fee")
    if not customer_details.unit.hostel.initial_fee or customer_details.unit.hostel.initial_fee == 0:
        missing_fees.append("Initial Fee")
    if missing_fees:
        messages.error(request, f"Please add {', '.join(missing_fees)} in hostel details. You cannot process without these fees.")
        return redirect('customer:customer_detail', customer_id)
    if request.method == "POST":
        # Parse registration month
        month_input = request.POST.get("reg_month")
        if not month_input:
            messages.error(request, "Payment month is required.")
            return redirect(request.path)
        try:
            year, month = map(int, month_input.split("-"))
        except ValueError:
            messages.error(request, "Invalid month format.")
            return redirect(request.path)
        # Parse numeric amounts
        try:
            deposit = Decimal(request.POST.get("deposit", "0"))
            deposit_discount = Decimal(request.POST.get("deposit_discount_percent", "0"))
            initial = Decimal(request.POST.get("initial_fee", "0"))
            initial_discount = Decimal(request.POST.get("initial_fee_discount_percent", "0"))
        except InvalidOperation:
            messages.error(request, "Invalid numeric values.")
            return redirect(request.path)
        # Calculate deposit and initial fee after discounts
        deposit_after = deposit * (Decimal(1) - deposit_discount / Decimal(100))
        initial_after = initial * (Decimal(1) - initial_discount / Decimal(100))
        total = deposit_after + initial_after
        # Validate memo requirement for discounted amounts
        memo = request.POST.get("memo", "").strip()
        if (deposit_discount > 0 or initial_discount > 0) and not memo:
            messages.error(request, "Memo is required when a discount is applied.")
            return redirect(request.path)
        # Create registration fee revenue record
        revenue, created = HostelRevenue.objects.get_or_create(
            title="registration_fee", customer=customer_details.customer, year=year, month=month,
            defaults={"deposit": deposit, "deposit_discount_percent": deposit_discount, "deposit_after_discount": deposit_after, "initial_fee": initial, "initial_fee_discount_percent": initial_discount, "initial_fee_after_discount": initial_after, "total_amount": total, "memo": memo, "created_by": request.user, "updated_by": request.user,}
        )
        if not created:
            messages.warning(request, "Registration fee for this month already exists.")
        else:
            customer = revenue.customer
            if customer and customer.email:
                try:
                    send_revenue_email(request, revenue, subject='Registration Fee Notification - TNA  Group Limited')
                except Exception as e:
                    print("EMAIL ERROR (view level):", e)
            messages.success(request, "Registration fee payment recorded successfully.")
        return redirect("finance:revenues")
    can_edit_fees = request.user.has_perm('finance.change_hostelrevenue') or request.user.is_superuser
    return render(request, 'finance/registration_fee.html', {'customer_details': customer_details, 'can_edit_fees': can_edit_fees})


@login_required(login_url='/accounts/login/')
def notification(request):
    """
    Rent defaulters dashboard - shows customers with unpaid rent months.
    Allows searching by customer name and downloading unpaid rent report to Excel.
    """
    search_name = request.GET.get('name', '').strip().lower()
    # Get all rent defaulters from helper function
    defaulters = get_rent_defaulters()
    # Filter by search name if provided
    if search_name:
        defaulters = [d for d in defaulters if search_name in d['customer'].name.lower()]
    # Handle Excel export
    if 'download' in request.GET:
        return export_unpaid_rent_to_excel(defaulters)
    return render(request, 'finance/notification.html', {'defaulters': defaulters, 'search_name': request.GET.get('name', ''), 'today': date.today()})


@login_required(login_url='/accounts/login/')
@permission_required(('finance.view_hostelexpense', 'finance.view_utilityexpense'), raise_exception=True)
def expenses(request):
    """
    Unified expenses dashboard combining hostel and utility expenses.
    Supports filtering by date, status, expense type, hostel, and Excel export.
    """
    # Parse filter parameters
    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()
    status = request.GET.get('status')
    expense_type = request.GET.get('expense_type')
    hostel_filter = request.GET.get('hostel')
    export = request.GET.get('export')
    # Get base querysets
    hostel_expenses = HostelExpense.objects.select_related('hostel', 'created_by', 'updated_by', 'approved_by')
    utility_expenses = UtilityExpense.objects.select_related('hostel', 'paid_by', 'approved_by')
    # Default to the current month and filter by the selected date range.
    today = timezone.now().date()
    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date() if from_date_str else today.replace(day=1)
    except ValueError:
        from_date = today.replace(day=1)
    try:
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date() if to_date_str else today
    except ValueError:
        to_date = today

    hostel_expenses = hostel_expenses.filter(purchased_date__range=(from_date, to_date))
    utility_expenses = utility_expenses.filter(paid_date__range=(from_date, to_date))
    # Filter by approval status
    if status in ['approved', 'pending', 'rejected']:
        hostel_expenses = hostel_expenses.filter(status=status)
        utility_expenses = utility_expenses.filter(approval_status=status.upper())
    # Filter by expense type (hostel vs utility)
    if expense_type == 'hostel':
        utility_expenses = utility_expenses.none()
    elif expense_type == 'utility':
        hostel_expenses = hostel_expenses.none()
    # Filter by hostel name
    if hostel_filter:
        hostel_expenses = hostel_expenses.filter(hostel__name__icontains=hostel_filter)
        utility_expenses = utility_expenses.filter(hostel__name__icontains=hostel_filter)
    # Combine hostel and utility expenses into unified list
    combined_expenses = []
    for expense in hostel_expenses:
        combined_expenses.append({'id': expense.id, 'type': 'hostel', 'transaction_code': expense.transaction_code, 'date': expense.purchased_date, 'date_display': expense.purchased_date.strftime('%b %d, %Y') if expense.purchased_date else 'N/A', 'hostel': expense.hostel.name if expense.hostel else "ALL", 'purchased_by': expense.purchased_by, 'memo': expense.memo, 'amount': expense.amount, 'status': expense.status, 'approved_by': expense.approved_by, 'created_by': expense.created_by, 'created_at': expense.created_at, 'updated_by': expense.updated_by, 'updated_at': expense.updated_at,})
    for expense in utility_expenses:
        # Build date display with utility billing period information
        billing_date = date(expense.billing_year, expense.billing_month, 1) if expense.billing_year and expense.billing_month else None
        date_display = f"{expense.paid_date.strftime('%b %d, %Y') if expense.paid_date else 'N/A'}<br><small class='text-muted mb-0'>(Bill of {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][expense.billing_month-1]} {expense.billing_year})</small>" if expense.paid_date and expense.billing_year and expense.billing_month else (expense.paid_date.strftime('%b %d, %Y') if expense.paid_date else 'N/A')
        combined_expenses.append({'id': expense.id, 'type': expense.expense_type, 'transaction_code': f"UTIL-{expense.id:06d}", 'date': billing_date, 'date_display': date_display, 'hostel': expense.hostel.name, 'purchased_by': expense.paid_by.first_name if expense.paid_by else "N/A", 'memo': expense.description, 'amount': expense.amount, 'status': expense.approval_status.lower(), 'approved_by': expense.approved_by, 'created_by': expense.created_by, 'created_at': expense.created_at, 'updated_by': expense.updated_by, 'updated_at': expense.updated_at,})
    # Sort by date descending
    combined_expenses.sort(key=lambda x: x['date'] if x['date'] else date.min, reverse=True)
    # Calculate totals
    total_amount = sum([expense['amount'] if expense['amount'] is not None else Decimal('0') for expense in combined_expenses], Decimal('0'))
    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(combined_expenses, 25)
    page_obj = paginator.get_page(page_number)
    expenses_page = page_obj.object_list
    page_total_amount = sum([expense['amount'] if expense['amount'] is not None else Decimal('0') for expense in expenses_page], Decimal('0'))
    # Build query string for pagination links (without page parameter)
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    query_string = query_params.urlencode()
    # Handle Excel export
    if export == 'excel':
        return export_expenses_to_excel(combined_expenses)
    # Get all hostels for filter dropdown
    from hostel.models import Hostel
    all_hostels = Hostel.objects.filter(status=True).order_by('name')
    return render(request, 'finance/expenses_dashboard.html', {
        'expenses': expenses_page,
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'status': status,
        'expense_type': expense_type,
        'hostel_filter': hostel_filter,
        'all_hostels': all_hostels,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_records': paginator.count,
        'total_amount': total_amount,
        'page_total_amount': page_total_amount,
        'query_string': query_string,
    })

@login_required(login_url='/accounts/login/')
@permission_required('finance.add_hostelexpense', raise_exception=True)
def hostel_expense_create(request):
    """Create a new hostel expense record"""
    if request.method == 'POST':
        form = HostelExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Expense created successfully.")
            return redirect('finance:expenses')
    else:
        form = HostelExpenseForm()
    return render(request, 'finance/hostel_expense_form.html', {'form': form})


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_hostelexpense', raise_exception=True)
def hostel_expense_edit(request, pk):
    """Edit hostel expense - prevent editing approved expenses"""
    expense = get_object_or_404(HostelExpense, pk=pk)
    if expense.status == 'approved':
        messages.warning(request, "Approved expenses cannot be edited.")
        return redirect('finance:expenses')
    if request.method == 'POST':
        form = HostelExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Expense updated successfully.")
            return redirect('finance:expenses')
    else:
        form = HostelExpenseForm(instance=expense)
    return render(request, 'finance/hostel_expense_form.html', {'form': form})


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda u: u.is_superuser)
def hostel_expense_detail(request, pk):
    """View and update hostel expense approval status"""
    expense = get_object_or_404(HostelExpense, pk=pk)
    if request.method == 'POST':
        if expense.status == 'approved':
            messages.warning(request, "Approved hostel expenses cannot have their status changed.")
            return redirect('finance:hostel_expense_detail', pk=expense.pk)
        new_status = request.POST.get('status')
        if new_status in dict(HostelExpense.STATUS_CHOICES):
            expense.status = new_status
            if new_status == 'approved':
                expense.updated_by = request.user
                expense.approved_by = request.user
            else:
                expense.approved_by = None
            expense.save()
            messages.success(request, "Status updated successfully.")
            return redirect('finance:expenses')
    return render(request, 'finance/hostel_expense_detail.html', {'expense': expense})


@login_required(login_url='/accounts/login/')
@permission_required('finance.add_utilityexpense', raise_exception=True)
def utility_expense_create(request):
    """Create a new utility expense record with file upload"""
    if request.method == 'POST':
        form = UtilityExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.paid_by = request.user
            expense.created_by = request.user
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Utility expense created successfully.")
            return redirect('finance:expenses')
    else:
        form = UtilityExpenseForm()
    return render(request, 'finance/utility_expense_form.html', {'form': form})


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_utilityexpense', raise_exception=True)
def utility_expense_edit(request, pk):
    """Edit utility expense - prevent editing approved expenses"""
    expense = get_object_or_404(UtilityExpense, pk=pk)
    if expense.approval_status == 'APPROVED':
        messages.warning(request, "Approved utility expenses cannot be edited.")
        return redirect('finance:expenses')
    if request.method == 'POST':
        form = UtilityExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Utility expense updated successfully.")
            return redirect('finance:expenses')
    else:
        form = UtilityExpenseForm(instance=expense)
    return render(request, 'finance/utility_expense_form.html', {'form': form})


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda u: u.is_superuser)
def utility_expense_detail(request, pk):
    """View and update utility expense approval status"""
    expense = get_object_or_404(UtilityExpense, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('approval_status')
        if new_status in dict(UtilityExpense.ApprovalStatus.choices):
            expense.approval_status = new_status
            if new_status == 'APPROVED':
                expense.approved_by = request.user
            else:
                expense.approved_by = None
            expense.updated_by = request.user
            expense.save()
            messages.success(request, "Status updated successfully.")
            return redirect('finance:expenses')
    return render(request, 'finance/utility_expense_detail.html', {'expense': expense})





@login_required(login_url='/accounts/login/')
@permission_required('finance.view_thirdpartyservicerecord', raise_exception=True)
def third_party_services(request):
    service_type = request.GET.get('service_type', '').strip()
    status = request.GET.get('status', '').strip()
    applicant = request.GET.get('applicant', '').strip()
    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()
    today = timezone.now().date()

    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date() if from_date_str else today.replace(day=1)
    except ValueError:
        from_date = today.replace(day=1)
    try:
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date() if to_date_str else today
    except ValueError:
        to_date = today

    records = ThirdPartyServiceRecord.objects.select_related('created_by', 'updated_by').filter(
        Q(collected_date__range=(from_date, to_date)) |
        Q(remitted_date__range=(from_date, to_date))
    ).distinct()
    if service_type in dict(ThirdPartyServiceRecord.ServiceType.choices):
        records = records.filter(service_type=service_type)
    if status in dict(ThirdPartyServiceRecord.RemittanceStatus.choices):
        records = records.filter(remittance_status=status)
    if applicant:
        records = records.filter(Q(applicant_name__icontains=applicant) | Q(phone_number__icontains=applicant))

    records = records.order_by('-collected_date', '-created_at')
    for record in records:
        record.period_collected = record.collected_amount if from_date <= record.collected_date <= to_date else Decimal('0')
        record.period_remitted = (
            record.remitted_amount
            if record.remitted_date and from_date <= record.remitted_date <= to_date
            else Decimal('0')
        )
        record.period_commission = record.commission_amount if record.period_remitted else Decimal('0')

    if request.GET.get('export') == 'excel':
        return export_third_party_services_to_excel(records, from_date, to_date)

    total_collected = sum((record.period_collected for record in records), Decimal('0'))
    total_remitted = sum((record.period_remitted for record in records), Decimal('0'))
    total_commission = sum((record.period_commission for record in records), Decimal('0'))

    paginator = Paginator(records, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_total_collected = sum((record.period_collected for record in page_obj.object_list), Decimal('0'))
    page_total_remitted = sum((record.period_remitted for record in page_obj.object_list), Decimal('0'))
    page_total_commission = sum((record.period_commission for record in page_obj.object_list), Decimal('0'))

    overdue_cutoff = from_date.replace(day=1)
    overdue_remittances = ThirdPartyServiceRecord.objects.filter(
        remittance_status=ThirdPartyServiceRecord.RemittanceStatus.PENDING,
        collected_date__lt=overdue_cutoff,
    )
    if service_type in dict(ThirdPartyServiceRecord.ServiceType.choices):
        overdue_remittances = overdue_remittances.filter(service_type=service_type)
    if applicant:
        overdue_remittances = overdue_remittances.filter(
            Q(applicant_name__icontains=applicant) | Q(phone_number__icontains=applicant)
        )
    if status == ThirdPartyServiceRecord.RemittanceStatus.REMITTED:
        overdue_remittances = overdue_remittances.none()
    overdue_remittances = overdue_remittances.order_by('collected_date', 'created_at')
    overdue_remittance_count = overdue_remittances.count()
    overdue_collected_total = overdue_remittances.aggregate(total=Sum('collected_amount'))['total'] or Decimal('0')
    overdue_remittances = overdue_remittances[:20]
    for record in overdue_remittances:
        if record.collected_date.month == 12:
            record.remittance_due_date = date(record.collected_date.year + 1, 1, 1)
        else:
            record.remittance_due_date = date(record.collected_date.year, record.collected_date.month + 1, 1)

    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')

    return render(request, 'finance/third_party_services.html', {
        'records': page_obj,
        'page_obj': page_obj,
        'service_type': service_type,
        'status': status,
        'applicant': applicant,
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'service_type_choices': ThirdPartyServiceRecord.ServiceType.choices,
        'status_choices': ThirdPartyServiceRecord.RemittanceStatus.choices,
        'total_records': paginator.count,
        'total_collected': total_collected,
        'total_remitted': total_remitted,
        'total_commission': total_commission,
        'page_total_collected': page_total_collected,
        'page_total_remitted': page_total_remitted,
        'page_total_commission': page_total_commission,
        'overdue_remittances': overdue_remittances,
        'overdue_remittance_count': overdue_remittance_count,
        'overdue_collected_total': overdue_collected_total,
        'query_string': query_params.urlencode(),
    })


@login_required(login_url='/accounts/login/')
@permission_required('finance.add_thirdpartyservicerecord', raise_exception=True)
def third_party_service_create(request):
    if request.method == 'POST':
        form = ThirdPartyServiceRecordCreateForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.created_by = request.user
            record.updated_by = request.user
            record.save()
            messages.success(request, 'Insurance / guarantor record created successfully.')
            return redirect('finance:third_party_services')
    else:
        form = ThirdPartyServiceRecordCreateForm()
    return render(request, 'finance/third_party_service_form.html', {'form': form, 'is_create': True})


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_thirdpartyservicerecord', raise_exception=True)
def third_party_service_edit(request, pk):
    record = get_object_or_404(ThirdPartyServiceRecord, pk=pk)
    if record.remittance_status == ThirdPartyServiceRecord.RemittanceStatus.REMITTED:
        messages.warning(request, 'This transaction has already been sent to the company and cannot be edited.')
        return redirect('finance:third_party_service_detail', pk=record.pk)

    if request.method == 'POST':
        form = ThirdPartyServiceRecordUpdateForm(request.POST, instance=record)
        if form.is_valid():
            record = form.save(commit=False)
            record.updated_by = request.user
            record.save()
            messages.success(request, 'Insurance / guarantor record updated successfully.')
            return redirect('finance:third_party_services')
    else:
        form = ThirdPartyServiceRecordUpdateForm(instance=record)
    return render(request, 'finance/third_party_service_form.html', {'form': form, 'record': record, 'is_create': False})


@login_required(login_url='/accounts/login/')
@permission_required('finance.view_thirdpartyservicerecord', raise_exception=True)
def third_party_service_detail(request, pk):
    record = get_object_or_404(ThirdPartyServiceRecord.objects.select_related('created_by', 'updated_by'), pk=pk)
    remittance_form = None

    if record.remittance_status != ThirdPartyServiceRecord.RemittanceStatus.REMITTED and request.user.has_perm('finance.change_thirdpartyservicerecord'):
        if request.method == 'POST':
            remittance_form = ThirdPartyServiceRemittanceForm(request.POST, instance=record)
            if remittance_form.is_valid():
                record = remittance_form.save(commit=False)
                record.updated_by = request.user
                record.save()
                messages.success(request, 'Remittance was recorded successfully.')
                return redirect('finance:third_party_services')
        else:
            remittance_form = ThirdPartyServiceRemittanceForm(instance=record)

    return render(request, 'finance/third_party_service_detail.html', {'record': record, 'remittance_form': remittance_form})


@login_required(login_url='/accounts/login/')
def staff_expense_list(request):
    """List all staff expenses for the logged-in employee."""
    transaction_code = request.GET.get("transaction_code", "").strip().upper()
    from_date_str = request.GET.get("from_date")
    to_date_str = request.GET.get("to_date")
    status = request.GET.get("status")
    today = timezone.now().date()
    search_by_code = bool(transaction_code)
    search_ignores_dates = search_by_code or status in {"pending", "approved", "rejected"}

    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date() if from_date_str else today.replace(day=1)
    except ValueError:
        from_date = today.replace(day=1)
    try:
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date() if to_date_str else today
    except ValueError:
        to_date = today

    query = Q(employee=request.user)
    if search_by_code:
        query &= Q(transaction_code__icontains=transaction_code)
    if not search_ignores_dates:
        query &= Q(start_date__gte=from_date, start_date__lte=to_date)
    if status == "pending":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.PENDING)
    elif status == "approved":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.APPROVED)
    elif status == "rejected":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.REJECTED)

    expenses = StaffExpense.objects.select_related("approved_by").filter(query).order_by("-created_at")
    return render(request, "finance/staff_expense_list.html", {
        "expenses": expenses,
        "total_count": expenses.count(),
        "transaction_code": transaction_code,
        "search_by_code": search_by_code,
        "search_ignores_dates": search_ignores_dates,
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "status": status,
    })

@login_required(login_url='/accounts/login/')
def staff_expense_create(request):
    """Create a new staff expense request."""
    if request.method == "POST":
        form = StaffExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.employee = request.user
            expense.created_by = request.user
            expense.updated_by = request.user
            expense.approval_status = StaffExpense.ApprovalStatus.PENDING
            expense.save()
            messages.success(request, "Staff expense submitted successfully.")
            return redirect("finance:staff_expense_list")
    else:
        form = StaffExpenseForm()
    return render(request, "finance/staff_expense_form.html", {"form": form})


@login_required(login_url='/accounts/login/')
def staff_expense_edit(request, pk):
    """Edit a staff expense only while it is pending."""
    expense = get_object_or_404(StaffExpense, pk=pk, employee=request.user)
    if expense.approval_status != StaffExpense.ApprovalStatus.PENDING:
        messages.error(request, "This staff expense has already been processed and cannot be edited.")
        return redirect("finance:staff_expense_list")
    if request.method == "POST":
        form = StaffExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Staff expense updated successfully.")
            return redirect("finance:staff_expense_list")
    else:
        form = StaffExpenseForm(instance=expense)
    return render(request, "finance/staff_expense_form.html", {"form": form})


@login_required(login_url='/accounts/login/')
def staff_expense_dashboard(request):
    """Admin dashboard showing all staff expense requests with search and export."""
    can_view_staff_expenses = (
        request.user.is_superuser
        or request.user.has_perm("finance.view_staffexpense")
        or request.user.has_perm("finance.change_staffexpense")
    )
    if not can_view_staff_expenses:
        raise PermissionDenied

    employee_id = request.GET.get("employee", "").strip()
    transaction_code = request.GET.get("transaction_code", "").strip().upper()
    expense_type = request.GET.get("expense_type", "").strip().upper()
    from_date_str = request.GET.get("from_date")
    to_date_str = request.GET.get("to_date")
    status = request.GET.get("status")
    export = request.GET.get("export")
    today = timezone.now().date()
    User = get_user_model()
    employees = User.objects.filter(is_active=True).order_by("first_name", "last_name", "email")
    search_by_code = bool(transaction_code)
    search_ignores_dates = search_by_code

    if from_date_str:
        try:
            from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        except ValueError:
            from_date = today.replace(day=1)
    else:
        from_date = today.replace(day=1)
    if to_date_str:
        try:
            to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
        except ValueError:
            to_date = today
    else:
        to_date = today

    query = Q()
    if search_by_code:
        query &= Q(transaction_code__icontains=transaction_code)
    if not search_ignores_dates:
        query &= Q(updated_at__date__gte=from_date, updated_at__date__lte=to_date)
    if employee_id:
        try:
            query &= Q(employee_id=int(employee_id))
        except ValueError:
            pass
    valid_expense_types = {choice.value for choice in StaffExpense.ExpenseType}
    if expense_type in valid_expense_types:
        query &= Q(expense_type=expense_type)
    if status == "pending":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.PENDING)
    elif status == "approved":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.APPROVED)
    elif status == "rejected":
        query &= Q(approval_status=StaffExpense.ApprovalStatus.REJECTED)

    expenses = (
        StaffExpense.objects.select_related("employee", "approved_by", "created_by", "updated_by")
        .filter(query)
        .order_by("-updated_at")
    )

    total_count = expenses.count()
    overall_total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    query_params = request.GET.copy()
    if "export" in query_params:
        query_params.pop("export")
    if "page" in query_params:
        query_params.pop("page")
    query_string = query_params.urlencode()

    if export == "excel":
        if expenses.exists():
            return export_staff_expenses_to_excel(expenses)
        messages.warning(request, "No data available to export.")

    expenses_page = Paginator(expenses, 20).get_page(request.GET.get("page"))
    page_total_amount = expenses_page.object_list.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    context = {
        "expenses": expenses_page,
        "total_count": total_count,
        "page_total_amount": page_total_amount,
        "overall_total_amount": overall_total_amount,
        "employees": employees,
        "selected_employee": employee_id,
        "expense_types": StaffExpense.ExpenseType.choices,
        "selected_expense_type": expense_type,
        "transaction_code": transaction_code,
        "search_by_code": search_by_code,
        "search_ignores_dates": search_ignores_dates,
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "status": status,
        "query_string": query_string,
        "can_change_staff_expenses": (
            request.user.is_superuser
            or request.user.has_perm("finance.change_staffexpense")
        ),
    }
    return render(request, "finance/staff_expense_dashboard.html", context)


@login_required(login_url='/accounts/login/')
@permission_required('finance.change_staffexpense', raise_exception=True)
def staff_expense_update_status(request, pk):
    """Display and update only the approval status of a staff expense."""
    expense = get_object_or_404(StaffExpense, pk=pk)

    if expense.created_by_id == request.user.id or expense.employee_id == request.user.id:
        messages.error(request, "You cannot approve or reject a staff expense that you created.")
        return redirect("finance:staff_expense_dashboard")

    if request.method == "POST" and expense.approval_status != StaffExpense.ApprovalStatus.PENDING:
        messages.info(request, "Approved or rejected staff expenses cannot be updated.")
        return redirect("finance:staff_expense_dashboard")

    if request.method == "POST":
        new_status = request.POST.get("approval_status")
        valid_statuses = set(StaffExpense.ApprovalStatus.values)
        status_memo = request.POST.get("status_memo", "").strip()

        if new_status not in valid_statuses:
            messages.error(request, "Please select a valid approval status.")
        elif new_status == expense.approval_status:
            messages.info(request, "The staff expense already has that status.")
        elif not status_memo:
            messages.error(request, "Please enter a memo for this status change.")
        else:
            expense.approval_status = new_status
            expense.status_memo = status_memo
            expense.updated_by = request.user
            if new_status == StaffExpense.ApprovalStatus.PENDING:
                expense.approved_by = None
            else:
                expense.approved_by = request.user
            expense.save(update_fields=["approval_status", "status_memo", "approved_by", "updated_by", "updated_at"])
            messages.success(request, "Staff expense status updated successfully.")
        return redirect("finance:staff_expense_dashboard")

    return render(request, "finance/staff_expense_status_form.html", {"expense": expense})

from django.http import HttpResponse
import openpyxl


def export_to_excel(sheet_title, headers, rows, filename):
    """Build and return an Excel file download response."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(headers)
    for row in rows:
        ws.append(row)
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


def _user_display_name(user):
    if not user:
        return ""
    full_name = user.get_full_name() if hasattr(user, "get_full_name") else ""
    if full_name:
        return full_name
    if hasattr(user, "first_name") and user.first_name:
        return user.first_name
    if hasattr(user, "email") and user.email:
        return user.email
    return str(user)


def export_revenues_to_excel(queryset, record_type='rent'):
    if record_type == 'registration':
        sheet_title = "Registration Revenues"
        headers = [
            'Customer', 'Hostel', 'Unit', 'Bed', 'Revenue Year', 'Revenue Month',
            'Initial Fee', 'I. F. Discount (%)', 'I. F. After Discount', 'Deposit',
            'D. Discount (%)', 'D. After Discount', 'Total Amount', 'Created At', 'Created By',
        ]
    else:
        sheet_title = "Rent Revenues"
        headers = [
            'Customer', 'Hostel', 'Unit', 'Bed', 'Revenue Year', 'Revenue Month',
            'Internet', 'Utilities', 'Rent', 'Rent Discount (%)', 'Rent After Discount',
            'Total Amount', 'Payment Type', 'Collected Amount', 'Prepaid/Postpaid Amount',
            'Created At', 'Created By',
        ]

    rows = []
    for rev in queryset:
        customer = getattr(rev, 'customer', None)
        bed = getattr(customer, 'bed_assignment', None) if customer else None
        unit = getattr(bed, 'unit', None) if bed else None
        hostel = getattr(unit, 'hostel', None) if unit else None
        created_at = rev.created_at.strftime('%Y-%m-%d %H:%M') if rev.created_at else ''
        created_by_name = _user_display_name(rev.created_by)

        if record_type == 'registration':
            rows.append([
                customer.name if customer else '',
                hostel.name if hostel else '',
                unit.room_num if unit else '',
                bed.bed_num if bed else '',
                rev.year,
                rev.month,
                rev.initial_fee or '',
                rev.initial_fee_discount_percent or '',
                rev.initial_fee_after_discount or '',
                rev.deposit or '',
                rev.deposit_discount_percent or '',
                rev.deposit_after_discount or '',
                rev.total_amount or '',
                created_at,
                created_by_name,
            ])
        else:
            payment_type = (
                'Prepaid' if rev.payment_type == 'prepaid'
                else ('Postpaid' if rev.payment_type == 'postpaid' else 'Normal')
            )
            prepaid_postpaid_amount = ''
            if rev.payment_type and rev.prepaid_amount:
                prepaid_postpaid_amount = (
                    f'+{rev.prepaid_amount}' if rev.payment_type == 'prepaid'
                    else f'-{rev.prepaid_amount}'
                )
            rows.append([
                customer.name if customer else '',
                hostel.name if hostel else '',
                unit.room_num if unit else '',
                bed.bed_num if bed else '',
                rev.year,
                rev.month,
                rev.internet or '',
                rev.utilities or '',
                rev.rent or '',
                rev.rent_discount_percent or '',
                rev.rent_after_discount or '',
                rev.total_amount or '',
                payment_type,
                rev.collected_amount or '',
                prepaid_postpaid_amount,
                created_at,
                created_by_name,
            ])

    return export_to_excel(sheet_title, headers, rows, f"{record_type}_revenues.xlsx")


def export_expenses_to_excel(combined_expenses):
    headers = [
        "Type", "ID", "Date", "Hostel", "Purchased By", "Approved By",
        "Amount", "Status", "Memo", "Created By", "Created At", "Updated By", "Updated At",
    ]
    rows = []
    for expense in combined_expenses:
        date_value = expense['date'].strftime('%Y-%m-%d') if expense.get('date') else expense.get('date_display', 'N/A')
        approved_name = _user_display_name(expense.get('approved_by')) or "-"
        rows.append([
            expense['type'].title(),
            expense['transaction_code'],
            date_value,
            expense['hostel'],
            expense['purchased_by'],
            approved_name,
            float(expense['amount']) if expense['amount'] is not None else '',
            expense['status'],
            expense['memo'] or "-",
            str(expense['created_by']) if expense['created_by'] else "-",
            expense['created_at'].strftime('%Y-%m-%d %H:%M:%S') if expense['created_at'] else "-",
            str(expense['updated_by']) if expense['updated_by'] else "-",
            expense['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if expense['updated_at'] else "-",
        ])
    return export_to_excel("All Expenses", headers, rows, "all_expenses.xlsx")


def export_travel_expenses_to_excel(queryset):
    headers = [
        "Transaction Code", "Employee", "Start Date", "End Date", "Amount",
        "Memo", "Status", "Approved By", "Created By", "Created At",
    ]
    rows = []
    for expense in queryset:
        rows.append([
            expense.transaction_code,
            _user_display_name(expense.employee),
            expense.start_date.strftime("%Y-%m-%d") if expense.start_date else "",
            expense.end_date.strftime("%Y-%m-%d") if expense.end_date else "",
            float(expense.amount) if expense.amount is not None else "",
            expense.memo or "",
            expense.get_approval_status_display(),
            _user_display_name(expense.approved_by),
            _user_display_name(expense.created_by),
            expense.created_at.strftime("%Y-%m-%d %H:%M") if expense.created_at else "",
        ])
    return export_to_excel("Travel Expenses", headers, rows, "travel_expenses.xlsx")


def export_unpaid_rent_to_excel(defaulters):
    headers = ['Customer Name', 'Stay Type', 'Assigned Date', 'Released/End Date', 'Unpaid Months']
    rows = []
    for entry in defaulters:
        unpaid_str = ", ".join(f"{year}-{month:02d}" for year, month in entry['unpaid_months'])
        rows.append([
            entry['customer'].name,
            entry['type'].capitalize(),
            entry['assigned_date'],
            entry['end_date'],
            unpaid_str,
        ])
    return export_to_excel("Unpaid Rent", headers, rows, "unpaid_rent.xlsx")

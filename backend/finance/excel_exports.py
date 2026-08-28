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


def export_cash_flow_to_excel(entries, start_date, end_date):
    headers = [
        "Date", "Source", "Category", "Reference", "Description",
        "Cash Inflow", "Cash Outflow", "Running Balance",
    ]
    rows = [[
        entry["date"].strftime("%Y-%m-%d"), entry["source"], entry["category"],
        entry["reference"], entry["description"], float(entry["inflow"]),
        float(entry["outflow"]), float(entry["balance"]),
    ] for entry in entries]
    total_inflow = sum((entry["inflow"] for entry in entries), 0)
    total_outflow = sum((entry["outflow"] for entry in entries), 0)
    rows.append([
        "", "", "", "", "Period Total", float(total_inflow),
        float(total_outflow), float(total_inflow - total_outflow),
    ])
    return export_to_excel(
        "Cash Flow", headers, rows, f"cash_flow_{start_date}_{end_date}.xlsx"
    )


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


def export_staff_expenses_to_excel(queryset):
    headers = [
        "Transaction Code", "Employee", "Expense Type", "Start Date", "End Date", "Amount",
        "Expense Memo", "Status", "Status Change Memo", "Approved By", "Status Updated At", "Created By", "Created At",
    ]
    rows = []
    for expense in queryset:
        rows.append([
            expense.transaction_code,
            _user_display_name(expense.employee),
            expense.get_expense_type_display(),
            expense.start_date.strftime("%Y-%m-%d") if expense.start_date else "",
            expense.end_date.strftime("%Y-%m-%d") if expense.end_date else "",
            float(expense.amount) if expense.amount is not None else "",
            expense.memo or "",
            expense.get_approval_status_display(),
            expense.status_memo or "",
            _user_display_name(expense.approved_by),
            expense.updated_at.strftime("%Y-%m-%d %H:%M") if expense.approval_status != "PENDING" and expense.updated_at else "",
            _user_display_name(expense.created_by),
            expense.created_at.strftime("%Y-%m-%d %H:%M") if expense.created_at else "",
        ])
    return export_to_excel("Staff Expenses", headers, rows, "staff_expenses.xlsx")


def export_office_expenses_to_excel(queryset):
    headers = [
        "Transaction Code", "Expense Date", "Transaction Type", "Original Expense",
        "Category", "Other Category", "Vendor", "Description", "Amount",
        "Payment Mode", "Bank Account", "Credit Card", "Frequency",
        "Service Period Start", "Service Period End", "Memo", "Approval Status",
        "Decision Note", "Approved / Rejected By", "Decision Date",
        "Created By", "Created At", "Updated By", "Updated At",
    ]
    rows = []
    for item in queryset:
        rows.append([
            item.transaction_code,
            item.expense_date.strftime("%Y-%m-%d") if item.expense_date else "",
            item.get_transaction_kind_display(),
            item.original_expense.transaction_code if item.original_expense else "",
            item.get_category_display(), item.other_category, item.vendor, item.description,
            float(item.amount) if item.amount is not None else "",
            item.get_payment_mode_display(), str(item.bank_account or ""), str(item.credit_card or ""),
            item.get_frequency_display(),
            item.service_period_start.strftime("%Y-%m-%d") if item.service_period_start else "",
            item.service_period_end.strftime("%Y-%m-%d") if item.service_period_end else "",
            item.memo, item.get_approval_status_display(), item.status_memo,
            _user_display_name(item.approved_by),
            item.decided_at.strftime("%Y-%m-%d %H:%M") if item.decided_at else "",
            _user_display_name(item.created_by),
            item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
            _user_display_name(item.updated_by),
            item.updated_at.strftime("%Y-%m-%d %H:%M") if item.updated_at else "",
        ])
    return export_to_excel("Office Expenses", headers, rows, "office_expenses.xlsx")


def export_card_settlements_to_excel(queryset):
    headers = [
        "Transaction Code", "Bank Deduction Date", "Credit Card Paid",
        "Bank Account Charged", "Card Bill Period From", "Card Bill Period To",
        "Amount Deducted", "Approved Expense Total", "Difference", "Comparison",
        "Notes", "Approval Status", "Decision Note",
        "Approved / Rejected By", "Decision Date", "Created By", "Created At",
        "Updated By", "Updated At",
    ]
    rows = []
    for item in queryset:
        rows.append([
            item.transaction_code,
            item.settlement_date.strftime("%Y-%m-%d") if item.settlement_date else "",
            str(item.credit_card), str(item.bank_account),
            item.statement_period_start.strftime("%Y-%m-%d") if item.statement_period_start else "",
            item.statement_period_end.strftime("%Y-%m-%d") if item.statement_period_end else "",
            float(item.amount) if item.amount is not None else "",
            float(item.calculated_expense_total), float(item.amount_difference),
            "Matched" if item.is_amount_matched else "Not Matched", item.memo,
            item.get_approval_status_display(), item.status_memo,
            _user_display_name(item.approved_by),
            item.decided_at.strftime("%Y-%m-%d %H:%M") if item.decided_at else "",
            _user_display_name(item.created_by),
            item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
            _user_display_name(item.updated_by),
            item.updated_at.strftime("%Y-%m-%d %H:%M") if item.updated_at else "",
        ])
    return export_to_excel("Card Bill Payments", headers, rows, "credit_card_bill_payments.xlsx")


def export_pending_ad_fees_to_excel(queryset):
    headers = ['Customer', 'Phone', 'Contract Date', 'Property Address', 'Partner / Management Company', 'Expected AD Fee']
    rows = [[
        contract.customer_name, contract.customer_number,
        contract.contract_date.strftime('%Y-%m-%d'), contract.building_address,
        contract.management_company_name, float(contract.ad_fee),
    ] for contract in queryset]
    return export_to_excel('Pending AD Fees', headers, rows, 'pending_ad_fee_receipts.xlsx')


def export_real_estate_revenue_to_excel(queryset, from_date, to_date):
    headers = ['Contract Date', 'Customer', 'Phone', 'Property Address', 'Partner / Management Company', 'Agent Revenue', 'Expected AD Fee', 'AD Status', 'Received Date', 'Received AD Fee', 'Transfer Fee', 'Period Revenue']
    rows = []
    for contract in queryset:
        agent_revenue = contract.agent_fee if from_date <= contract.contract_date <= to_date else 0
        received_ad_fee = contract.ad_fee_received_amount if contract.ad_fee_received_date and from_date <= contract.ad_fee_received_date <= to_date else 0
        period_revenue = agent_revenue + (received_ad_fee or 0)
        rows.append([
            contract.contract_date.strftime('%Y-%m-%d'), contract.customer_name, contract.customer_number,
            contract.building_address, contract.management_company_name, float(agent_revenue), float(contract.ad_fee),
            'Confirmed (No AD Fee)' if not contract.ad_fee else ('Received' if contract.ad_fee_confirmed_at else 'Pending'),
            contract.ad_fee_received_date.strftime('%Y-%m-%d') if contract.ad_fee_received_date else '',
            float(contract.ad_fee_received_amount) if contract.ad_fee_received_amount is not None else (0 if not contract.ad_fee else ''),
            float(contract.ad_fee_transfer_fee) if contract.ad_fee_confirmed_at or not contract.ad_fee else '', float(period_revenue),
        ])
    return export_to_excel('Real Estate Revenue', headers, rows, f'real_estate_revenue_{from_date}_{to_date}.xlsx')


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


def export_third_party_services_to_excel(queryset, from_date, to_date):
    headers = [
        "Transaction ID", "Service", "Applicant Name", "Applicant Phone", "Applicant Address",
        "Insurance For", "Insurance Address", "Guarantor / Insurance Company", "Company Phone",
        "Collected Amount", "Collected Date", "Remittance Amount", "Remittance Date",
        "Commission Amount", "Remittance Status", "Memo", "Created By", "Created At",
    ]
    rows = []
    for record in queryset:
        rows.append([
            record.transaction_code,
            record.get_service_type_display(),
            record.applicant_name,
            record.phone_number,
            record.applicant_address,
            record.get_service_subject_type_display() if record.service_type == "INSURANCE" else "",
            record.service_subject_address if record.service_type == "INSURANCE" else "",
            record.company_name,
            record.company_phone_number,
            float(record.collected_amount) if record.collected_amount is not None else "",
            record.collected_date.strftime("%Y-%m-%d") if record.collected_date else "",
            float(record.remitted_amount) if record.remitted_amount is not None else "",
            record.remitted_date.strftime("%Y-%m-%d") if record.remitted_date else "",
            float(record.commission_amount),
            record.get_remittance_status_display(),
            record.memo,
            _user_display_name(record.created_by),
            record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "",
        ])
    return export_to_excel("Insurance Guarantor", headers, rows, f"insurance_guarantor_{from_date}_{to_date}.xlsx")

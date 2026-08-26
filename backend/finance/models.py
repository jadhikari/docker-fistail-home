from django.db import models
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from hostel.models import Hostel
from customer.models import Customer
import datetime
import string
import random
import secrets

User = get_user_model()

class TimeStampedUserModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created_by",
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated_by",
        null=True,
        blank=True
    )


    class Meta:
        abstract = True


def current_year():
    return datetime.date.today().year

def year_choices():
    return [(r, r) for r in range(2000, datetime.date.today().year + 10)]


class HostelRevenue(TimeStampedUserModel):
    REVENUE_TYPE_CHOICES = [
        ('registration_fee', 'Registration Fee'),
        ('rent', 'Rent'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('', 'Normal Payment'),
        ('prepaid', 'Prepaid Payment'),
        ('postpaid', 'Postpaid Payment'),
    ]

    title = models.CharField(max_length=20, choices=REVENUE_TYPE_CHOICES)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    year = models.IntegerField(choices=year_choices(), default=current_year)  # type: ignore
    month = models.IntegerField(choices=[(i, i) for i in range(1, 13)])

    # Fields for registration fee
    deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deposit_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    deposit_after_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    initial_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    initial_fee_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    initial_fee_after_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Fields for rent
    internet = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    utilities = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rent_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rent_after_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Prepaid/Postpaid fields for rent
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, default='', blank=True)
    prepaid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                       help_text="Amount paid in advance (for prepaid) or amount carried forward (for postpaid)")
    collected_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         help_text="Actual amount collected from customer")

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    memo = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'customer', 'year', 'month'],
                name='unique_revenue_transaction'
            )
        ]

    def clean(self):
        if self.title == 'registration_fee':
            if self.deposit is None or self.initial_fee is None:
                raise ValidationError('Deposit and Initial Fee are required for Registration Fee.')
        elif self.title == 'rent':
            if self.internet is None or self.utilities is None or self.rent is None:
                raise ValidationError('Internet, Utilities, and Rent are required for Rent.')
            
            # Validate prepaid/postpaid logic for rent
            if self.payment_type and self.collected_amount and self.prepaid_amount:
                rent_total = (self.rent_after_discount or self.rent or Decimal("0")) + (self.internet or Decimal("0")) + (self.utilities or Decimal("0"))
                
                if self.payment_type == 'prepaid':
                    # For prepaid: collected_amount should be >= total_amount
                    if self.collected_amount < rent_total:
                        raise ValidationError('For prepaid payment, collected amount must be greater than or equal to total rent amount.')
                    # prepaid_amount should be the excess amount
                    expected_prepaid = self.collected_amount - rent_total
                    if abs(self.prepaid_amount - expected_prepaid) > Decimal("0.01"):  # Allow small rounding differences
                        raise ValidationError(f'Prepaid amount should be {expected_prepaid} (excess of collected amount over total rent).')
                        
                elif self.payment_type == 'postpaid':
                    # For postpaid: collected_amount should be < total_amount
                    if self.collected_amount >= rent_total:
                        raise ValidationError('For postpaid payment, collected amount must be less than total rent amount.')
                    # prepaid_amount should be the shortfall amount
                    expected_postpaid = rent_total - self.collected_amount
                    if abs(self.prepaid_amount - expected_postpaid) > Decimal("0.01"):  # Allow small rounding differences
                        raise ValidationError(f'Postpaid amount should be {expected_postpaid} (shortfall of total rent over collected amount).')
                        
            elif self.payment_type and not self.collected_amount:
                raise ValidationError('Collected amount is required when payment type is specified.')
            elif self.payment_type and not self.prepaid_amount:
                raise ValidationError('Prepaid/Postpaid amount is required when payment type is specified.')

    def save(self, *args, **kwargs):
        if self.deposit and self.deposit_discount_percent is not None:
            self.deposit_after_discount = self.deposit * (Decimal(1) - self.deposit_discount_percent / Decimal(100))  # type: ignore

        if self.initial_fee and self.initial_fee_discount_percent is not None:
            self.initial_fee_after_discount = self.initial_fee * (Decimal(1) - self.initial_fee_discount_percent / Decimal(100))  # type: ignore

        if self.rent and self.rent_discount_percent is not None:
            self.rent_after_discount = self.rent * (Decimal(1) - self.rent_discount_percent / Decimal(100))  # type: ignore

        
        # Safely calculate total_amount
        rent_total = (self.rent_after_discount or Decimal("0")) + (self.internet or Decimal("0")) + (self.utilities or Decimal("0")) # type: ignore
        registration_total = (self.deposit_after_discount or Decimal("0")) + (self.initial_fee_after_discount or Decimal("0")) # type: ignore

        if self.title == 'rent':
            # For rent, total_amount is the calculated rent amount
            # collected_amount is the actual amount paid by customer
            self.total_amount = rent_total
            
            # Handle prepaid/postpaid logic
            if self.payment_type == 'prepaid' and self.collected_amount and self.prepaid_amount:
                # For prepaid: collected_amount should be >= total_amount
                # prepaid_amount is the excess amount paid in advance
                pass  # Validation handled in clean method
            elif self.payment_type == 'postpaid' and self.collected_amount and self.prepaid_amount:
                # For postpaid: collected_amount should be < total_amount
                # prepaid_amount is the shortfall amount carried forward
                pass  # Validation handled in clean method
            elif not self.payment_type:
                # Normal payment: collected_amount should equal total_amount
                if not self.collected_amount:
                    self.collected_amount = self.total_amount
                    
        elif self.title == 'registration_fee':
            self.total_amount = registration_total
            if not self.collected_amount:
                self.collected_amount = self.total_amount
        else:
            self.total_amount = Decimal("0")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_title_display()} for {self.customer}" # type: ignore


class HostelExpense(TimeStampedUserModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, blank=True, null=True)
    purchased_date = models.DateField()
    purchased_by = models.CharField(max_length=255)
    memo = models.TextField()
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    transaction_code = models.CharField(max_length=6, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.transaction_code:
            self.transaction_code = self.generate_unique_code()
        if not self.status:
            self.status = 'pending'
        super().save(*args, **kwargs)

    def generate_unique_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(chars, k=6))
            if not HostelExpense.objects.filter(transaction_code=code).exists(): # type: ignore
                return code
    
    def __str__(self):
        hostel_name = self.hostel.name if self.hostel else "ALL"
        return f"[{self.transaction_code}] Expense by {self.purchased_by} on {self.purchased_date} for {hostel_name}"


class UtilityExpense(TimeStampedUserModel):
    class ExpenseType(models.TextChoices):
        INTERNET = 'INTERNET', 'Internet'
        WATER = 'WATER', 'Water'
        ELECTRICITY = 'ELECTRICITY', 'Electricity'
        GAS = 'GAS', 'Gas'

    class ApprovalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    hostel = models.ForeignKey('hostel.Hostel', on_delete=models.CASCADE, related_name='utility_expenses')
    expense_type = models.CharField(max_length=20, choices=ExpenseType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Total amount paid for the utility.')
    billing_year = models.IntegerField(choices=year_choices(), default=current_year, help_text='Year the utility bill was issued.') # type: ignore
    billing_month = models.IntegerField(choices=[(i, i) for i in range(1, 13)], help_text='Month the utility bill was issued.')
    date_from = models.DateField(verbose_name='Usage Start Date', help_text='Start date of the usage period.')
    date_to = models.DateField(verbose_name='Usage End Date', help_text='End date of the usage period.')
    paid_date = models.DateField(verbose_name='Paid Date', help_text='Date when the expense was paid.')
    usage_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Usage measured (e.g., kWh, m³, GB).')
    description = models.TextField(blank=True, help_text='Optional description or notes.')
    paid_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, help_text='User who recorded or paid the expense.')
    approved_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_utility_expenses', help_text='User who approved the expense.')
    approval_status = models.CharField(max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING, help_text='Approval status of the expense.')

    class Meta:
        ordering = ['-billing_year', '-billing_month']
        verbose_name = 'Utility Expense'
        verbose_name_plural = 'Utility Expenses'
        constraints = [
            models.UniqueConstraint(
                fields=['hostel', 'billing_year', 'billing_month', 'expense_type'],
                name='unique_utility_expense_per_hostel_year_month_type'
            )
        ]




    def __str__(self):
        return f"{self.get_expense_type_display()} | {self.hostel.name} | {self.amount}" # type: ignore


class StaffExpense(TimeStampedUserModel):

    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class ExpenseType(models.TextChoices):
        TRAVEL = "TRAVEL", "Travel"
        PURCHASE = "PURCHASE", "Purchase"
        OTHER = "OTHER", "Other"

    employee = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_expenses", help_text="Employee who submitted the staff expense.")
    approved_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_staff_expenses", help_text="User who approved or rejected the expense.")
    approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING, db_index=True, help_text="Current approval status of the staff expense.")
    expense_type = models.CharField(max_length=20, choices=ExpenseType.choices, default=ExpenseType.TRAVEL, help_text="Category of the staff expense.")
    start_date = models.DateField(help_text="Start date of the expense period.")
    end_date = models.DateField(help_text="End date of the expense period.")
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total staff expense amount.")
    memo = models.TextField(help_text="Additional information about the staff expense.")
    status_memo = models.TextField(blank=True, help_text="Memo recorded when the approval status is changed.")
    transaction_code = models.CharField(max_length=6, unique=True, editable=False, db_index=True, help_text="Unique transaction code for this staff expense.")

    def clean(self):
        super().clean()

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be earlier than start date."})

        if self.approval_status in [self.ApprovalStatus.APPROVED, self.ApprovalStatus.REJECTED] and not self.approved_by:
            raise ValidationError({"approved_by": "An approver is required."})

    def save(self, *args, **kwargs):
        if not self.transaction_code:
            self.transaction_code = self.generate_unique_code()

        self.full_clean()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_code():
        chars = string.ascii_uppercase + string.digits

        while True:
            code = "".join(secrets.choice(chars) for _ in range(6))

            if not StaffExpense.objects.filter(transaction_code=code).exists():
                return code

    def __str__(self):
        if self.employee:
            full_name = self.employee.get_full_name()
            return f"{self.transaction_code} - {full_name or self.employee.username}"

        return self.transaction_code

    class Meta:
        verbose_name = "Staff Expense"
        verbose_name_plural = "Staff Expenses"


class ThirdPartyServiceRecord(TimeStampedUserModel):
    class ServiceType(models.TextChoices):
        INSURANCE = "INSURANCE", "Insurance"
        GUARANTOR = "GUARANTOR", "Guarantor"

    class ServiceSubjectType(models.TextChoices):
        RESIDENT = "RESIDENT", "Resident"
        OFFICE_SHOP = "OFFICE_SHOP", "Office/Shop"
        RESTAURANT = "RESTAURANT", "Restaurant"

    class RemittanceStatus(models.TextChoices):
        PENDING = "PENDING", "Not Sent to Company"
        REMITTED = "REMITTED", "Sent to Company"

    transaction_code = models.CharField(max_length=8, unique=True, editable=False, db_index=True)
    service_type = models.CharField(max_length=20, choices=ServiceType.choices, db_index=True)
    applicant_name = models.CharField(max_length=120, help_text="Person who needs the insurance or guarantor service.")
    phone_number = models.CharField(max_length=20, default="")
    applicant_address = models.TextField(default="")
    service_subject_type = models.CharField(max_length=20, choices=ServiceSubjectType.choices, blank=True, help_text="Required for insurance records.")
    service_subject_address = models.TextField(blank=True, help_text="Required for insurance records.")
    company_name = models.CharField(max_length=150, help_text="Insurance or guarantor company.")
    company_phone_number = models.CharField(max_length=20, default="")
    collected_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount collected from the applicant.")
    collected_date = models.DateField(db_index=True)
    remitted_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Amount sent to the company.")
    remitted_date = models.DateField(null=True, blank=True)
    remittance_status = models.CharField(max_length=20, choices=RemittanceStatus.choices, default=RemittanceStatus.PENDING, db_index=True)
    memo = models.TextField()

    @property
    def commission_amount(self):
        return (self.collected_amount or Decimal("0.00")) - (self.remitted_amount or Decimal("0.00"))

    def clean(self):
        super().clean()
        errors = {}
        if not self.phone_number:
            errors["phone_number"] = "Customer phone number is required."
        if not self.applicant_address:
            errors["applicant_address"] = "Customer address is required."
        if not self.company_phone_number:
            errors["company_phone_number"] = "Company phone number is required."
        if not self.memo:
            errors["memo"] = "Memo is required."
        if self.collected_amount is not None and self.collected_amount <= 0:
            errors["collected_amount"] = "Collected amount must be greater than zero."
        if self.remitted_amount is not None and self.remitted_amount < 0:
            errors["remitted_amount"] = "Remitted amount cannot be negative."
        if self.collected_amount is not None and self.remitted_amount is not None and self.remitted_amount > self.collected_amount:
            errors["remitted_amount"] = "Remitted amount cannot be greater than collected amount."
        if self.remitted_amount and self.remitted_amount > 0 and not self.remitted_date:
            errors["remitted_date"] = "Remitted date is required when remitted amount is entered."
        if self.remitted_date and self.collected_date and self.remitted_date < self.collected_date:
            errors["remitted_date"] = "Remitted date cannot be before collected date."
        if self.service_type == self.ServiceType.INSURANCE:
            if not self.service_subject_type:
                errors["service_subject_type"] = "Insurance for what is required for insurance records."
            if not self.service_subject_address:
                errors["service_subject_address"] = "Address is required for insurance records."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.transaction_code:
            self.transaction_code = self.generate_unique_code()
        if self.remitted_amount is None:
            self.remitted_amount = Decimal("0.00")

        if self.remitted_amount == 0:
            self.remittance_status = self.RemittanceStatus.PENDING
        else:
            self.remittance_status = self.RemittanceStatus.REMITTED

        self.full_clean()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_code():
        chars = string.ascii_uppercase + string.digits

        while True:
            code = "TPS-" + "".join(secrets.choice(chars) for _ in range(4))

            if not ThirdPartyServiceRecord.objects.filter(transaction_code=code).exists():
                return code

    def __str__(self):
        return f"{self.transaction_code} - {self.applicant_name} - {self.get_service_type_display()}"

    class Meta:
        ordering = ["-collected_date", "-created_at"]
        verbose_name = "Insurance / Guarantor Record"
        verbose_name_plural = "Insurance / Guarantor Records"


class OfficeBankAccount(TimeStampedUserModel):
    name = models.CharField(max_length=100, unique=True)
    bank_name = models.CharField(max_length=100, blank=True)
    last_four_digits = models.CharField(max_length=4, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        if self.last_four_digits and (len(self.last_four_digits) != 4 or not self.last_four_digits.isdigit()):
            raise ValidationError({"last_four_digits": "Enter exactly four digits."})

    def __str__(self):
        suffix = f" ••••{self.last_four_digits}" if self.last_four_digits else ""
        return f"{self.name}{suffix}"


class OfficeCreditCard(TimeStampedUserModel):
    name = models.CharField(max_length=100, unique=True)
    issuer = models.CharField(max_length=100, blank=True)
    last_four_digits = models.CharField(max_length=4, blank=True)
    settlement_bank_account = models.ForeignKey(
        OfficeBankAccount, on_delete=models.PROTECT, null=True, blank=True,
        related_name="credit_cards",
    )
    closing_day = models.PositiveSmallIntegerField(null=True, blank=True)
    payment_day = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        errors = {}
        if self.last_four_digits and (len(self.last_four_digits) != 4 or not self.last_four_digits.isdigit()):
            errors["last_four_digits"] = "Enter exactly four digits."
        for field in ("closing_day", "payment_day"):
            value = getattr(self, field)
            if value is not None and not 1 <= value <= 31:
                errors[field] = "Enter a day between 1 and 31."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        suffix = f" ••••{self.last_four_digits}" if self.last_four_digits else ""
        return f"{self.name}{suffix}"


class OfficeExpense(TimeStampedUserModel):
    class Category(models.TextChoices):
        RENT = "RENT", "Office Rent"
        ELECTRICITY = "ELECTRICITY", "Office Electricity"
        WATER = "WATER", "Office Water"
        INTERNET = "INTERNET", "Internet"
        PHONE = "PHONE", "Phone"
        WEB_HOSTING = "WEB_HOSTING", "Web Server / Hosting"
        PARKING = "PARKING", "Parking"
        VEHICLE_INSURANCE = "VEHICLE_INSURANCE", "Vehicle Insurance"
        STAFF_INSURANCE = "STAFF_INSURANCE", "Staff Shakai Hoken"
        PRINTER_PURCHASE = "PRINTER_PURCHASE", "Printer Purchase"
        PRINTER_SUPPLIES = "PRINTER_SUPPLIES", "Printer Ink / Toner"
        PRINTING_SERVICE = "PRINTING_SERVICE", "Printing Service"
        SUBSCRIPTION = "SUBSCRIPTION", "Office Subscription"
        OFFICE_SUPPLIES = "OFFICE_SUPPLIES", "Office Supplies"
        BANK_CHARGE = "BANK_CHARGE", "Bank / Card Service Charge"
        OTHER = "OTHER", "Other"

    class PaymentMode(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK = "BANK", "Bank Account"
        CREDIT_CARD = "CREDIT_CARD", "Credit Card"

    class Frequency(models.TextChoices):
        ONE_TIME = "ONE_TIME", "One-time"
        MONTHLY = "MONTHLY", "Monthly"
        YEARLY = "YEARLY", "Yearly"
        IRREGULAR = "IRREGULAR", "Irregular"

    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class TransactionKind(models.TextChoices):
        EXPENSE = "EXPENSE", "Expense"
        REFUND = "REFUND", "Refund"

    transaction_code = models.CharField(max_length=10, unique=True, editable=False, db_index=True)
    transaction_kind = models.CharField(max_length=10, choices=TransactionKind.choices, default=TransactionKind.EXPENSE)
    original_expense = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="refunds")
    expense_date = models.DateField(db_index=True)
    category = models.CharField(max_length=30, choices=Category.choices, db_index=True)
    other_category = models.CharField(max_length=100, blank=True)
    vendor = models.CharField(max_length=150)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PaymentMode.choices, db_index=True)
    bank_account = models.ForeignKey(OfficeBankAccount, on_delete=models.PROTECT, null=True, blank=True, related_name="expenses")
    credit_card = models.ForeignKey(OfficeCreditCard, on_delete=models.PROTECT, null=True, blank=True, related_name="expenses")
    frequency = models.CharField(max_length=15, choices=Frequency.choices, default=Frequency.ONE_TIME)
    service_period_start = models.DateField(null=True, blank=True)
    service_period_end = models.DateField(null=True, blank=True)
    memo = models.TextField(blank=True)
    approval_status = models.CharField(max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING, db_index=True)
    status_memo = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_office_expenses")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]

    def clean(self):
        errors = {}
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "Amount must be greater than zero."
        if self.category == self.Category.OTHER and not self.other_category.strip():
            errors["other_category"] = "Describe the category when Other is selected."
        if self.category != self.Category.OTHER and self.other_category:
            errors["other_category"] = "Only use this field when the category is Other."
        if self.payment_mode == self.PaymentMode.BANK:
            if not self.bank_account:
                errors["bank_account"] = "Select the bank account used."
            if self.credit_card:
                errors["credit_card"] = "Do not select a credit card for a bank payment."
        elif self.payment_mode == self.PaymentMode.CREDIT_CARD:
            if not self.credit_card:
                errors["credit_card"] = "Select the credit card used."
            if self.bank_account:
                errors["bank_account"] = "The bank deduction is recorded later as a card settlement."
        elif self.bank_account or self.credit_card:
            errors["payment_mode"] = "Cash expenses cannot have a bank account or credit card."
        if self.service_period_start and self.service_period_end and self.service_period_end < self.service_period_start:
            errors["service_period_end"] = "Service period end cannot be before its start."
        if self.transaction_kind == self.TransactionKind.REFUND:
            if not self.original_expense:
                errors["original_expense"] = "Select the original expense for a refund."
            elif self.original_expense.transaction_kind != self.TransactionKind.EXPENSE:
                errors["original_expense"] = "A refund must link to an expense, not another refund."
            elif self.amount:
                previous_refunds = self.original_expense.refunds.exclude(pk=self.pk).exclude(
                    approval_status=self.ApprovalStatus.REJECTED
                ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
                if previous_refunds + self.amount > self.original_expense.amount:
                    errors["amount"] = "Refunds cannot exceed the original expense amount."
        elif self.original_expense:
            errors["original_expense"] = "Only refunds can link to an original expense."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            current = OfficeExpense.objects.filter(pk=self.pk).values_list("approval_status", flat=True).first()
            if current in (self.ApprovalStatus.APPROVED, self.ApprovalStatus.REJECTED):
                raise ValidationError("Approved or rejected office expenses are locked.")
        if not self.transaction_code:
            while True:
                code = "OE-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                if not OfficeExpense.objects.filter(transaction_code=code).exists():
                    self.transaction_code = code
                    break
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_code} - {self.vendor}"


class CreditCardSettlement(TimeStampedUserModel):
    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    transaction_code = models.CharField(max_length=10, unique=True, editable=False, db_index=True)
    credit_card = models.ForeignKey(OfficeCreditCard, on_delete=models.PROTECT, related_name="settlements")
    bank_account = models.ForeignKey(OfficeBankAccount, on_delete=models.PROTECT, related_name="card_settlements")
    settlement_date = models.DateField(db_index=True)
    statement_period_start = models.DateField(null=True, blank=False)
    statement_period_end = models.DateField(null=True, blank=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    calculated_expense_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), editable=False,
        help_text="Snapshot of approved card expenses less refunds for the selected bill period.",
    )
    matched_expenses = models.ManyToManyField(
        OfficeExpense, blank=True, related_name="card_bill_settlements",
    )
    memo = models.TextField(blank=True)
    approval_status = models.CharField(max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING, db_index=True)
    status_memo = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_card_settlements")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-settlement_date", "-created_at"]

    def clean(self):
        errors = {}
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "Amount must be greater than zero."
        if not self.statement_period_start:
            errors["statement_period_start"] = "Card bill period start is required."
        if not self.statement_period_end:
            errors["statement_period_end"] = "Card bill period end is required."
        if self.statement_period_start and self.statement_period_end and self.statement_period_end < self.statement_period_start:
            errors["statement_period_end"] = "Card bill period end cannot be before its start."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            current = CreditCardSettlement.objects.filter(pk=self.pk).values_list("approval_status", flat=True).first()
            if current in (self.ApprovalStatus.APPROVED, self.ApprovalStatus.REJECTED):
                raise ValidationError("Approved or rejected settlements are locked.")
        if not self.transaction_code:
            while True:
                code = "CC-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                if not CreditCardSettlement.objects.filter(transaction_code=code).exists():
                    self.transaction_code = code
                    break
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_code} - {self.credit_card}"

    @property
    def amount_difference(self):
        return (self.amount or Decimal("0.00")) - (self.calculated_expense_total or Decimal("0.00"))

    @property
    def is_amount_matched(self):
        return abs(self.amount_difference) <= Decimal("0.01")

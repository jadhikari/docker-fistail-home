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

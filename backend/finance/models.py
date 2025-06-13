from django.db import models
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from hostel.models import Hostel
from customer.models import Customer
import datetime
import string
import random

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

    title = models.CharField(max_length=20, choices=REVENUE_TYPE_CHOICES)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    year = models.IntegerField(choices=year_choices(), default=current_year)
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

    def save(self, *args, **kwargs):
        if self.deposit and self.deposit_discount_percent is not None:
            self.deposit_after_discount = self.deposit * (Decimal(1) - self.deposit_discount_percent / Decimal(100))

        if self.initial_fee and self.initial_fee_discount_percent is not None:
            self.initial_fee_after_discount = self.initial_fee * (Decimal(1) - self.initial_fee_discount_percent / Decimal(100))

        if self.rent and self.rent_discount_percent is not None:
            self.rent_after_discount = self.rent * (Decimal(1) - self.rent_discount_percent / Decimal(100))

        
        # Safely calculate total_amount
        rent_total = (self.rent_after_discount or Decimal("0")) + (self.internet or Decimal("0")) + (self.utilities or Decimal("0"))
        registration_total = (self.deposit_after_discount or Decimal("0")) + (self.initial_fee_after_discount or Decimal("0"))

        if self.title == 'rent':
            self.total_amount = rent_total
        elif self.title == 'registration_fee':
            self.total_amount = registration_total
        else:
            self.total_amount = Decimal("0")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_title_display()} for {self.customer}"


class HostelExpense(TimeStampedUserModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, blank=True, null=True)
    purchased_date = models.DateField()
    purchased_by = models.CharField(max_length=255)
    bill_url = models.TextField()
    memo = models.TextField()
    approved_by = models.CharField(max_length=255, blank=True, null=True)

    amount_before_tax = models.DecimalField(max_digits=10, decimal_places=2)
    amount_tax = models.DecimalField(max_digits=10, decimal_places=2)
    amount_total = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    transaction_code = models.CharField(max_length=6, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.transaction_code:
            self.transaction_code = self.generate_unique_code()
        if not self.status:
            self.status = 'pending'
        self.amount_total = (self.amount_before_tax or Decimal("0.00")) + (self.amount_tax or Decimal("0.00"))
        super().save(*args, **kwargs)

    def generate_unique_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(chars, k=6))
            if not HostelExpense.objects.filter(transaction_code=code).exists():
                return code
    
    def __str__(self):
        hostel_name = self.hostel.name if self.hostel else "ALL"
        return f"[{self.transaction_code}] Expense by {self.purchased_by} on {self.purchased_date} for {hostel_name}"

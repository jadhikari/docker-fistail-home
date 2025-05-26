from django.db import models
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from hostel.models import Hostel
from customer.models import Customer
import datetime

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


class Revenue(TimeStampedUserModel):
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

        if self.title == 'rent' and self.internet is not None and self.utilities is not None and self.rent_after_discount is not None:
            self.total_amount = self.rent_after_discount + self.internet + self.utilities

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_title_display()} for {self.customer}"


class Expense(TimeStampedUserModel):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE)
    purchased_date = models.DateField()
    purchased_by = models.CharField(max_length=255)
    bill_url = models.URLField()
    image_url = models.URLField()
    memo = models.TextField()

    amount_before_tax = models.DecimalField(max_digits=10, decimal_places=2)
    amount_tax = models.DecimalField(max_digits=10, decimal_places=2)
    amount_total = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.amount_total = (self.amount_before_tax or Decimal("0.00")) + (self.amount_tax or Decimal("0.00"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Expense by {self.purchased_by} on {self.purchased_date} for {self.hostel.name}"

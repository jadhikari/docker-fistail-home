from django.db import models
from django.contrib.auth import get_user_model
from customer.models import BedAssignment  # adjust the import if necessary

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

class Revenue(TimeStampedUserModel):
    REVENUE_TYPE_CHOICES = [
        ('registration_fee', 'Registration Fee'),
        ('rent', 'Rent'),
    ]

    title = models.CharField(max_length=20, choices=REVENUE_TYPE_CHOICES)
    customer = models.ForeignKey(BedAssignment, on_delete=models.CASCADE)

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

    memo = models.TextField(blank=True, null=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.title == 'registration_fee':
            if self.deposit is None or self.initial_fee is None:
                raise ValidationError('Deposit and Initial Fee are required for Registration Fee.')
        elif self.title == 'rent':
            if self.internet is None or self.utilities is None or self.rent is None:
                raise ValidationError('Internet, Utilities, and Rent are required for Rent.')

    def save(self, *args, **kwargs):
        # Calculate deposit after discount
        if self.deposit and self.deposit_discount_percent is not None:
            self.deposit_after_discount = self.deposit * (1 - self.deposit_discount_percent / 100)

        # Calculate initial fee after discount
        if self.initial_fee and self.initial_fee_discount_percent is not None:
            self.initial_fee_after_discount = self.initial_fee * (1 - self.initial_fee_discount_percent / 100)

        # Calculate rent after discount
        if self.rent and self.rent_discount_percent is not None:
            self.rent_after_discount = self.rent * (1 - self.rent_discount_percent / 100)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_title_display()} for {self.customer}"

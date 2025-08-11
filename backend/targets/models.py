from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
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


class Target(TimeStampedUserModel):
    """Model to store monthly targets assigned by super users to regular users"""
    
    # User who receives the target
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='assigned_targets',
        help_text="User who is assigned this target"
    )
    
    # Super user who assigned the target
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='targets_assigned',
        help_text="Super user who assigned this target"
    )
    
    # Target amount (monthly)
    target_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Monthly target amount in Japanese Yen"
    )
    
    # Month and year for the target
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    
    target_month = models.PositiveIntegerField(
        choices=MONTH_CHOICES,
        help_text="Target month (1-12)"
    )
    target_year = models.PositiveIntegerField(
        help_text="Target year"
    )
    
    # Status of the target
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active'
    )
    
    # Notes or description
    description = models.TextField(
        blank=True, 
        null=True,
        help_text="Additional notes about the target"
    )

    class Meta:
        # Ensure one target per user per month/year
        unique_together = ['user', 'target_month', 'target_year']
        ordering = ['-target_year', '-target_month', 'user__first_name']
        verbose_name = "Monthly Target"
        verbose_name_plural = "Monthly Targets"

    def __str__(self):
        return f"{self.user.first_name or self.user.email} - {self.target_month}/{self.target_year} - ¥{self.target_amount}"

    @property
    def target_period(self):
        """Return formatted target period"""
        months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        return f"{months[self.target_month - 1]} {self.target_year}"
    
    @property
    def target_date(self):
        """Return the first day of the target month/year for chronological ordering"""
        import datetime
        return datetime.date(self.target_year, self.target_month, 1)

    @property
    def is_current_month(self):
        """Check if target is for current month"""
        today = datetime.date.today()
        return self.target_month == today.month and self.target_year == today.year

    @property
    def is_overdue(self):
        """Check if target is overdue"""
        today = datetime.date.today()
        target_date = datetime.date(self.target_year, self.target_month, 1)
        return target_date < datetime.date(today.year, today.month, 1) and self.status == 'active'

    def save(self, *args, **kwargs):
        """Update status based on date when saving"""
        if self.is_overdue:
            self.status = 'overdue'
        super().save(*args, **kwargs)


class RentalContract(TimeStampedUserModel):
    """Model to store rental property contracts and agreements"""
    
    # Customer Information
    customer_name = models.CharField(
        max_length=255,
        help_text="Name of the customer/tenant"
    )
    
    customer_number = models.CharField(
        max_length=11,
        help_text="Customer contact number (maximum 11 digits)"
    )
    
    # Property Information
    building_address = models.TextField(
        help_text="Full address of the building/property"
    )
    
    # Contract Information
    contract_date = models.DateField(
        help_text="Date when the contract was signed"
    )
    
    # Financial Information
    agent_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Agent fee amount"
    )
    
    ad_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Advertisement fee amount"
    )
    
    # Calculated total amount (agent fee + AD fee)
    @property
    def total_amount(self):
        """Calculate total amount from agent fee and AD fee"""
        return self.agent_fee + self.ad_fee
    
    # Support Information
    support_phone = models.CharField(
        max_length=11,
        help_text="24/7 support phone number (maximum 11 digits)"
    )
    
    # Contract Details
    CONTRACT_TYPE_CHOICES = [
        ('fix_term', 'Fix Term'),
        ('regular', 'Regular'),
    ]
    
    contract_type = models.CharField(
        max_length=20,
        choices=CONTRACT_TYPE_CHOICES,
        help_text="Type of rental contract"
    )
    
    cancellation_notice_period = models.CharField(
        max_length=255,
        help_text="Notice period required for cancellation"
    )
    
    cancellation_period = models.CharField(
        max_length=255,
        help_text="Cancellation period details"
    )
    
    cancellation_charge = models.CharField(
        max_length=255,
        help_text="Charges applicable on cancellation"
    )
    
    deposit_fee = models.CharField(
        max_length=255,
        help_text="Deposit fee amount and terms"
    )
    
    cleaning_charge = models.BooleanField(
        default=False,
        help_text="Whether cleaning charge is applicable"
    )
    
    # Emergency Contact
    emergency_contact_person = models.CharField(
        max_length=255,
        help_text="Emergency contact person name"
    )
    
    emergency_phone = models.CharField(
        max_length=11,
        help_text="Emergency contact phone number (maximum 11 digits)"
    )
    
    # Additional Information
    renew_fee = models.CharField(
        max_length=255,
        help_text="Renewal fee amount and terms"
    )
    
    living_num_people = models.PositiveIntegerField(
        help_text="Number of people living in the property"
    )
    
    rent_payment_date = models.CharField(
        max_length=255,
        help_text="Rent payment due date"
    )

    class Meta:
        verbose_name = "Rental Contract"
        verbose_name_plural = "Rental Contracts"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer_name} - {self.contract_date} - ¥{self.total_amount}"

    def clean(self):
        """Validate phone numbers are maximum 11 digits and user has active target"""
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        # Validate phone numbers (maximum 11 digits)
        if len(self.customer_number) > 11:
            raise ValidationError("Customer number cannot exceed 11 digits")
        
        if len(self.support_phone) > 11:
            raise ValidationError("Support phone cannot exceed 11 digits")
        
        if len(self.emergency_phone) > 11:
            raise ValidationError("Emergency phone cannot exceed 11 digits")
        
        # Validate that user has an active target for the current month
        if self.created_by and not self.pk:  # Only check for new contracts
            today = timezone.now().date()
            
            # Use get_model to avoid circular import
            from django.apps import apps
            Target = apps.get_model('targets', 'Target')
            
            active_target = Target.objects.filter(
                user=self.created_by,
                target_month=today.month,
                target_year=today.year,
                status='active'
            ).first()
            
            if not active_target:
                raise ValidationError(
                    "You can only create achievements when you have an active target for the current month. "
                    "Please contact your supervisor if you need a target assigned."
                )
    
    def save(self, *args, **kwargs):
        """Ensure validation is called before saving"""
        self.full_clean()
        super().save(*args, **kwargs)
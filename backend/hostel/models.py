import re
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from decimal import Decimal
from customer.models import Customer
from django.utils import timezone

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

# Model representing a hostel with contract and management metadata
class Hostel(TimeStampedUserModel):
    HOSTEL_TYPE_CHOICES = [
        ('boys', 'Boys'),
        ('girls', 'Girls')
    ]

    name = models.CharField(max_length=255, unique=True)
    common_name = models.CharField(max_length=255, blank=True, null=True)
    hostel_type = models.CharField(max_length=20, choices=HOSTEL_TYPE_CHOICES)
    image = models.ImageField(upload_to='hostel_images/', blank=True, null=True)
    total_rooms = models.PositiveIntegerField()
    address = models.TextField()
    longitude = models.DecimalField(max_digits=15, decimal_places=10, blank=True, null=True)
    latitude = models.DecimalField(max_digits=15, decimal_places=10, blank=True, null=True)
    memo = models.TextField(blank=True, null=True)
    contract_start_date = models.DateField(blank=True, null=True)
    contract_end_date = models.DateField(blank=True, null=True)
    house_owner = models.CharField(max_length=100, blank=True, null=True)
    hw_contact_num = models.CharField(max_length=15, blank=True, null=True)
    deposit_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    initial_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    internet_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    utilities_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    rent = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    hostel_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='hostels_managed',
        limit_choices_to={'is_staff': True},
        null=True,
        blank=True
    )   # 👇 ForeignKey to a staff user
    

    def normalize_name(self, name):
        # Lowercase and remove all spaces
        return re.sub(r'\s+', '', name.lower())

    def clean(self):
        norm_new = self.normalize_name(self.name)
        existing = Hostel.objects.exclude(pk=self.pk)
        for hostel in existing:
            if self.normalize_name(hostel.name) == norm_new:
                raise ValidationError({'name': 'A hostel with a similar name already exists (ignores case and spacing).'})

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    



class Unit(TimeStampedUserModel):
    UNIT_TYPE_CHOICES = [
        ('bedroom', 'BedRoom'),
        ('kitchen', 'Kitchen'),
        ('bathroom', 'Bathroom'),
        ('toilet', 'Toilet'),
        ('toilet_bathroom', 'Toilet + Bathroom'),
    ]

    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='units')
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPE_CHOICES)
    room_num = models.CharField(max_length=20, null=True, blank=True)
    num_of_beds = models.PositiveIntegerField(null=True, blank=True)
    unit_id = models.CharField(max_length=50, null=True, blank=True)
    image = models.ImageField(upload_to='unit_images/', blank=True, null=True)
    memo = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['hostel', 'room_num'],
                condition=models.Q(unit_type='bedroom'),
                name='unique_bedroom_per_hostel'
            ),
            models.UniqueConstraint(
                fields=['hostel', 'unit_id'],
                condition=~models.Q(unit_type='bedroom'),
                name='unique_unit_id_per_hostel'
            ),
        ]

    def __str__(self):
        if self.unit_type == 'bedroom':
            return f"{self.hostel.name} - Bedroom {self.room_num}"
        return f"{self.hostel.name} - {self.unit_type} ({self.unit_id})"

    
class Bed(TimeStampedUserModel):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='beds',
        limit_choices_to={'unit_type': 'bedroom'}
    )
    bed_num = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex='^[a-zA-Z0-9]+$',
                message='Bed number must be alphanumeric.'
            )
        ]
    )
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='bed_assignment',
        blank=True,
        null=True
    )
    assigned_date = models.DateField(blank=True, null=True)
    released_date = models.DateField(blank=True, null=True)

    def save(self, *args, **kwargs):
        today = timezone.now().date()

        # If existing bed and released_date is passed
        if (
            self.pk and
            self.released_date and
            self.released_date <= today and
            self.customer and
            self.assigned_date
        ):
            from .models import BedAssignmentHistory

            # Move to history
            BedAssignmentHistory.objects.create(
                bed=self,
                customer=self.customer,
                assigned_date=self.assigned_date,
                released_date=self.released_date
            )

            # Mark customer inactive
            self.customer.status = False
            self.customer.save()

            # Clear bed assignment
            self.customer = None
            self.assigned_date = None
            self.released_date = None

        super().save(*args, **kwargs)
    
class BedAssignmentHistory(TimeStampedUserModel):
    bed = models.ForeignKey(Bed, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    assigned_date = models.DateField()
    released_date = models.DateField()

    def save(self, *args, **kwargs):
        # On save, deactivate the customer
        if self.customer and self.customer.status:
            self.customer.status = False
            self.customer.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer} - {self.bed} from {self.assigned_date} to {self.released_date}"
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from decimal import Decimal

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

    name = models.CharField(
        max_length=255,
        unique=True,
        validators=[
            RegexValidator(
                regex='^[a-zA-Z0-9_]+$',
                message='Name must be alphanumeric (letters, numbers, underscores only).'
            )
        ]
    )
    common_name = models.CharField(max_length=255, blank=True, null=True)
    hostel_type = models.CharField(max_length=20, choices=HOSTEL_TYPE_CHOICES)
    image = models.ImageField(upload_to='hostel_images/', blank=True, null=True)
    total_rooms = models.PositiveIntegerField()
    address = models.TextField()
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
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
    bedroom_num = models.PositiveIntegerField(null=True, blank=True)
    num_of_beds = models.PositiveIntegerField(null=True, blank=True)
    unit_id = models.CharField(max_length=50, null=True, blank=True)
    image = models.ImageField(upload_to='unit_images/', blank=True, null=True)
    memo = models.TextField(blank=True, null=True)

    def clean(self):
        # Bedroom validation
        if self.unit_type == 'bedroom':
            if self.bedroom_num is None:
                raise ValidationError({'bedroom_num': 'This field is required when unit type is Bedroom.'})
            if self.num_of_beds is None:
                raise ValidationError({'num_of_beds': 'This field is required when unit type is Bedroom.'})
            self.unit_id = None

            # Enforce uniqueness of (hostel, bedroom_num)
            if Unit.objects.filter(
                hostel=self.hostel,
                bedroom_num=self.bedroom_num,
                unit_type='bedroom'
            ).exclude(pk=self.pk).exists():
                raise ValidationError({'bedroom_num': 'A bedroom with this number already exists in this hostel.'})

            # Check existing bed count if updating
            if self.pk:
                existing_beds = self.beds.count()  # 'beds' is the related_name from Bed model
                if self.num_of_beds < existing_beds:
                    raise ValidationError({
                        'num_of_beds': f"Cannot set number of beds to {self.num_of_beds}. "
                                       f"There are already {existing_beds} bed(s) assigned to this unit. "
                                       f"Please delete beds before reducing the count."
                    })
        else:
            if not self.unit_id:
                raise ValidationError({'unit_id': 'This field is required when unit type is not Bedroom.'})
            self.bedroom_num = None
            self.num_of_beds = None

            # Enforce uniqueness of (hostel, unit_id)
            if Unit.objects.filter(
                hostel=self.hostel,
                unit_id=self.unit_id
            ).exclude(pk=self.pk).exists():
                raise ValidationError({'unit_id': 'A unit with this ID already exists in this hostel.'})

    def __str__(self):
        if self.unit_type == 'bedroom':
            return f"Bedroom {self.bedroom_num} - {self.hostel.name}"
        return f"{self.get_unit_type_display()} ({self.unit_id}) - {self.hostel.name}"

    
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

    def clean(self):
        # Ensure selected unit is a bedroom
        if self.unit.unit_type != 'bedroom':
            raise ValidationError({'unit': 'Only bedroom-type units can be assigned beds.'})

        # Count existing beds in this unit, excluding the current one (for updates)
        current_bed_count = Bed.objects.filter(unit=self.unit).exclude(pk=self.pk).count()

        # Check if unit.num_of_beds is exceeded
        if self.unit.num_of_beds is not None and current_bed_count >= self.unit.num_of_beds:
            raise ValidationError({'bed_num': f"This unit can only have {self.unit.num_of_beds} beds."})

        # Optional: enforce unique bed_num per unit
        if Bed.objects.filter(unit=self.unit, bed_num=self.bed_num).exclude(pk=self.pk).exists():
            raise ValidationError({'bed_num': 'This bed number already exists in this unit.'})

    def __str__(self):
        return f"Bed {self.bed_num} in {self.unit}"
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_countries.fields import CountryField  # type: ignore
from django.contrib.auth import get_user_model
from datetime import date


from hostel.models import Bed

User = get_user_model()

class TimeStampedUserModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        related_name="%(class)s_created_by",
        null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        related_name="%(class)s_updated_by",
        null=True, blank=True
    )

    class Meta:
        abstract = True


def visa_type_choices():
    return [
        ('Student', 'Student'),
        ('Skilled Labor', 'Skilled Labor'),
        ('Specified Skilled Worker', 'Specified Skilled Worker'),
        ('Technical Intern Training', 'Technical Intern Training'),
        ('Engineer/Specialist in Humanities/International Services', 'Engineer/Humanities/International'),
        ('Working Holiday', 'Working Holiday'),
        ('Spouse or Child of Japanese National', 'Spouse/Child of Japanese'),
        ('Permanent Resident', 'Permanent Resident'),
        ('Dependent', 'Dependent'),
        ('Other', 'Other'),
    ]


class Customer(TimeStampedUserModel):
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    nationality = CountryField()
    home_address = models.TextField()
    parent_phone_number = models.CharField(max_length=20)
    visa_type = models.CharField(max_length=100, choices=visa_type_choices(), blank=True, null=True)
    workplace_or_school_name = models.CharField(max_length=255, blank=True, null=True)
    workplace_or_school_address = models.TextField(blank=True, null=True)
    workplace_or_school_phone = models.CharField(max_length=20, blank=True, null=True)
    zairyu_card_number = models.CharField(max_length=50)
    zairyu_card_expire_date = models.DateField()
    zairyu_card_url = models.URLField()
    passport_url = models.URLField()
    student_card_url = models.URLField(blank=True, null=True)

    def is_expired(self):
        latest_assignment = self.assignments.order_by('-assigned_until').first()
        return latest_assignment and latest_assignment.assigned_until < timezone.now().date()

    def clean(self):
        if self.nationality.code != 'JP' and not self.visa_type:
            raise ValidationError({'visa_type': 'Visa type is required for non-Japanese nationals.'})
        if self.visa_type == 'Student' and not self.student_card_url:
            raise ValidationError({'student_card_url': 'Student card URL is required for Student visa holders.'})
        if self.pk and self.is_expired():
            raise ValidationError("This customer's record is locked and cannot be modified.")

    def __str__(self):
        return self.name

    @property
    def current_bed_assignment(self):
        today = timezone.now().date()
        return self.assignments.filter(assigned_from__lte=today, assigned_until__gte=today).first()

    @property
    def is_active(self):
        return self.current_bed_assignment is not None

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['id','name', 'date_of_birth'], name='unique_customer_name_dob_id')
        ]


class BedAssignment(TimeStampedUserModel):
    bed = models.ForeignKey(
        'hostel.Bed',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    assigned_from = models.DateField()
    assigned_until = models.DateField(blank=True, null=True)

    def is_active(self):
        """Returns True if today is between assigned_from and assigned_until (or open-ended)."""
        today = timezone.now().date()
        if self.assigned_until:
            return self.assigned_from <= today <= self.assigned_until
        return self.assigned_from <= today

    def clean(self):
        today = timezone.now().date()

        if self.pk:
            original = BedAssignment.objects.get(pk=self.pk)
            if original.assigned_until and original.assigned_until < today:
                raise ValidationError("You cannot modify a past bed assignment.")

        # Normalize end date for open-ended ranges
        assigned_until = self.assigned_until or date.max

        # Check for overlapping bed assignments
        overlapping = BedAssignment.objects.filter(
            bed=self.bed,
            assigned_from__lte=assigned_until,
        ).filter(
            models.Q(assigned_until__gte=self.assigned_from) | models.Q(assigned_until__isnull=True)
        ).exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError("This bed is already assigned during the selected period.")

        # Check for expired assignments
        customer_has_expired = BedAssignment.objects.filter(
            customer=self.customer,
            assigned_until__lt=today
        ).exists()

        if customer_has_expired:
            raise ValidationError("This customer already had a bed assignment in the past and is now locked.")

        # Overlapping assignment for customer
        overlapping_customer = BedAssignment.objects.filter(
            customer=self.customer,
            assigned_from__lte=assigned_until,
        ).filter(
            models.Q(assigned_until__gte=self.assigned_from) | models.Q(assigned_until__isnull=True)
        ).exclude(pk=self.pk)

        if overlapping_customer.exists():
            raise ValidationError("This customer already has a bed assigned during this time.")


    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.assigned_until < timezone.now().date():
            raise ValidationError("You cannot delete a past bed assignment.")
        super().delete(*args, **kwargs)

    def __str__(self):
        try:
            hostel_name = self.bed.unit.hostel.name
            room_num = self.bed.unit.bedroom_num
        except AttributeError:
            hostel_name = "Unknown Hostel"
        return f"{self.customer.name} →{hostel_name} - {room_num} - {self.bed.bed_num}"

    class Meta:
        ordering = ['-assigned_from']
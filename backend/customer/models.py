from django.db import models
from django.core.exceptions import ValidationError
from django_countries.fields import CountryField  # type: ignore
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.core.validators import RegexValidator


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


phone_validator = RegexValidator(
    regex=r'^\+?\d{9,15}$',
    message="Enter a valid phone number (e.g., +819012345678 or 09012345678)."
)


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

def validate_file_size(value):
    max_size = 1024 * 1024  # 1MB
    if value.size > max_size:
        raise ValidationError("File size must be under 1MB.")


class Customer(TimeStampedUserModel):
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=15,
        validators=[phone_validator],
        verbose_name="Phone Number"
    )
    nationality = CountryField()
    home_address = models.TextField()
    parent_phone_number = models.CharField(
        max_length=15,
        validators=[phone_validator],
        verbose_name="Parent Phone Number"
    )
    visa_type = models.CharField(max_length=100, choices=visa_type_choices())
    workplace_or_school_name = models.CharField(max_length=255)
    workplace_or_school_address = models.TextField()
    workplace_or_school_phone = models.CharField(max_length=20)
    zairyu_card_number = models.CharField(max_length=50)
    zairyu_card_expire_date = models.DateField()
    zairyu_card_pdf = models.FileField(
        upload_to='documents/zairyu_cards/',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf']),
            validate_file_size
        ],
        blank=True,
        null=True
    )
    passport_pdf = models.FileField(
        upload_to='documents/passports/',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf']),
            validate_file_size
        ],
        blank=True,
        null=True
    )
    student_card_pdf = models.FileField(
        upload_to='documents/student_cards/',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf']),
            validate_file_size
        ],
        blank=True,
        null=True
    )
    status = models.BooleanField(default=True)
    memo = models.TextField(blank=True, null=True)

    # def clean(self):
    #     if self.nationality.code != 'JP' and not self.visa_type:
    #         raise ValidationError({'visa_type': 'Visa type is required for non-Japanese nationals.'})
    #     if self.visa_type == 'Student' and not self.student_card_pdf:
    #         raise ValidationError({'student_card_pdf': 'Student card is required for Student visa holders.'})

    def __str__(self):
        return f"{self.name} - {self.date_of_birth}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['status','name', 'date_of_birth'], name='unique_customer_name_dob_status')
        ]
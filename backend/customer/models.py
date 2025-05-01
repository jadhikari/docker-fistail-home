from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django_countries.fields import CountryField


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

    visa_type = models.CharField(
        max_length=100,
        choices=visa_type_choices(),
        blank=True,
        null=True
    )

    workplace_or_school_name = models.CharField(max_length=255, blank=True, null=True)
    workplace_or_school_address = models.TextField(blank=True, null=True)
    workplace_or_school_phone = models.CharField(max_length=20, blank=True, null=True)

    zairyu_card_number = models.CharField(max_length=50)
    zairyu_card_expire_date = models.DateField()
    zairyu_card_url = models.URLField()
    passport_url = models.URLField()
    student_card_url = models.URLField(blank=True, null=True)

    def clean(self):
        if self.nationality.code != 'JP' and not self.visa_type:
            raise ValidationError({'visa_type': 'Visa type is required for non-Japanese nationals.'})

        if self.visa_type == 'Student' and not self.student_card_url:
            raise ValidationError({'student_card_url': 'Student card URL is required for Student visa holders.'})

    def __str__(self):
        return self.name
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'date_of_birth'], name='unique_customer_name_dob')
        ]

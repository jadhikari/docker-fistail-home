from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone

User = get_user_model()

# ---------- Base Model ----------
class TimeStampedUserModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="%(class)s_created_by", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="%(class)s_updated_by", null=True, blank=True)

    class Meta: abstract = True


# ---------- Business ----------
class Business(TimeStampedUserModel):
    name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, unique=True)
    business_type = models.CharField(max_length=100)
    industry_category = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, help_text="Phone number must be unique when combined with business name")
    website = models.URLField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    tax_number = models.CharField(max_length=100, blank=True, null=True)

    owner_name = models.CharField(max_length=255)
    owner_contact_number = models.CharField(max_length=20, blank=True, null=True)
    owner_email = models.EmailField(blank=True, null=True)
    owner_address = models.CharField(max_length=255, blank=True, null=True)

    office_rent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)], help_text="Monthly office rent amount")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Businesses"
        unique_together = [["name", "phone"]]

    def __str__(self): return self.name

    def clean(self):
        if self.office_rent < 0: raise ValidationError("Office rent cannot be negative.")
        qs = Business.objects.filter(name=self.name, phone=self.phone).exclude(pk=self.pk) if self.pk else Business.objects.filter(name=self.name, phone=self.phone)
        if qs.exists(): raise ValidationError("A business with this name and phone number already exists.")


# ---------- Municipal Shop ----------
class MunicipalShop(TimeStampedUserModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="shops")
    name = models.CharField(max_length=255)
    permit_id = models.CharField(max_length=100, unique=True)
    shop_type = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True, null=True)
    shop_rent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)], help_text="Monthly shop rent amount")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Municipal Shops"

    def __str__(self): return f"{self.name} ({self.business.name})"
    def clean(self): 
        if self.shop_rent < 0: raise ValidationError("Shop rent cannot be negative.")


# ---------- Staff ----------
class Staff(TimeStampedUserModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, null=True, blank=True, related_name="staff")
    shop = models.ForeignKey(MunicipalShop, on_delete=models.CASCADE, null=True, blank=True, related_name="staff")

    full_name = models.CharField(max_length=255)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[("M","Male"), ("F","Female"), ("O","Other")])
    contact_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=100)
    employment_type = models.CharField(max_length=50, choices=[("FT","Full-Time"), ("PT","Part-Time"), ("CT","Contract"), ("Owner","Owner")])
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank if staff is still active")
    status = models.CharField(max_length=20, choices=[("Active","Active"), ("Inactive","Inactive"), ("Terminated","Terminated"), ("Resigned","Resigned")], default="Active")
    address = models.CharField(max_length=255, blank=True, null=True)

    zairyucard_number = models.CharField(max_length=100, unique=True)
    zairyucard_issue_date = models.DateField(null=True, blank=True)
    zairyucard_expiry_date = models.DateField(null=True, blank=True)

    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["full_name"]
        verbose_name_plural = "Staff"

    def __str__(self):
        if self.shop and self.business: return f"{self.full_name} ({self.role}) - {self.shop.name} at {self.business.name}"
        if self.shop: return f"{self.full_name} ({self.role}) - {self.shop.name}"
        if self.business: return f"{self.full_name} ({self.role}) - {self.business.name}"
        return f"{self.full_name} ({self.role})"

    def clean(self):
        if self.shop and self.business and self.shop.business != self.business: raise ValidationError("The selected shop must belong to the specified business.")
        if not self.business and not self.shop: raise ValidationError("Staff must belong to either a business or a shop.")
        if self.salary < 0: raise ValidationError("Salary cannot be negative.")
        if self.dob and self.start_date and self.dob > self.start_date: raise ValidationError("Date of birth cannot be after start date.")
        if self.end_date and self.start_date and self.end_date < self.start_date: raise ValidationError("End date cannot be before start date.")
        if self.end_date and self.status == "Active": self.status = "Inactive"

    def save(self, *args, **kwargs): self.clean(); super().save(*args, **kwargs)

    @property
    def is_active(self): return self.status == "Active" and (not self.end_date or self.end_date > timezone.now().date())
    @property
    def assignment_display(self): return f"{self.shop.name} at {self.business.name}" if self.shop and self.business else (self.shop.name if self.shop else (self.business.name if self.business else "Unassigned"))
    @property
    def employment_duration(self): return (self.end_date or timezone.now().date() - self.start_date).days if self.start_date else 0

    def terminate_employment(self, end_date=None): self.end_date = end_date or timezone.now().date(); self.status="Terminated"; self.save()
    def resign_employment(self, end_date=None): self.end_date = end_date or timezone.now().date(); self.status="Resigned"; self.save()
    def reactivate_employment(self, new_start_date=None): self.end_date=None; self.start_date=new_start_date or timezone.now().date(); self.status="Active"; self.save()

    def update_salary(self, amount, change_type, reason=""):
        if amount < 0: raise ValidationError("Amount cannot be negative.")
        prev = self.salary
        if change_type in ["Increment","Bonus"]: self.salary += amount
        elif change_type == "Decrement":
            if amount > self.salary: raise ValidationError("Cannot decrement more than current salary.")
            self.salary -= amount
        else: raise ValidationError("Invalid change type.")
        self.save()


# ---------- Dependent ----------
class Dependent(TimeStampedUserModel):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="dependents")
    full_name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=50, choices=[("Spouse","Spouse"), ("Child","Child"), ("Parent","Parent"), ("Other","Other")])
    dob = models.DateField(null=True, blank=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name_plural = "Dependents"

    def __str__(self): return f"{self.full_name} ({self.relationship} of {self.staff.full_name})" if self.staff_id and self.staff else f"{self.full_name} (No staff assigned)"

    def clean(self):
        if self.dob and self.staff_id and self.staff and self.staff.dob and self.dob > self.staff.dob: 
            raise ValidationError("Dependent's date of birth cannot be after staff's date of birth.")

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Target, RentalContract
import datetime

User = get_user_model()


class TargetForm(forms.ModelForm):
    """Form for editing existing targets"""
    
    class Meta:
        model = Target
        fields = ['target_amount', 'target_month', 'target_year', 'status', 'description']
        widgets = {
            'target_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Enter target amount'
            }),
            'target_month': forms.Select(attrs={'class': 'form-select'}),
            'target_year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2020',
                'max': '2030'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description or notes about this target'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set month choices
        months = [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]
        self.fields['target_month'].choices = [('', 'Select Month')] + months
        
        # Set default year to current year
        current_year = datetime.date.today().year
        self.fields['target_year'].initial = current_year


class TargetAssignmentForm(forms.ModelForm):
    """Form for assigning new targets to users"""
    
    class Meta:
        model = Target
        fields = ['user', 'target_amount', 'target_month', 'target_year', 'description']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'target_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Enter target amount'
            }),
            'target_month': forms.Select(attrs={'class': 'form-select'}),
            'target_year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2020',
                'max': '2030'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description or notes about this target'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Show only regular active users (exclude superusers)
        self.fields['user'].queryset = User.objects.filter(
            is_active=True,
            is_superuser=False
        ).order_by('first_name', 'email')
        
        # Customize user display with clean formatting
        def format_user_display(user):
            if user.first_name and user.last_name:
                return f"{user.first_name} {user.last_name} ({user.email})"
            elif user.first_name:
                return f"{user.first_name} ({user.email})"
            else:
                return f"{user.email}"
        
        self.fields['user'].label_from_instance = format_user_display
        
        # Set month choices
        months = [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]
        self.fields['target_month'].choices = [('', 'Select Month')] + months
        
        # Set default year to current year
        current_year = datetime.date.today().year
        self.fields['target_year'].initial = current_year
        
        # Add help text
        self.fields['user'].help_text = "Select the user to assign this target to"
        self.fields['target_amount'].help_text = "Monthly target amount in Japanese Yen"
        self.fields['target_month'].help_text = "Month for which this target applies"
        self.fields['target_year'].help_text = "Year for which this target applies"

    def clean(self):
        """Validate that user doesn't already have target for this month/year"""
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        target_month = cleaned_data.get('target_month')
        target_year = cleaned_data.get('target_year')
        
        if user and target_month and target_year:
            # Check if target already exists for this user/month/year
            existing_target = Target.objects.filter(
                user=user,
                target_month=target_month,
                target_year=target_year
            )
            
            # If editing, exclude current instance
            if self.instance.pk:
                existing_target = existing_target.exclude(pk=self.instance.pk)
            
            if existing_target.exists():
                raise ValidationError(
                    f"Target for {user.first_name or user.email} already exists for "
                    f"{target_month}/{target_year}. Please edit the existing target instead."
                )
        
        return cleaned_data

    def clean_target_month(self):
        """Validate target month"""
        target_month = self.cleaned_data.get('target_month')
        if target_month and (target_month < 1 or target_month > 12):
            raise ValidationError("Please select a valid month.")
        return target_month

    def clean_target_year(self):
        """Validate target year"""
        target_year = self.cleaned_data.get('target_year')
        current_year = datetime.date.today().year
        
        if target_year and (target_year < 2020 or target_year > current_year + 5):
            raise ValidationError(f"Please enter a year between 2020 and {current_year + 5}.")
        
        return target_year


class RentalContractForm(forms.ModelForm):
    """Form for creating and editing rental contracts"""
    
    class Meta:
        model = RentalContract
        fields = [
            'customer_name', 'customer_number', 'building_address', 'contract_date',
            'agent_fee', 'ad_fee', 'support_phone', 'contract_type',
            'cancellation_notice_period', 'cancellation_period', 'cancellation_charge',
            'deposit_fee', 'cleaning_charge', 'emergency_contact_person',
            'emergency_phone', 'renew_fee', 'living_num_people', 'rent_payment_date'
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter customer name'
            }),
            'customer_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter customer phone number (max 11 digits)'
            }),
            'building_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter building address'
            }),
            'contract_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Select contract date'
            }),
            'agent_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': 'Enter agent fee'
            }),
            'ad_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': 'Enter advertisement fee'
            }),
            'support_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter 24/7 support phone number (max 11 digits)'
            }),
            'contract_type': forms.Select(attrs={'class': 'form-select'}),
            'cancellation_notice_period': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter cancellation notice period'
            }),
            'cancellation_period': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter cancellation period'
            }),
            'cancellation_charge': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter cancellation charge'
            }),
            'deposit_fee': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter deposit fee'
            }),
            'cleaning_charge': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'emergency_contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter emergency contact person'
            }),
            'emergency_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter emergency contact phone number (max 11 digits)'
            }),
            'renew_fee': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter renewal fee'
            }),
            'living_num_people': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Enter number of people'
            }),
            'rent_payment_date': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter rent payment date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer_number'].help_text = "Maximum 11 digits"
        self.fields['support_phone'].help_text = "Maximum 11 digits"
        self.fields['emergency_phone'].help_text = "Maximum 11 digits"
        self.fields['agent_fee'].help_text = "Agent fee amount"
        self.fields['ad_fee'].help_text = "Advertisement fee amount"


class BulkTargetAssignmentForm(forms.Form):
    """Form for assigning targets to multiple users at once"""
    
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True, is_superuser=False),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Select users to assign targets to (superusers are excluded)"
    )
    
    target_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Enter target amount'
        }),
        help_text="Target amount for all selected users"
    )
    
    target_month = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Month for the targets"
    )
    
    target_year = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '2020',
            'max': '2030'
        }),
        help_text="Year for the targets"
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional description for all targets'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set month choices
        months = [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]
        self.fields['target_month'].choices = [('', 'Select Month')] + months
        
        # Set default year to current year
        current_year = datetime.date.today().year
        self.fields['target_year'].initial = current_year
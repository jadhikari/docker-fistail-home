from django import forms
from django.core.exceptions import ValidationError
from .models import Business, MunicipalShop, Staff, Dependent


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = [
            'name', 'registration_number', 'business_type', 'industry_category',
            'email', 'phone', 'website', 'address', 'tax_number',
            'owner_name', 'owner_contact_number', 'owner_email', 'owner_address', 'owner_salary',
            'office_rent'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'business_type': forms.TextInput(attrs={'class': 'form-control'}),
            'industry_category': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'owner_name': forms.TextInput(attrs={'class': 'form-control'}),
            'owner_contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'owner_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'owner_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'owner_salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'office_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        owner_salary = cleaned_data.get('owner_salary')
        office_rent = cleaned_data.get('office_rent')
        
        if owner_salary is not None and owner_salary < 0:
            raise ValidationError("Owner salary cannot be negative.")
        
        if office_rent is not None and office_rent < 0:
            raise ValidationError("Office rent cannot be negative.")
        
        return cleaned_data


class MunicipalShopForm(forms.ModelForm):
    class Meta:
        model = MunicipalShop
        fields = ['business', 'name', 'permit_id', 'shop_type', 'address', 'shop_rent']
        widgets = {
            'business': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'permit_id': forms.TextInput(attrs={'class': 'form-control'}),
            'shop_type': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'shop_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        shop_rent = cleaned_data.get('shop_rent')
        
        if shop_rent is not None and shop_rent < 0:
            raise ValidationError("Shop rent cannot be negative.")
        
        return cleaned_data


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = [
            'business', 'shop', 'full_name', 'dob', 'gender', 'contact_number',
            'email', 'role', 'employment_type', 'start_date', 'end_date', 'status',
            'address', 'zairyucard_number', 'zairyucard_issue_date', 'zairyucard_expiry_date', 'salary'
        ]
        widgets = {
            'business': forms.Select(attrs={'class': 'form-control'}),
            'shop': forms.Select(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.TextInput(attrs={'class': 'form-control'}),
            'employment_type': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'zairyucard_number': forms.TextInput(attrs={'class': 'form-control'}),
            'zairyucard_issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'zairyucard_expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        # Check if this is for editing an existing staff member
        self.is_editing = kwargs.get('instance') is not None
        self.pre_selected_business = kwargs.pop('pre_selected_business', None)
        self.pre_selected_shop = kwargs.pop('pre_selected_shop', None)
        
        super().__init__(*args, **kwargs)
        
        # Set up business field
        if 'business' in self.fields:
            if self.pre_selected_business:
                # Business is pre-selected, make it read-only
                self.fields['business'].queryset = Business.objects.filter(pk=self.pre_selected_business.pk)
                self.fields['business'].widget.attrs.update({
                    'class': 'form-control',
                    'readonly': 'readonly',
                    'disabled': 'disabled'
                })
                self.fields['business'].initial = self.pre_selected_business
            else:
                # No pre-selected business, allow selection
                self.fields['business'].queryset = Business.objects.all().order_by('name')
                self.fields['business'].empty_label = "Select a business"
        
        # Set up shop field
        if 'shop' in self.fields:
            if self.pre_selected_shop:
                # Shop is pre-selected, make it read-only and set business
                self.fields['shop'].queryset = MunicipalShop.objects.filter(pk=self.pre_selected_shop.pk)
                self.fields['shop'].widget.attrs.update({
                    'class': 'form-control',
                    'readonly': 'readonly',
                    'disabled': 'disabled'
                })
                self.fields['shop'].initial = self.pre_selected_shop
                # Also set the business field to the shop's business
                if self.pre_selected_business:
                    self.fields['business'].queryset = Business.objects.filter(pk=self.pre_selected_business.pk)
                    self.fields['business'].widget.attrs.update({
                        'class': 'form-control',
                        'readonly': 'readonly',
                        'disabled': 'disabled'
                    })
                    self.fields['business'].initial = self.pre_selected_business
            elif self.pre_selected_business:
                # Filter shops by pre-selected business
                shops = MunicipalShop.objects.filter(business=self.pre_selected_business).order_by('name')
                shop_choices = [('', '---------')]
                for shop in shops:
                    shop_choices.append((shop.id, shop.name))
                
                self.fields['shop'].choices = shop_choices
                self.fields['shop'].empty_label = "Select a shop (optional)"
            else:
                # Show all shops with business context
                shops = MunicipalShop.objects.select_related('business').all().order_by('business__name', 'name')
                shop_choices = [('', '---------')]
                for shop in shops:
                    shop_choices.append((shop.id, f"{shop.name} ({shop.business.name})"))
                
                self.fields['shop'].choices = shop_choices
                self.fields['shop'].empty_label = "Select a shop (optional)"
        
        # Set up other fields
        if 'gender' in self.fields:
            self.fields['gender'].choices = [
                ('', 'Select gender'),
                ('M', 'Male'),
                ('F', 'Female'),
                ('O', 'Other')
            ]
        
        if 'employment_type' in self.fields:
            self.fields['employment_type'].choices = [
                ('', 'Select employment type'),
                ('FT', 'Full-Time'),
                ('PT', 'Part-Time'),
                ('CT', 'Contract')
            ]
        
        if 'status' in self.fields:
            self.fields['status'].choices = [
                ('', 'Select status'),
                ('Active', 'Active'),
                ('Inactive', 'Inactive'),
                ('Terminated', 'Terminated'),
                ('Resigned', 'Resigned')
            ]

    def clean(self):
        cleaned_data = super().clean()
        business = cleaned_data.get('business')
        shop = cleaned_data.get('shop')
        dob = cleaned_data.get('dob')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        status = cleaned_data.get('status')
        salary = cleaned_data.get('salary')
        
        # If business is pre-selected, ensure it's included in cleaned data
        if self.pre_selected_business:
            cleaned_data['business'] = self.pre_selected_business
            business = self.pre_selected_business
        
        # If shop is pre-selected, ensure it's included in cleaned data
        if self.pre_selected_shop:
            cleaned_data['shop'] = self.pre_selected_shop
            shop = self.pre_selected_shop
        
        # Check business/shop assignment
        if business and shop:
            # Verify that the shop belongs to the selected business
            if shop.business != business:
                raise ValidationError("The selected shop does not belong to the selected business.")
        elif not business and not shop:
            raise ValidationError("Staff must belong to either a business or a shop.")
        
        # Check salary
        if salary is not None and salary < 0:
            raise ValidationError("Salary cannot be negative.")
        
        # Check dates
        if dob and start_date and dob > start_date:
            raise ValidationError("Date of birth cannot be after start date.")
        
        # Check end date validation
        if end_date and start_date and end_date < start_date:
            raise ValidationError("End date cannot be before start date.")
        
        # Status validation
        if end_date and status == "Active":
            cleaned_data['status'] = "Inactive"
        
        return cleaned_data


class DependentForm(forms.ModelForm):
    class Meta:
        model = Dependent
        fields = ['full_name', 'relationship', 'dob', 'contact_number', 'address']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        dob = cleaned_data.get('dob')
        
        # Additional validation can be added here if needed
        return cleaned_data


class BusinessSearchForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Business name...'})
    )
    business_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Business type...'})
    )
    owner_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Owner name...'})
    )

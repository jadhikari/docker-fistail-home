from django import forms
from django.core.exceptions import ValidationError
from .models import Business, MunicipalShop, Staff, Dependent, Title, Transaction


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = [
            'name', 'registration_number', 'business_type', 'industry_category',
            'email', 'phone', 'website', 'address', 'tax_number',
            'owner_name', 'owner_contact_number', 'owner_email', 'owner_address',
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
            'office_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        office_rent = cleaned_data.get('office_rent')
        name = cleaned_data.get('name')
        phone = cleaned_data.get('phone')
        
        if office_rent is not None and office_rent < 0:
            raise ValidationError("Office rent cannot be negative.")
        
        # Check for duplicate business name + phone combination
        if name and phone:
            # Get the current instance if editing
            instance = getattr(self, 'instance', None)
            
            if instance and instance.pk:  # If updating existing business
                existing_businesses = Business.objects.filter(name=name, phone=phone).exclude(pk=instance.pk)
            else:  # If creating new business
                existing_businesses = Business.objects.filter(name=name, phone=phone)
            
            if existing_businesses.exists():
                # Add non-field error for better user experience
                self.add_error(None, "A business with this name and phone number already exists.")
                # Also add field-specific errors
                self.add_error('name', "This business name with the given phone number already exists.")
                self.add_error('phone', "This phone number with the given business name already exists.")
        
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
                    'class': 'form-control'
                })
                # Make field readonly but not disabled to avoid validation issues
                self.fields['business'].widget.attrs['readonly'] = True
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
                    'class': 'form-control'
                })
                # Make field readonly but not disabled to avoid validation issues
                self.fields['shop'].widget.attrs['readonly'] = True
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
                ('CT', 'Contract'),
                ('Owner', 'Owner')
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
        fields = ['full_name', 'relationship', 'dob', 'contact_number', 'address', 'zairyucard_number', 'zairyucard_issue_date', 'zairyucard_expiry_date']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'zairyucard_number': forms.TextInput(attrs={'class': 'form-control'}),
            'zairyucard_issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'zairyucard_expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
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


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            'transaction_type', 'transaction_mode', 'year', 'month', 
            'amount', 'memo', 'business', 'shop'
        ]
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'transaction_mode': forms.Select(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': '2000'}),
            'month': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Transaction description or notes...'}),
            'business': forms.Select(attrs={'class': 'form-control'}),
            'shop': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Check if this is for editing an existing transaction
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
                    'class': 'form-control'
                })
                # Make field readonly but not disabled to avoid validation issues
                self.fields['business'].widget.attrs['readonly'] = True
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
                    'class': 'form-control'
                })
                # Make field readonly but not disabled to avoid validation issues
                self.fields['shop'].widget.attrs['readonly'] = True
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
        
        # Set up choice fields
        if 'transaction_type' in self.fields:
            self.fields['transaction_type'].choices = [
                ('', 'Select transaction type'),
                ('Revenue', 'Revenue'),
                ('Expense', 'Expense')
            ]
        
        if 'transaction_mode' in self.fields:
            self.fields['transaction_mode'].choices = [
                ('', 'Select transaction mode'),
                ('Online', 'Online'),
                ('Offline', 'Offline')
            ]
        
        if 'month' in self.fields:
            self.fields['month'].choices = [
                ('', 'Select month'),
                (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
            ]

    def clean(self):
        cleaned_data = super().clean()
        business = cleaned_data.get('business')
        shop = cleaned_data.get('shop')
        amount = cleaned_data.get('amount')
        year = cleaned_data.get('year')
        
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
        elif not business:
            raise ValidationError("Transaction must be associated with a business.")
        
        # Check amount
        if amount is not None and amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        
        # Check year
        from django.utils import timezone
        current_year = timezone.now().year
        if year and (year < 2000 or year > current_year + 10):
            raise ValidationError(f"Year must be between 2000 and {current_year + 10}.")
        
        return cleaned_data


class TransactionSearchForm(forms.Form):
    """Form for searching and filtering transactions"""
    transaction_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Transaction.TRANSACTION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    transaction_mode = forms.ChoiceField(
        choices=[('', 'All Modes')] + Transaction.TRANSACTION_MODE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    year = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Year...', 'min': '2000'})
    )
    month = forms.ChoiceField(
        choices=[('', 'All Months')] + Transaction.MONTH_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    business = forms.ModelChoiceField(
        queryset=Business.objects.all().order_by('name'),
        required=False,
        empty_label="All Businesses",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    shop = forms.ModelChoiceField(
        queryset=MunicipalShop.objects.all().order_by('business__name', 'name'),
        required=False,
        empty_label="All Shops",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class TransactionDetailsSearchForm(forms.Form):
    """Form for searching transaction details with date range"""
    business = forms.ModelChoiceField(
        queryset=Business.objects.all().order_by('name'),
        required=False,
        empty_label="Select Business",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    from_period = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'month',
            'placeholder': 'From Year-Month'
        }),
        help_text="Select the starting year and month"
    )
    to_period = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'month',
            'placeholder': 'To Year-Month'
        }),
        help_text="Select the ending year and month"
    )


class RevenueForm(forms.ModelForm):
    """Form specifically for revenue transactions"""
    period = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'month',
            'placeholder': 'Select Year and Month'
        }),
        help_text="Select the year and month for this revenue"
    )
    
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'transaction_mode', 'title', 'amount', 'memo', 'business', 'shop']
        widgets = {
            'transaction_type': forms.HiddenInput(),
            'transaction_mode': forms.Select(attrs={'class': 'form-control', 'id': 'id_transaction_mode'}),
            'title': forms.Select(attrs={'class': 'form-control', 'id': 'id_title'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Revenue description or notes...'}),
            'business': forms.Select(attrs={'class': 'form-control'}),
            'shop': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.pre_selected_business = kwargs.pop('pre_selected_business', None)
        self.pre_selected_shop = kwargs.pop('pre_selected_shop', None)
        
        super().__init__(*args, **kwargs)
        
        # Set transaction type to Revenue
        self.fields['transaction_type'].initial = 'Revenue'
        self.fields['transaction_type'].required = False  # Make it not required since we set it automatically
        
        # Set up business field
        if 'business' in self.fields:
            if self.pre_selected_business:
                # Use hidden field for pre-selected business
                self.fields['business'] = forms.ModelChoiceField(
                    queryset=Business.objects.filter(pk=self.pre_selected_business.pk),
                    widget=forms.HiddenInput(),
                    initial=self.pre_selected_business
                )
            else:
                self.fields['business'].queryset = Business.objects.all().order_by('name')
                self.fields['business'].empty_label = "Select a business"
        
        # Set up shop field
        if 'shop' in self.fields:
            if self.pre_selected_shop:
                # Use hidden field for pre-selected shop
                self.fields['shop'] = forms.ModelChoiceField(
                    queryset=MunicipalShop.objects.filter(pk=self.pre_selected_shop.pk),
                    widget=forms.HiddenInput(),
                    initial=self.pre_selected_shop
                )
            elif self.pre_selected_business:
                shops = MunicipalShop.objects.filter(business=self.pre_selected_business).order_by('name')
                shop_choices = [('', '---------')]
                for shop in shops:
                    shop_choices.append((shop.id, shop.name))
                self.fields['shop'].choices = shop_choices
                self.fields['shop'].empty_label = "Select a shop (optional)"
            else:
                shops = MunicipalShop.objects.select_related('business').all().order_by('business__name', 'name')
                shop_choices = [('', '---------')]
                for shop in shops:
                    shop_choices.append((shop.id, f"{shop.name} ({shop.business.name})"))
                self.fields['shop'].choices = shop_choices
                self.fields['shop'].empty_label = "Select a shop (optional)"
        
        # Set up transaction mode choices
        if 'transaction_mode' in self.fields:
            self.fields['transaction_mode'].choices = [
                ('', 'Select transaction mode'),
                ('Online', 'Online'),
                ('Offline', 'Offline')
            ]
        
        # Set up title field - load all revenue titles
        if 'title' in self.fields:
            revenue_titles = Title.objects.filter(category='Revenue', is_active=True).order_by('name')
            title_choices = [('', 'Select a title')] + [(title.id, title.name) for title in revenue_titles]
            
            # If editing an existing transaction, ensure the current title is in the choices
            if self.instance and self.instance.pk and self.instance.title:
                current_title = self.instance.title
                if (current_title.id, current_title.name) not in title_choices:
                    # Add the current title to choices if it's not already there
                    title_choices = [('', 'Select a title')] + [(current_title.id, current_title.name)] + [(title.id, title.name) for title in revenue_titles]
            
            self.fields['title'].choices = title_choices
            
            # Ensure the form field is properly bound to the instance data
            if self.instance and self.instance.pk and self.instance.title:
                # Force the field to use the instance value
                self.fields['title'].initial = self.instance.title.id
                # Also set the widget value
                if hasattr(self.fields['title'].widget, 'value_from_datadict'):
                    # This ensures the widget knows about the current value
                    pass

    def clean(self):
        cleaned_data = super().clean()
        business = cleaned_data.get('business')
        shop = cleaned_data.get('shop')
        amount = cleaned_data.get('amount')
        period = cleaned_data.get('period')
        
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
            if shop.business != business:
                raise ValidationError("The selected shop does not belong to the selected business.")
        elif not business:
            raise ValidationError("Transaction must be associated with a business.")
        
        # Check amount
        if amount is not None and amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        
        # Extract year and month from period
        if period:
            try:
                # Parse the month input (format: YYYY-MM)
                year, month = period.split('-')
                cleaned_data['year'] = int(year)
                cleaned_data['month'] = int(month)
                cleaned_data['transaction_type'] = 'Revenue'
            except (ValueError, AttributeError):
                raise ValidationError("Please enter a valid year and month (YYYY-MM format).")
        else:
            raise ValidationError("Period is required.")
        
        return cleaned_data
    
    def clean_transaction_type(self):
        # Always return the correct transaction type for this form
        return 'Revenue' if 'Revenue' in str(type(self)) else 'Expense'
    
    def clean_business(self):
        business = self.cleaned_data.get('business')
        # If business is pre-selected and field is readonly, use the pre-selected business
        if self.pre_selected_business and not business:
            return self.pre_selected_business
        return business
    
    def clean_shop(self):
        shop = self.cleaned_data.get('shop')
        # If shop is pre-selected and field is readonly, use the pre-selected shop
        if self.pre_selected_shop and not shop:
            return self.pre_selected_shop
        return shop
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Ensure year and month are set from the period field
        if self.cleaned_data.get('period'):
            period = self.cleaned_data['period']
            try:
                year, month = period.split('-')
                instance.year = int(year)
                instance.month = int(month)
                instance.transaction_type = 'Revenue'
            except (ValueError, AttributeError):
                pass  # Should not happen if clean() passed
        if commit:
            instance.save()
        return instance


class ExpenseForm(forms.ModelForm):
    """Form specifically for expense transactions"""
    period = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'month',
            'placeholder': 'Select Year and Month'
        }),
        help_text="Select the year and month for this expense"
    )
    
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'transaction_mode', 'title', 'amount', 'memo', 'business', 'shop']
        widgets = {
            'transaction_type': forms.HiddenInput(),
            'transaction_mode': forms.Select(attrs={'class': 'form-control', 'id': 'id_transaction_mode'}),
            'title': forms.Select(attrs={'class': 'form-control', 'id': 'id_title'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Expense description or notes...'}),
            'business': forms.Select(attrs={'class': 'form-control'}),
            'shop': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.pre_selected_business = kwargs.pop('pre_selected_business', None)
        self.pre_selected_shop = kwargs.pop('pre_selected_shop', None)
        
        super().__init__(*args, **kwargs)
        
        # Set transaction type to Expense
        self.fields['transaction_type'].initial = 'Expense'
        self.fields['transaction_type'].required = False  # Make it not required since we set it automatically
        
        # Set up business field
        if 'business' in self.fields:
            if self.pre_selected_business:
                # Use hidden field for pre-selected business
                self.fields['business'] = forms.ModelChoiceField(
                    queryset=Business.objects.filter(pk=self.pre_selected_business.pk),
                    widget=forms.HiddenInput(),
                    initial=self.pre_selected_business
                )
            else:
                self.fields['business'].queryset = Business.objects.all().order_by('name')
                self.fields['business'].empty_label = "Select a business"
        
        # Set up shop field
        if 'shop' in self.fields:
            if self.pre_selected_shop:
                # Use hidden field for pre-selected shop
                self.fields['shop'] = forms.ModelChoiceField(
                    queryset=MunicipalShop.objects.filter(pk=self.pre_selected_shop.pk),
                    widget=forms.HiddenInput(),
                    initial=self.pre_selected_shop
                )
            elif self.pre_selected_business:
                shops = MunicipalShop.objects.filter(business=self.pre_selected_business).order_by('name')
                shop_choices = [('', '---------')]
                for shop in shops:
                    shop_choices.append((shop.id, shop.name))
                self.fields['shop'].choices = shop_choices
                self.fields['shop'].empty_label = "Select a shop (optional)"
            else:
                shops = MunicipalShop.objects.select_related('business').all().order_by('business__name', 'name')
                shop_choices = [('', '---------')]
                for shop in shops:
                    shop_choices.append((shop.id, f"{shop.name} ({shop.business.name})"))
                self.fields['shop'].choices = shop_choices
                self.fields['shop'].empty_label = "Select a shop (optional)"
        
        # Set up transaction mode choices
        if 'transaction_mode' in self.fields:
            self.fields['transaction_mode'].choices = [
                ('', 'Select transaction mode'),
                ('Online', 'Online'),
                ('Offline', 'Offline')
            ]
        
        # Set up title field - load all expense titles
        if 'title' in self.fields:
            expense_titles = Title.objects.filter(category='Expense', is_active=True).order_by('name')
            title_choices = [('', 'Select a title')] + [(title.id, title.name) for title in expense_titles]
            
            # If editing an existing transaction, ensure the current title is in the choices
            if self.instance and self.instance.pk and self.instance.title:
                current_title = self.instance.title
                if (current_title.id, current_title.name) not in title_choices:
                    # Add the current title to choices if it's not already there
                    title_choices = [('', 'Select a title')] + [(current_title.id, current_title.name)] + [(title.id, title.name) for title in expense_titles]
            
            self.fields['title'].choices = title_choices
            
            # Ensure the form field is properly bound to the instance data
            if self.instance and self.instance.pk and self.instance.title:
                # Force the field to use the instance value
                self.fields['title'].initial = self.instance.title.id
                # Also set the widget value
                if hasattr(self.fields['title'].widget, 'value_from_datadict'):
                    # This ensures the widget knows about the current value
                    pass

    def clean(self):
        cleaned_data = super().clean()
        business = cleaned_data.get('business')
        shop = cleaned_data.get('shop')
        amount = cleaned_data.get('amount')
        period = cleaned_data.get('period')
        
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
            if shop.business != business:
                raise ValidationError("The selected shop does not belong to the selected business.")
        elif not business:
            raise ValidationError("Transaction must be associated with a business.")
        
        # Check amount
        if amount is not None and amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        
        # Extract year and month from period
        if period:
            try:
                # Parse the month input (format: YYYY-MM)
                year, month = period.split('-')
                cleaned_data['year'] = int(year)
                cleaned_data['month'] = int(month)
                cleaned_data['transaction_type'] = 'Expense'
            except (ValueError, AttributeError):
                raise ValidationError("Please enter a valid year and month (YYYY-MM format).")
        else:
            raise ValidationError("Period is required.")
        
        return cleaned_data
    
    def clean_transaction_type(self):
        # Always return the correct transaction type for this form
        return 'Revenue' if 'Revenue' in str(type(self)) else 'Expense'
    
    def clean_business(self):
        business = self.cleaned_data.get('business')
        # If business is pre-selected and field is readonly, use the pre-selected business
        if self.pre_selected_business and not business:
            return self.pre_selected_business
        return business
    
    def clean_shop(self):
        shop = self.cleaned_data.get('shop')
        # If shop is pre-selected and field is readonly, use the pre-selected shop
        if self.pre_selected_shop and not shop:
            return self.pre_selected_shop
        return shop
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Ensure year and month are set from the period field
        if self.cleaned_data.get('period'):
            period = self.cleaned_data['period']
            try:
                year, month = period.split('-')
                instance.year = int(year)
                instance.month = int(month)
                instance.transaction_type = 'Expense'
            except (ValueError, AttributeError):
                pass  # Should not happen if clean() passed
        if commit:
            instance.save()
        return instance

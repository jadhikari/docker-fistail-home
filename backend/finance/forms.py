from datetime import date
from decimal import Decimal
from django import forms
from .models import HostelExpense, UtilityExpense, Hostel, StaffExpense, ThirdPartyServiceRecord
from targets.models import RentalContract


class HostelExpenseForm(forms.ModelForm):
    class Meta:
        model = HostelExpense
        fields = ['hostel', 'purchased_date', 'purchased_by', 'amount', 'memo']
        widgets = {'purchased_date': forms.DateInput(attrs={'type': 'date'}), 'memo': forms.Textarea(attrs={'rows': 3})}
    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active hostels in the dropdown
        self.fields['hostel'].queryset = Hostel.objects.filter(status=True)
        # Make all fields required (except hostel)
        for field_name, field in self.fields.items():
            if field_name != 'hostel':
                field.required = True
            # Bootstrap styling
            css_class = 'form-select form-select-sm' if field.widget.__class__.__name__ == 'Select' else 'form-control form-control-sm'
            field.widget.attrs.update({'class': css_class})
        self.fields['hostel'].empty_label = "ALL"


class UtilityExpenseForm(forms.ModelForm):
    billing_date = forms.DateField(widget=forms.DateInput(format='%Y-%m', attrs={'type': 'month'}), input_formats=['%Y-%m'], label='Billing Period', help_text='Select the billing month; the year and month will be saved automatically.')
    class Meta:
        model = UtilityExpense
        fields = ['hostel', 'expense_type', 'amount', 'billing_year', 'billing_month', 'date_from', 'date_to', 'paid_date', 'usage_amount', 'description']
        widgets = {'billing_year': forms.Select(choices=[(i, i) for i in range(2020, 2030)]), 'billing_month': forms.Select(choices=[(1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'), (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'), (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')]), 'date_from': forms.DateInput(attrs={'type': 'date'}), 'date_to': forms.DateInput(attrs={'type': 'date'}), 'paid_date': forms.DateInput(attrs={'type': 'date'}), 'description': forms.Textarea(attrs={'rows': 3})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['billing_year'].widget = forms.HiddenInput()
        self.fields['billing_month'].widget = forms.HiddenInput()
        self.fields['billing_year'].required = False
        self.fields['billing_month'].required = False
        # Only show active hostels in the dropdown
        self.fields['hostel'].queryset = Hostel.objects.filter(status=True)
        # Make all fields required (except usage_amount)
        optional_fields = {'usage_amount', 'description', 'billing_year', 'billing_month'}
        for field_name, field in self.fields.items():
            if field_name not in optional_fields:
                field.required = True
            # Apply Bootstrap styling
            if not isinstance(field.widget, forms.HiddenInput):
                css_class = 'form-select form-select-sm' if field.widget.__class__.__name__ == 'Select' else 'form-control form-control-sm'
                field.widget.attrs.update({'class': css_class})
        if not self.data:
            initial_date = None
            if self.instance and self.instance.pk and self.instance.billing_year and self.instance.billing_month:
                try:
                    initial_date = date(self.instance.billing_year, self.instance.billing_month, 1)
                except ValueError:
                    initial_date = None
            if initial_date is None:
                today = date.today()
                initial_date = today.replace(day=1)
            self.fields['billing_date'].initial = initial_date
    def clean(self):
        cleaned_data = super().clean()
        billing_date = cleaned_data.get('billing_date')
        if billing_date:
            cleaned_data['billing_year'] = billing_date.year
            cleaned_data['billing_month'] = billing_date.month
        return cleaned_data



class StaffExpenseForm(forms.ModelForm):
    class Meta:
        model = StaffExpense
        fields = ["expense_type", "start_date", "end_date", "amount", "memo"]
        widgets = {"expense_type": forms.Select(attrs={"class": "form-select"}), "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}), "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}), "amount": forms.NumberInput(attrs={"class": "form-control"}), "memo": forms.Textarea(attrs={"class": "form-control", "rows": 4})}


class ThirdPartyServiceRecordBaseForm(forms.ModelForm):
    class Meta:
        model = ThirdPartyServiceRecord
        fields = [
            "service_type",
            "applicant_name",
            "phone_number",
            "applicant_address",
            "service_subject_type",
            "service_subject_address",
            "company_name",
            "company_phone_number",
            "collected_amount",
            "collected_date",
            "remitted_amount",
            "remitted_date",
            "memo",
        ]
        widgets = {
            "service_type": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "applicant_name": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "applicant_address": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 2}),
            "service_subject_type": forms.Select(attrs={"class": "form-select form-select-sm", "data-insurance-field": "true"}),
            "service_subject_address": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 2, "data-insurance-field": "true"}),
            "company_name": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "company_phone_number": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "collected_amount": forms.NumberInput(attrs={"class": "form-control form-control-sm", "min": "0", "step": "0.01"}),
            "collected_date": forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
            "remitted_amount": forms.NumberInput(attrs={"class": "form-control form-control-sm", "min": "0", "step": "0.01"}),
            "remitted_date": forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
            "memo": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["applicant_name"].label = "Applicant Name"
        self.fields["phone_number"].label = "Applicant Phone Number"
        self.fields["applicant_address"].label = "Applicant Address"
        self.fields["service_subject_type"].label = "Insurance For"
        self.fields["service_subject_address"].label = "Insurance Address"
        self.fields["company_name"].label = "Insurance / Guarantor Company Name"
        self.fields["company_phone_number"].label = "Insurance / Guarantor Company Phone Number"
        self.fields["service_subject_type"].required = False
        self.fields["service_subject_address"].required = False
        if "remitted_amount" in self.fields:
            self.fields["remitted_amount"].required = False
        if "remitted_date" in self.fields:
            self.fields["remitted_date"].required = False
        self.fields["memo"].required = True
        if not self.initial.get("collected_date") and not self.instance.pk:
            self.fields["collected_date"].initial = date.today()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("service_type") == ThirdPartyServiceRecord.ServiceType.INSURANCE:
            if not cleaned_data.get("service_subject_type"):
                self.add_error("service_subject_type", "Insurance for what is required for insurance records.")
            if not cleaned_data.get("service_subject_address"):
                self.add_error("service_subject_address", "Insurance address is required for insurance records.")
        remitted_date = cleaned_data.get("remitted_date")
        collected_date = cleaned_data.get("collected_date")
        if remitted_date and collected_date and remitted_date < collected_date:
            self.add_error("remitted_date", "Remitted date cannot be before collected date.")
        return cleaned_data


class ThirdPartyServiceRecordCreateForm(ThirdPartyServiceRecordBaseForm):
    class Meta(ThirdPartyServiceRecordBaseForm.Meta):
        fields = [
            "service_type",
            "applicant_name",
            "phone_number",
            "applicant_address",
            "service_subject_type",
            "service_subject_address",
            "company_name",
            "company_phone_number",
            "collected_amount",
            "collected_date",
            "memo",
        ]


class ThirdPartyServiceRecordUpdateForm(ThirdPartyServiceRecordBaseForm):
    class Meta(ThirdPartyServiceRecordBaseForm.Meta):
        fields = [
            "service_type",
            "applicant_name",
            "phone_number",
            "applicant_address",
            "service_subject_type",
            "service_subject_address",
            "company_name",
            "company_phone_number",
            "collected_amount",
            "collected_date",
            "memo",
        ]


class ThirdPartyServiceRemittanceForm(forms.ModelForm):
    class Meta:
        model = ThirdPartyServiceRecord
        fields = ["remitted_amount", "remitted_date"]
        widgets = {
            "remitted_amount": forms.NumberInput(attrs={"class": "form-control form-control-sm", "min": "0", "step": "0.01"}),
            "remitted_date": forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["remitted_amount"].label = "Remittance Amount"
        self.fields["remitted_date"].label = "Remittance Date"
        self.fields["remitted_amount"].required = True
        self.fields["remitted_date"].required = True

    def clean(self):
        cleaned_data = super().clean()
        remitted_amount = cleaned_data.get("remitted_amount")
        remitted_date = cleaned_data.get("remitted_date")

        if remitted_amount is not None and remitted_amount <= 0:
            self.add_error("remitted_amount", "Remittance amount must be greater than zero.")
        if remitted_amount is not None and self.instance.collected_amount is not None and remitted_amount > self.instance.collected_amount:
            self.add_error("remitted_amount", "Remittance amount cannot be greater than collected amount.")
        if remitted_date and self.instance.collected_date and remitted_date < self.instance.collected_date:
            self.add_error("remitted_date", "Remittance date cannot be before collected date.")

        return cleaned_data


class AdFeeReceiptForm(forms.ModelForm):
    class Meta:
        model = RentalContract
        fields = ['ad_fee_received_amount', 'ad_fee_transfer_fee', 'ad_fee_received_date', 'ad_fee_memo']
        widgets = {
            'ad_fee_received_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'ad_fee_transfer_fee': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'ad_fee_received_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ad_fee_memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Transfer reference or notes (optional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ad_fee_received_amount'].label = 'Actual Amount Received'
        self.fields['ad_fee_transfer_fee'].label = 'Transfer Fee Deducted'
        self.fields['ad_fee_received_date'].label = 'Received Date'
        self.fields['ad_fee_received_amount'].required = True
        self.fields['ad_fee_received_date'].required = True

    def clean(self):
        cleaned_data = super().clean()
        received_amount = cleaned_data.get('ad_fee_received_amount')
        transfer_fee = cleaned_data.get('ad_fee_transfer_fee') or Decimal('0.00')
        if received_amount is not None and received_amount + transfer_fee != self.instance.ad_fee:
            raise forms.ValidationError('Actual amount received plus transfer fee deducted must equal the expected AD fee.')
        return cleaned_data

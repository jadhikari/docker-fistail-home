from datetime import date

from django import forms

from .models import HostelExpense, UtilityExpense


class HostelExpenseForm(forms.ModelForm):
    class Meta:
        model = HostelExpense
        fields = [
            'hostel',
            'purchased_date',
            'purchased_by',
            'amount',
            'memo',
        ]
        widgets = {
            'purchased_date': forms.DateInput(attrs={'type': 'date'}),
            'memo': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make all fields required (except hostel)
        for field_name, field in self.fields.items():
            if field_name not in ['hostel']:
                field.required = True

            # Apply Bootstrap styling
            css_class = 'form-select form-select-sm' if field.widget.__class__.__name__ == 'Select' else 'form-control form-control-sm'
            field.widget.attrs.update({'class': css_class})

        self.fields['hostel'].empty_label = "ALL"


class UtilityExpenseForm(forms.ModelForm):
    billing_date = forms.DateField(
        widget=forms.DateInput(format='%Y-%m', attrs={'type': 'month'}),
        input_formats=['%Y-%m'],
        label='Billing Period',
        help_text='Select the billing month; the year and month will be saved automatically.'
    )

    class Meta:
        model = UtilityExpense
        fields = [
            'hostel',
            'expense_type',
            'amount',
            'billing_year',
            'billing_month',
            'date_from',
            'date_to',
            'paid_date',
            'usage_amount',
            'description',
        ]
        widgets = {
            'billing_year': forms.Select(choices=[(i, i) for i in range(2020, 2030)]),
            'billing_month': forms.Select(choices=[
                (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
            ]),
            'date_from': forms.DateInput(attrs={'type': 'date'}),
            'date_to': forms.DateInput(attrs={'type': 'date'}),
            'paid_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['billing_year'].widget = forms.HiddenInput()
        self.fields['billing_month'].widget = forms.HiddenInput()
        self.fields['billing_year'].required = False
        self.fields['billing_month'].required = False

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


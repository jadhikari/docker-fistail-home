from django import forms
from .models import HostelExpense, UtilityExpense


class HostelExpenseForm(forms.ModelForm):
    class Meta:
        model = HostelExpense
        fields = [
            'hostel',
            'purchased_date',
            'purchased_by',
            'bill_url',
            'memo',
            'amount_before_tax',
            'amount_tax',
        ]
        widgets = {
            'purchased_date': forms.DateInput(attrs={'type': 'date'}),
            'bill_url': forms.Textarea(attrs={'rows': 1}),
            'memo': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        before_tax = cleaned_data.get('amount_before_tax')
        tax = cleaned_data.get('amount_tax')

        if before_tax is not None and tax is not None and tax >= before_tax:
            self.add_error('amount_tax', "Tax must be less than the amount before tax.")


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make all fields required (except hostel and bill_url)
        for field_name, field in self.fields.items():
            if field_name not in ['hostel', 'bill_url']:
                field.required = True

            # Apply Bootstrap styling
            css_class = 'form-select form-select-sm' if field.widget.__class__.__name__ == 'Select' else 'form-control form-control-sm'
            field.widget.attrs.update({'class': css_class})

        self.fields['hostel'].empty_label = "ALL"


class UtilityExpenseForm(forms.ModelForm):
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
            'receipt',
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

        # Make all fields required (except usage_amount and receipt)
        for field_name, field in self.fields.items():
            if field_name not in ['usage_amount', 'receipt', 'description']:
                field.required = True

            # Apply Bootstrap styling
            css_class = 'form-select form-select-sm' if field.widget.__class__.__name__ == 'Select' else 'form-control form-control-sm'
            field.widget.attrs.update({'class': css_class})
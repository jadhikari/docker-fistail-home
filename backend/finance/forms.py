from django import forms
from .models import HostelExpense


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

        # Make all fields required (except hostel)
        for field_name, field in self.fields.items():
            if field_name != 'hostel':
                field.required = True

            # Apply Bootstrap styling
            css_class = 'form-select form-select-sm' if field.widget.__class__.__name__ == 'Select' else 'form-control form-control-sm'
            field.widget.attrs.update({'class': css_class})

        self.fields['hostel'].empty_label = "ALL"
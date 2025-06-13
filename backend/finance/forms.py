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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make all fields required
        for field_name, field in self.fields.items():
            if field_name != 'hostel':
                field.required = True

        # Add "ALL" option to hostel dropdown
        self.fields['hostel'].empty_label = "ALL"
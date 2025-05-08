from django import forms
from .models import Customer
from django_countries.widgets import CountrySelectWidget

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'name', 'date_of_birth', 'email', 'phone_number', 'nationality', 'home_address',
            'parent_phone_number', 'visa_type', 'workplace_or_school_name',
            'workplace_or_school_address', 'workplace_or_school_phone',
            'zairyu_card_number', 'zairyu_card_expire_date',
            'zairyu_card_url', 'passport_url', 'student_card_url', 'status','memo'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'zairyu_card_expire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nationality': CountrySelectWidget(attrs={'class': 'form-select'}),
            'home_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'workplace_or_school_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields:
            if field not in self.Meta.widgets and not isinstance(self.fields[field].widget, (forms.CheckboxInput, CountrySelectWidget)):
                self.fields[field].widget.attrs.update({'class': 'form-control'})

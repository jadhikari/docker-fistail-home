from django import forms
from .models import Hostel, Unit

class HostelForm(forms.ModelForm):
    class Meta:
        model = Hostel
        exclude = ['created_by', 'updated_by']
        widgets = {
            'contract_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'contract_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hostel_type': forms.Select(attrs={'class': 'form-select'}),
            'memo': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hw_contact_num'].label = "House Owner Contact Number"

        for field in self.fields:
            if field not in self.Meta.widgets and not isinstance(self.fields[field].widget, (forms.CheckboxInput,)):
                css_class = 'form-select' if isinstance(self.fields[field].widget, forms.Select) else 'form-control'
                self.fields[field].widget.attrs.update({'class': css_class})

class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['unit_type', 'bedroom_num', 'num_of_beds', 'unit_id', 'image', 'memo']
        widgets = {
                'memo': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            }

    def __init__(self, *args, **kwargs):
        self.hostel = kwargs.pop('hostel', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.hostel:
            instance.hostel = self.hostel
        if commit:
            instance.save()
        return instance
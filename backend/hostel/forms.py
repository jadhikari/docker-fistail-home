from django import forms
from django.core.exceptions import ValidationError
from .models import Hostel, Unit, Bed
from hostel.models import Customer

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
    def __init__(self, *args, **kwargs):
        self.hostel = kwargs.pop('hostel', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = Unit
        fields = ['unit_type', 'bedroom_num', 'num_of_beds', 'unit_id', 'image', 'memo']
        widgets = {
                'memo': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            }

    def clean(self):
        cleaned_data = super().clean()
        unit_type = cleaned_data.get('unit_type')
        bedroom_num = cleaned_data.get('bedroom_num')
        num_of_beds = cleaned_data.get('num_of_beds')
        unit_id = cleaned_data.get('unit_id')

        if not self.hostel:
            raise ValidationError("Hostel is required.")

        if unit_type == 'bedroom':
            if bedroom_num is None:
                self.add_error('bedroom_num', 'This field is required for bedroom units.')
            if num_of_beds is None:
                self.add_error('num_of_beds', 'This field is required for bedroom units.')

            if Unit.objects.filter(
                hostel=self.hostel,
                bedroom_num=bedroom_num,
                unit_type='bedroom'
            ).exclude(pk=self.instance.pk).exists():
                self.add_error('bedroom_num', 'A bedroom with this number already exists in this hostel.')

        else:
            if not unit_id:
                self.add_error('unit_id', 'This field is required for non-bedroom units.')

            if Unit.objects.filter(
                hostel=self.hostel,
                unit_id=unit_id
            ).exclude(pk=self.instance.pk).exists():
                self.add_error('unit_id', 'A unit with this ID already exists in this hostel.')

        return cleaned_data



    
class BedForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.unit = kwargs.pop('unit', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = Bed
        fields = ['bed_num']

    def clean(self):
        cleaned_data = super().clean()
        bed_num = cleaned_data.get('bed_num')

        if self.unit is None:
            raise ValidationError("Unit is required.")

        # Normalize
        if bed_num:
            bed_num = bed_num.upper()
            cleaned_data['bed_num'] = bed_num

        if self.unit.unit_type != 'bedroom':
            raise ValidationError({'bed_num': 'Only bedroom-type units can be assigned beds.'})

        existing_beds = self.unit.beds.exclude(pk=self.instance.pk).count()
        if self.unit.num_of_beds is not None and existing_beds >= self.unit.num_of_beds:
            raise ValidationError({'bed_num': f"This unit can only have {self.unit.num_of_beds} beds."})

        if Bed.objects.filter(unit=self.unit, bed_num__iexact=bed_num).exclude(pk=self.instance.pk).exists():
            raise ValidationError({'bed_num': 'This bed number already exists in this unit.'})

        return cleaned_data



class BedAssignmentForm(forms.ModelForm):
    class Meta:
        model = Bed
        fields = ['customer', 'assigned_date']
        widgets = {
            'assigned_date': forms.DateInput(attrs={'style': 'width: 200px;', 'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['customer'].required = True
        self.fields['assigned_date'].required = True

        assigned_ids = Bed.objects.exclude(customer=self.instance.customer).values_list('customer_id', flat=True)
        self.fields['customer'].queryset = Customer.objects.filter(status=True).exclude(id__in=assigned_ids)

        if self.instance and self.instance.customer and self.instance.assigned_date:
            self.fields['customer'].disabled = True
            self.fields['assigned_date'].disabled = True


class EditReleasedDateForm(forms.ModelForm):
    class Meta:
        model = Bed
        fields = ['released_date']
        widgets = {
            'released_date': forms.DateInput(attrs={'style': 'width: 200px;','type': 'date', 'class': 'form-control'}),
        }
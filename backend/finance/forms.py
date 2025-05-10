from django import forms
from .models import Revenue
from hostel.models import Hostel
from customer.models import Customer

class RevenueForm(forms.ModelForm):
    class Meta:
        model = Revenue
        fields = [
            'title', 'customer', 'year', 'month',
            'deposit', 'deposit_discount_percent',
            'initial_fee', 'initial_fee_discount_percent', 
            'internet', 'utilities', 'rent', 'rent_discount_percent',
            'memo',
        ]
        widgets = {
                'memo': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        customer_id = None
        title = None

        if self.data:
            customer_id = self.data.get('customer')
            title = self.data.get('title')
        elif getattr(self.instance, 'customer', None):
            customer_id = self.instance.customer.id
            title = self.instance.title

        if customer_id and str(customer_id).isdigit():
            try:
                customer = Customer.objects.get(id=int(customer_id))
                if customer.bed_assignment and customer.bed_assignment.unit:
                    hostel = customer.bed_assignment.unit.hostel

                    if title == 'registration_fee':
                        self.fields['deposit'].initial = hostel.deposit_fee
                        self.fields['initial_fee'].initial = hostel.initial_fee

                    elif title == 'rent':
                        self.fields['internet'].initial = hostel.internet_fee
                        self.fields['utilities'].initial = hostel.utilities_fee
                        self.fields['rent'].initial = hostel.rent

            except (Customer.DoesNotExist, AttributeError):
                pass  # fail silently for missing/invalid customer

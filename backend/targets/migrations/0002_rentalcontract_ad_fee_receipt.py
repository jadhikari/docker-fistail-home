from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('targets', '0001_initial'),
    ]

    operations = [
        migrations.AddField(model_name='rentalcontract', name='ad_fee_confirmed_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='rentalcontract', name='ad_fee_confirmed_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_ad_fees', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='rentalcontract', name='ad_fee_memo', field=models.TextField(blank=True, help_text='AD fee receipt reference or notes')),
        migrations.AddField(model_name='rentalcontract', name='ad_fee_received_amount', field=models.DecimalField(blank=True, decimal_places=2, help_text='Actual AD fee amount received after deductions', max_digits=12, null=True, validators=[MinValueValidator(Decimal('0.00'))])),
        migrations.AddField(model_name='rentalcontract', name='ad_fee_received_date', field=models.DateField(blank=True, help_text='Date the AD fee was received', null=True)),
        migrations.AddField(model_name='rentalcontract', name='ad_fee_transfer_fee', field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Transfer fee deducted from the AD fee', max_digits=12, validators=[MinValueValidator(Decimal('0.00'))])),
    ]

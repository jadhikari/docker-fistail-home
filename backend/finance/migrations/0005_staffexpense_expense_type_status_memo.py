# Generated manually to preserve existing TravelExpense records while renaming the model.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finance", "0004_alter_travelexpense_memo"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="TravelExpense",
            new_name="StaffExpense",
        ),
        migrations.AlterModelOptions(
            name="staffexpense",
            options={"verbose_name": "Staff Expense", "verbose_name_plural": "Staff Expenses"},
        ),
        migrations.AddField(
            model_name="staffexpense",
            name="expense_type",
            field=models.CharField(
                choices=[("TRAVEL", "Travel"), ("PURCHASE", "Purchase"), ("OTHER", "Other")],
                default="TRAVEL",
                help_text="Category of the staff expense.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="staffexpense",
            name="status_memo",
            field=models.TextField(blank=True, default="", help_text="Memo recorded when the approval status is changed."),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="staffexpense",
            name="approved_by",
            field=models.ForeignKey(blank=True, help_text="User who approved or rejected the expense.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_staff_expenses", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="staffexpense",
            name="employee",
            field=models.ForeignKey(blank=True, help_text="Employee who submitted the staff expense.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="staff_expenses", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="staffexpense",
            name="approval_status",
            field=models.CharField(choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], db_index=True, default="PENDING", help_text="Current approval status of the staff expense.", max_length=20),
        ),
        migrations.AlterField(
            model_name="staffexpense",
            name="start_date",
            field=models.DateField(help_text="Start date of the expense period."),
        ),
        migrations.AlterField(
            model_name="staffexpense",
            name="end_date",
            field=models.DateField(help_text="End date of the expense period."),
        ),
        migrations.AlterField(
            model_name="staffexpense",
            name="amount",
            field=models.DecimalField(decimal_places=2, help_text="Total staff expense amount.", max_digits=12),
        ),
        migrations.AlterField(
            model_name="staffexpense",
            name="memo",
            field=models.TextField(help_text="Additional information about the staff expense."),
        ),
        migrations.AlterField(
            model_name="staffexpense",
            name="transaction_code",
            field=models.CharField(db_index=True, editable=False, help_text="Unique transaction code for this staff expense.", max_length=6, unique=True),
        ),
    ]

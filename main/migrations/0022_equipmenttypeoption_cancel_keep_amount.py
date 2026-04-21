from decimal import Decimal

from django.db import migrations, models


def set_default_cancel_amounts(apps, schema_editor):
    EquipmentTypeOption = apps.get_model('main', 'EquipmentTypeOption')
    EquipmentTypeOption.objects.all().update(cancel_keep_amount=Decimal('750'))
    EquipmentTypeOption.objects.filter(value__iexact='Хд - Холодильники').update(cancel_keep_amount=Decimal('1000'))


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0021_seed_default_equipment_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipmenttypeoption',
            name='cancel_keep_amount',
            field=models.DecimalField(decimal_places=2, default=750, max_digits=10, verbose_name='Остаток мастеру при отмене'),
        ),
        migrations.RunPython(set_default_cancel_amounts, migrations.RunPython.noop),
    ]

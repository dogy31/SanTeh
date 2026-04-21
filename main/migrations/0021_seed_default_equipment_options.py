from django.db import migrations


DEFAULT_EQUIPMENT_TYPES = [
    'См - Cтиральные машины',
    'ПМ - Посудомоечные машины',
    'Хд - Холодильники',
    'Вд - Водонагреватели',
    'Дш - Духовые шкафы',
    'ВП - Варочные панель',
    'Тв - Телевизоры',
    'Км - Кофемашины',
    'Пром - Промышленная техника',
]


def seed_defaults(apps, schema_editor):
    EquipmentTypeOption = apps.get_model('main', 'EquipmentTypeOption')
    for item in DEFAULT_EQUIPMENT_TYPES:
        EquipmentTypeOption.objects.get_or_create(value=item)


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0020_request_performed_work'),
    ]

    operations = [
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]

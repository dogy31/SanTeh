# Сводит две параллельные ветки от 0022: WorkerInstruction и поля AddressBaseOption.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0023_addressbaseoption_apartment_and_more'),
        ('main', '0023_workerinstruction'),
    ]

    operations = []

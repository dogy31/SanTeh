from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0019_profile_worker_equipment_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='request',
            name='performed_work',
            field=models.TextField(blank=True, default='', verbose_name='Проделаные работы'),
        ),
    ]

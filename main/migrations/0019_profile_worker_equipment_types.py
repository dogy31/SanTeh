from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0018_request_visit_time_transportexpense'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='worker_equipment_types',
            field=models.TextField(blank=True, default='', verbose_name='Виды техники мастера'),
        ),
    ]

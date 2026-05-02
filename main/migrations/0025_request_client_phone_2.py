from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0024_merge_addressbaseoption_workerinstruction'),
    ]

    operations = [
        migrations.AddField(
            model_name='request',
            name='client_phone_2',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Доп. телефон клиента'),
        ),
    ]

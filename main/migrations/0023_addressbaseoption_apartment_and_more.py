from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0022_equipmenttypeoption_cancel_keep_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='addressbaseoption',
            name='house_number',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='Дом по умолчанию'),
        ),
        migrations.AddField(
            model_name='addressbaseoption',
            name='entrance',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='Подъезд по умолчанию'),
        ),
        migrations.AddField(
            model_name='addressbaseoption',
            name='floor',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='Этаж по умолчанию'),
        ),
        migrations.AddField(
            model_name='addressbaseoption',
            name='apartment',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='Квартира по умолчанию'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0015_pushsubscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='request',
            name='apartment',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Квартира'),
        ),
        migrations.AddField(
            model_name='request',
            name='entrance',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Подъезд'),
        ),
        migrations.AddField(
            model_name='request',
            name='floor',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Этаж'),
        ),
        migrations.AddField(
            model_name='request',
            name='house_number',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Номер дома'),
        ),
        migrations.AlterField(
            model_name='request',
            name='client_name',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Имя клиента'),
        ),
        migrations.CreateModel(
            name='AddressBaseOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=200, unique=True, verbose_name='Базовый адрес')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
            ],
            options={
                'ordering': ['value'],
            },
        ),
        migrations.CreateModel(
            name='EquipmentTypeOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=100, unique=True, verbose_name='Вид техники')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
            ],
            options={
                'ordering': ['value'],
            },
        ),
    ]

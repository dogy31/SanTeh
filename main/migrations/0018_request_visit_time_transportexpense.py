from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0017_request_accepted_and_documents'),
    ]

    operations = [
        migrations.AddField(
            model_name='request',
            name='visit_time',
            field=models.TimeField(blank=True, null=True, verbose_name='Время визита'),
        ),
        migrations.CreateModel(
            name='TransportExpense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.CharField(blank=True, default='', max_length=255, verbose_name='Описание')),
                ('receipt_photo', models.ImageField(blank=True, null=True, upload_to='transport/', verbose_name='Фото/чек')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transport_expenses', to='main.request')),
            ],
        ),
    ]

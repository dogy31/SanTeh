from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0014_notification'),
    ]

    operations = [
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.TextField(verbose_name='Endpoint')),
                ('p256dh', models.CharField(max_length=255, verbose_name='P256DH ключ')),
                ('auth', models.CharField(max_length=255, verbose_name='Auth ключ')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('active', models.BooleanField(default=True, verbose_name='Активна')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='push_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
                'unique_together': {('user', 'endpoint')},
            },
        ),
    ]

# Generated manually for WorkerInstruction

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0022_equipmenttypeoption_cancel_keep_amount'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkerInstruction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body_html', models.TextField(blank=True, default='', verbose_name='Содержимое (HTML)')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Инструкция для мастеров',
                'verbose_name_plural': 'Инструкция для мастеров',
            },
        ),
    ]

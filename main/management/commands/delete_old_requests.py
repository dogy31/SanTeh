from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from main.models import Request

class Command(BaseCommand):
    help = 'Удаляет заявки старше 30 дней и связанные с ними данные'

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=30)
        old_requests = Request.objects.filter(created_date__lt=cutoff_date)
        count = old_requests.count()
        if count > 0:
            old_requests.delete()  # Каскадное удаление удалит связанные Photo и Part
            self.stdout.write(self.style.SUCCESS(f'Удалено {count} старых заявок'))
        else:
            self.stdout.write('Нет старых заявок для удаления')
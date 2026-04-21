from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Администратор'),
        ('worker', 'Рабочий'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField('Телефон', max_length=20)
    role = models.CharField('Роль', max_length=10, choices=ROLE_CHOICES, default='worker')
    tg_code = models.CharField('Код из Telegram', max_length=10, blank=True, null=True)
    max_code = models.CharField('Код из MAX', max_length=10, blank=True, null=True)
    worker_equipment_types = models.TextField('Виды техники мастера', blank=True, default='')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    def get_worker_equipment_values(self):
        if not self.worker_equipment_types:
            return []
        # Поддержка старого формата с кодами для обратной совместимости.
        legacy_map = {
            'SM': 'См - Cтиральные машины',
            'PM': 'ПМ - Посудомоечные машины',
            'HD': 'Хд - Холодильники',
            'VD': 'Вд - Водонагреватели',
            'DSH': 'Дш - Духовые шкафы',
            'VP': 'ВП - Варочные панель',
            'TV': 'Тв - Телевизоры',
            'KM': 'Км - Кофемашины',
            'PROM': 'Пром - Промышленная техника',
        }
        values = []
        for raw in self.worker_equipment_types.split(','):
            item = raw.strip()
            if not item:
                continue
            normalized = legacy_map.get(item, item)
            if normalized not in values:
                values.append(normalized)
        return values

    def set_worker_equipment_values(self, values):
        clean = []
        for value in (values or []):
            item = (value or '').strip()
            if item and item not in clean:
                clean.append(item)
        self.worker_equipment_types = ','.join(clean)

    def get_worker_equipment_labels(self):
        return self.get_worker_equipment_values()

class Request(models.Model):
    STATUS_CHOICES = (
        ('new', 'Новая'),
        ('accepted', 'Принял'),
        ('in-progress', 'В работе'),
        ('done', 'Выполнена'),
        ('cancelled', 'Отменена'),
    )
    description = models.TextField('Описание задачи')
    client_name = models.CharField('Имя клиента', max_length=100, blank=True, default='')
    client_phone = models.CharField('Телефон клиента', max_length=20)
    client_email = models.EmailField('Email клиента', blank=True)
    client_address = models.CharField('Адрес клиента', max_length=200, blank=True)
    house_number = models.CharField('Номер дома', max_length=20, blank=True, default='')
    entrance = models.CharField('Подъезд', max_length=20, blank=True, default='')
    floor = models.CharField('Этаж', max_length=20, blank=True, default='')
    apartment = models.CharField('Квартира', max_length=20, blank=True, default='')
    equipment_type = models.CharField('Вид техники', max_length=100, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requests', verbose_name='Исполнитель')
    created_date = models.DateTimeField('Дата создания', auto_now_add=True)
    deadline_date = models.DateField('Дата выполнения', null=True, blank=True)
    visit_time = models.TimeField('Время визита', null=True, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, null=True, blank=True)
    comment = models.TextField('Комментарий рабочего', blank=True)
    performed_work = models.TextField('Проделаные работы', blank=True, default='')
    money_delivered = models.BooleanField('Деньги сданы', default=False)
    overdue_reason = models.TextField('Причина просрочки', blank=True, default='')
    prepayment_amount = models.DecimalField('Сумма предоплаты', max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    worker_percent = models.PositiveSmallIntegerField('Процент рабочего от чистой прибыли', default=50)

    def __str__(self):
        return f"Заявка #{self.id} - {self.client_name or 'без имени'}"


class EquipmentTypeOption(models.Model):
    value = models.CharField('Вид техники', max_length=100, unique=True)
    cancel_keep_amount = models.DecimalField('Остаток мастеру при отмене', max_digits=10, decimal_places=2, default=750)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        ordering = ['value']

    def __str__(self):
        return self.value


class AddressBaseOption(models.Model):
    value = models.CharField('Базовый адрес', max_length=200, unique=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        ordering = ['value']

    def __str__(self):
        return self.value

class Photo(models.Model):
    PHOTO_TYPE_CHOICES = (
        ('contract', 'Договор'),
        ('receipt', 'Чек'),
    )
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField('Фото', upload_to='requests/')
    photo_type = models.CharField('Тип фото', max_length=10, choices=PHOTO_TYPE_CHOICES, default='receipt')
    uploaded_at = models.DateTimeField('Дата загрузки', auto_now_add=True)

    def __str__(self):
        return f"Фото к заявке #{self.request.id} ({self.get_photo_type_display()})"

class Part(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='parts')
    name = models.CharField('Название детали', max_length=200)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, null=True, blank=True)
    receipt_photo = models.ImageField('Чек за деталь', upload_to='parts/', blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.price}₽"


class TransportExpense(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='transport_expenses')
    note = models.CharField('Описание', max_length=255, blank=True, default='')
    receipt_photo = models.ImageField('Фото/чек', upload_to='transport/', blank=True, null=True)

    def __str__(self):
        return f"Транспортные для заявки #{self.request_id}"

class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = (
        ('new_request', 'Новая заявка'),
        ('reassign', 'Переназначение заявки'),
        ('cancel', 'Отмена заявки'),
        ('complete', 'Заявка выполнена'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField('Тип уведомления', max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField('Заголовок', max_length=200)
    text = models.TextField('Текст уведомления')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    is_read = models.BooleanField('Прочитано', default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"


class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.TextField('Endpoint')
    p256dh = models.CharField('P256DH ключ', max_length=255)
    auth = models.CharField('Auth ключ', max_length=255)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    active = models.BooleanField('Активна', default=True)

    class Meta:
        unique_together = ('user', 'endpoint')
        ordering = ['-updated_at']

    def __str__(self):
        return f"PushSubscription {self.user.username} - {self.endpoint[:40]}"


class Document(models.Model):
    title = models.CharField('Название документа', max_length=200)
    file = models.FileField('Файл', upload_to='documents/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_documents')
    created_at = models.DateTimeField('Дата загрузки', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
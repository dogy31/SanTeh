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

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class Request(models.Model):
    STATUS_CHOICES = (
        ('new', 'Новая'),
        ('in-progress', 'В работе'),
        ('done', 'Выполнена'),
    )
    description = models.TextField('Описание задачи')
    client_name = models.CharField('Имя клиента', max_length=100)
    client_phone = models.CharField('Телефон клиента', max_length=20)
    client_email = models.EmailField('Email клиента', blank=True)
    client_address = models.CharField('Адрес клиента', max_length=200, blank=True)
    equipment_type = models.CharField('Вид техники', max_length=100, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requests', verbose_name='Исполнитель')
    created_date = models.DateTimeField('Дата создания', auto_now_add=True)
    deadline_date = models.DateField('Дата выполнения', null=True, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, null=True, blank=True)
    comment = models.TextField('Комментарий рабочего', blank=True)
    money_delivered = models.BooleanField('Деньги сданы', default=False)
    overdue_reason = models.TextField('Причина просрочки', blank=True, default='')
    prepayment_made = models.BooleanField('Предоплата внесена', default=False)

    def __str__(self):
        return f"Заявка #{self.id} - {self.client_name}"

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
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Profile, Request, Photo, Part
import os, sys
import requests
from datetime import datetime, date

# add tg_bot folder to path so we can reuse its sqlite helper
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
tg_bot_path = os.path.join(project_root, 'Messenger_bot')
if tg_bot_path not in sys.path:
    sys.path.append(tg_bot_path)
try:
    import database as tg_database
    import config as tg_config
    BOT_TOKEN = getattr(tg_config, 'BOT_TOKEN', None)
    MAX_TOKEN = getattr(tg_config, 'MAX_TOKEN', None)
    SMS_API_KEY = getattr(tg_config, 'SMS_API_KEY', None)
except Exception:
    tg_database = None
    BOT_TOKEN = None
    MAX_TOKEN = None
    SMS_API_KEY = None
import json
from datetime import datetime, timedelta

# Регистрация
def register(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        role = 'worker' 
        tg_token = request.POST.get('tg_token')
        max_token = request.POST.get('max_token')
        messengers = request.POST.getlist('messengers')  # список выбранных мессенджеров

        # Валидация обязательных полей
        if not name or not phone or not password or not password2:
            return render(request, 'main/register.html', {'error': 'Заполните все обязательные поля'})
        
        if password != password2:
            return render(request, 'main/register.html', {'error': 'Пароли не совпадают'})

        if 'telegram' in messengers and not tg_token:
            return render(request, 'main/register.html', {'error': 'Если вы выбрали Telegram, то получите код'})
        if 'max' in messengers and not max_token:
            return render(request, 'main/register.html', {'error': 'Если вы выбрали MAX, то получите код'})

        tg_id = None
        max_id = None
        if tg_database:
            if 'telegram' in messengers:
                tg_link = tg_database.get_telegram(tg_token)
                if not tg_link or not tg_link[0]:
                    return render(request, 'main/register.html', {'error': 'Telegram не привязан: отправьте код боту'})
                tg_id = str(tg_link[0])
            if 'max' in messengers:
                max_link = tg_database.get_max(max_token)
                if not max_link or not max_link[0]:
                    return render(request, 'main/register.html', {'error': 'MAX не привязан: отправьте код боту'})
                max_id = str(max_link[0])

        if User.objects.filter(username=phone).exists():
            return render(request, 'main/register.html', {'error': 'Пользователь с таким номером телефона уже существует'})
        user = User.objects.create_user(username=phone, email=phone, password=password, first_name=name)
        Profile.objects.create(user=user, phone=phone, role=role, tg_code=tg_id, max_code=max_id)
        return redirect('login')
    return render(request, 'main/register.html', {'max_enabled': bool(MAX_TOKEN)})

# Вход
def login_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        user = authenticate(request, username=phone, password=password)
        if user:
            login(request, user)
            profile = user.profile
            if profile.role == 'admin':
                return redirect('admin_dashboard')
            else:
                return redirect('worker_dashboard')
        else:
            return render(request, 'main/login.html', {'error': 'Неверные данные'})
    return render(request, 'main/login.html')

# Выход
def logout_view(request):
    logout(request)
    return redirect('login')

# Админ-панель
@login_required
def admin_dashboard(request):
    if request.user.profile.role != 'admin':
        return redirect('worker_dashboard')
    workers = User.objects.filter(profile__role='worker')
    return render(request, 'main/admin.html', {'workers': workers, 'max_enabled': bool(MAX_TOKEN)})

# Рабочая панель
@login_required
def worker_dashboard(request):
    if request.user.profile.role != 'worker':
        return redirect('admin_dashboard')
    return render(request, 'main/worker.html', {'max_enabled': bool(MAX_TOKEN)})

# Создание заявки (админ)
@login_required
def create_request(request):
    if request.method == 'POST':
        data = request.POST
        worker_id = data.get('worker_id')
        client_address = data.get('client_address', '').strip()
        if not client_address:
            return JsonResponse({'error': 'Адрес обязателен для заполнения'}, status=400)
        req = Request.objects.create(
            description=data['description'],
            client_name=data['client_name'],
            client_phone=data['client_phone'],
            client_email=data.get('client_email', ''),
            client_address=client_address,
            equipment_type=data.get('equipment_type', ''),
            assigned_to_id=worker_id if worker_id else None,
            deadline_date=data.get('deadline_date')
        )
        # Отправка уведомления в Telegram и MAX
        try:
            if worker_id:
                worker = User.objects.filter(pk=worker_id).first()
                if worker and hasattr(worker, 'profile'):
                    profile = worker.profile
                    now = datetime.now()
                    text = f"""
━━━━━━━━━━━━━
   🚀 НОВАЯ ЗАЯВКА #{req.id}
   от {now.strftime('%d.%m.%Y %H:%M')}
━━━━━━━━━━━━━
📌 ОПИСАНИЕ РАБОТ:
`{req.description}`
━━━━━━━━━━━━━
👤 КЛИЕНТ: {req.client_name}
📞 ТЕЛЕФОН: `{req.client_phone}`
📍 АДРЕС: {req.client_address or '—'}
━━━━━━━━━━━━━
"""
                    try:
                        if profile.tg_code and BOT_TOKEN:
                            url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
                            requests.post(url, json={'chat_id': profile.tg_code, 'text': text}, timeout=3)
                        if profile.max_code and MAX_TOKEN:
                            # Предполагаем аналогичный API для MAX
                            url = f'https://api.max.org/bot{MAX_TOKEN}/sendMessage'
                            requests.post(url, json={'chat_id': profile.max_code, 'text': text}, timeout=3)
                        else:
                            requests.post('http://127.0.0.1:5000/create_ticket', json={'user_id': worker.email, 'text': text}, timeout=3)
                    except Exception:
                        print('Не удалось отправить уведомление')
        except Exception:
            pass
        return JsonResponse({'success': True, 'id': req.id})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Редактирование заявки (рабочий / админ)
@login_required
def edit_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    # Проверка прав: только назначенный рабочий или админ
    if request.user.profile.role != 'admin' and req.assigned_to != request.user:
        return JsonResponse({'error': 'permission denied'}, status=403)

    if request.method == 'POST':
        # Обновляем основные поля
        req.client_name = request.POST.get('client_name', req.client_name)
        req.client_email = request.POST.get('client_email', '')
        req.client_address = request.POST.get('client_address', '')
        req.equipment_type = request.POST.get('equipment_type', req.equipment_type)
        price = request.POST.get('price')
        if price:
            req.price = price
        req.comment = request.POST.get('comment', '')
        req.overdue_reason = request.POST.get('overdue_reason', '')
        # Обновление предоплаты и статуса
        prepayment = request.POST.get('prepayment_made') == 'true'
        if prepayment and req.status == 'new':
            req.status = 'in-progress'
        req.prepayment_made = prepayment
        req.save()

        # Обработка договора
        if 'contract_photos' in request.FILES:
            req.photos.filter(photo_type='contract').delete()
            contract_file = request.FILES['contract_photos']
            Photo.objects.create(request=req, image=contract_file, photo_type='contract')
        elif request.POST.get('delete_contract') == 'true':
            req.photos.filter(photo_type='contract').delete()

        # Обработка деталей
        parts_data_json = request.POST.get('parts_data')
        if parts_data_json:
            parts_data = json.loads(parts_data_json)
            # Удаляем старые детали
            req.parts.all().delete()
            for i, part in enumerate(parts_data):
                part_obj = Part(
                    request=req,
                    name=part.get('name', ''),
                    price=part.get('price') if part.get('price') else None
                )
                photo_field = f'part_photo_{i}'
                if photo_field in request.FILES:
                    part_obj.receipt_photo = request.FILES[photo_field]
                part_obj.save()

        return JsonResponse({'success': True})

    # GET — вернуть данные
    parts_data = []
    for part in req.parts.all():
        parts_data.append({
            'id': part.id,
            'name': part.name,
            'price': str(part.price) if part.price else None,
            'receipt_photo_url': part.receipt_photo.url if part.receipt_photo else None,
        })
    data = {
        'id': req.id,
        'description': req.description,
        'client_name': req.client_name,
        'client_phone': req.client_phone,
        'client_email': req.client_email,
        'client_address': req.client_address,
        'equipment_type': req.equipment_type,
        'price': str(req.price) if req.price else None,
        'comment': req.comment,
        'photos': [{'image': p.image.url, 'photo_type': p.photo_type} for p in req.photos.all()],
        'status': req.status,
        'parts': parts_data,
        'overdue_reason': req.overdue_reason,
        'is_overdue': date.today() > req.deadline_date if req.deadline_date else False,
        'worker_id': req.assigned_to.id if req.assigned_to else '',
        'prepayment_made': req.prepayment_made,
    }
    return JsonResponse(data)

def send_sms(phone, message):
    if not SMS_API_KEY:
        print(f"SMS not sent (no API key): {phone} - {message}")
        return
    url = "https://sms.ru/sms/send"
    params = {
        'api_id': SMS_API_KEY,
        'to': phone,
        'msg': message,
        'json': 1
    }
    try:
        response = requests.get(url, params=params)
        result = response.json()
        if result.get('status') == 'OK':
            print(f"SMS sent to {phone}")
        else:
            print(f"SMS failed: {result}")
    except Exception as e:
        print(f"SMS error: {e}")

# Закрытие заявки (рабочий)
@login_required
def close_request(request, pk):
    if request.method == 'POST':
        req = get_object_or_404(Request, pk=pk)
        # Проверяем наличие цены
        if not req.price:
            return JsonResponse({'error': 'Цена не указана'}, status=400)
        # Проверяем наличие договора (фото с типом 'contract')
        if not req.photos.filter(photo_type='contract').exists():
            return JsonResponse({'error': 'Не прикреплен договор'}, status=400)
        # Проверка: у всех деталей должен быть чек
        parts = req.parts.all()
        for part in parts:
            if not part.receipt_photo:
                return JsonResponse({'error': f'Отсутствует чек для детали "{part.name}"'}, status=400)
        req.status = 'done'
        req.save()
        # Отправка СМС клиенту
        if req.client_phone:
            completion_date = date.today().strftime('%d.%m.%Y')
            message = f"Ваша заявка выполнена {completion_date}. Сумма: {req.price} руб. Гарантия 14 дней."
            send_sms(req.client_phone, message)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Просмотр заявки (админ)
@login_required
def view_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    # Вычисляем себестоимость, чистую прибыль и зарплату рабочего
    cost_price = sum(float(part.price) for part in req.parts.all() if part.price)
    net_profit = None
    worker_salary = None
    if req.price:
        net_profit = float(req.price) - cost_price
        worker_salary = net_profit * 0.5 if net_profit else 0
    data = {
        'id': req.id,
        'description': req.description,
        'client_name': req.client_name,
        'client_phone': req.client_phone,
        'client_email': req.client_email,
        'client_address': req.client_address,
        'equipment_type': req.equipment_type,
        'status': req.status,
        'price': str(req.price) if req.price else None,
        'cost_price': round(cost_price, 2),
        'net_profit': round(net_profit, 2) if net_profit is not None else None,
        'worker_salary': round(worker_salary, 2) if worker_salary is not None else None,
        'money_delivered': req.money_delivered,
        'prepayment_made': req.prepayment_made,
        'created_date': req.created_date.strftime('%d.%m.%Y %H:%M'),
        'comment': req.comment,
        'worker': req.assigned_to.first_name if req.assigned_to else '',
        'photos': [{'image': p.image.url, 'photo_type': p.photo_type} for p in req.photos.all()],
        'parts': [{'id': p.id, 'name': p.name, 'price': str(p.price) if p.price else None, 'receipt_photo_url': p.receipt_photo.url if p.receipt_photo else None} for p in req.parts.all()],
        'overdue_reason': req.overdue_reason,
    }
    return JsonResponse(data)

# Обновление чекбокса "деньги сданы"
@csrf_exempt
def update_money_delivered(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        req_id = data.get('id')
        value = data.get('value')
        req = get_object_or_404(Request, pk=req_id)
        if req.status == 'done':
            req.money_delivered = value
            req.save()
            return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid'}, status=400)

def get_requests(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'auth required'}, status=401)
    requests = Request.objects.all().order_by('-created_date')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    price_from = request.GET.get('price_from')
    price_to = request.GET.get('price_to')
    worker_id = request.GET.get('worker')
    status = request.GET.get('status')

    if date_from:
        requests = requests.filter(created_date__gte=date_from)
    if date_to:
        requests = requests.filter(created_date__lte=date_to + ' 23:59:59')
    if price_from:
        requests = requests.filter(price__gte=price_from)
    if price_to:
        requests = requests.filter(price__lte=price_to)
    if worker_id:
        requests = requests.filter(assigned_to_id=worker_id)
    if status:
        requests = requests.filter(status=status)

    data = []
    for r in requests:
        # Вычисляем себестоимость, чистую прибыль, зарплату
        cost_price = sum(float(part.price) for part in r.parts.all() if part.price)
        net_profit = None
        worker_salary = None
        if r.price:
            net_profit = float(r.price) - cost_price
            worker_salary = net_profit * 0.5 if net_profit else 0
        data.append({
            'id': r.id,
            'description': r.description,
            'client_name': r.client_name,
            'client_phone': r.client_phone,
            'client_address': r.client_address,
            'equipment_type': r.equipment_type,
            'status': r.status,
            'price': str(r.price) if r.price else None,
            'cost_price': round(cost_price, 2),
            'net_profit': round(net_profit, 2) if net_profit is not None else None,
            'worker_salary': round(worker_salary, 2) if worker_salary is not None else None,
            'money_delivered': r.money_delivered,
            'prepayment_made': r.prepayment_made,
            'worker_name': r.assigned_to.first_name if r.assigned_to else '',
            'created_date': r.created_date.isoformat(),
            'deadline_date': r.deadline_date.isoformat() if r.deadline_date else None,
        })
    return JsonResponse(data, safe=False)

def get_worker_requests(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'auth required'}, status=401)
    requests = Request.objects.filter(assigned_to=request.user).order_by('-created_date')

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    price_from = request.GET.get('price_from')
    price_to = request.GET.get('price_to')
    status = request.GET.get('status')

    if date_from:
        requests = requests.filter(created_date__gte=date_from)
    if date_to:
        requests = requests.filter(created_date__lte=date_to + ' 23:59:59')
    if price_from:
        requests = requests.filter(price__gte=price_from)
    if price_to:
        requests = requests.filter(price__lte=price_to)
    if status:
        requests = requests.filter(status=status)

    data = []
    for r in requests:
        data.append({
            'id': r.id,
            'description': r.description,
            'client_name': r.client_name,
            'client_phone': r.client_phone,
            'client_email': r.client_email,
            'client_address': r.client_address,
            'equipment_type': r.equipment_type,
            'status': r.status,
            'price': str(r.price) if r.price else None,
            'money_delivered': r.money_delivered,
            'prepayment_made': r.prepayment_made,
            'worker_name': r.assigned_to.first_name if r.assigned_to else '',
            'created_date': r.created_date.isoformat(),
            'photos': [{'image': p.image.url, 'photo_type': p.photo_type} for p in r.photos.all()],
        })
    return JsonResponse(data, safe=False)

def reopen_request(request, pk):
    if request.method == 'POST' and request.user.is_authenticated and request.user.profile.role == 'admin':
        req = get_object_or_404(Request, pk=pk)
        if req.status == 'done':
            req.status = 'in-progress'
            req.save()
            return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def generate_tg_code(request):
    if request.method == 'POST':
        try:
            import random, uuid, json
            user_id = None
            if request.content_type == 'application/json':
                try:
                    payload = json.loads(request.body.decode('utf-8') or '{}')
                    user_id = payload.get('user_id')
                except Exception:
                    user_id = None
            else:
                user_id = request.POST.get('user_id')

            if not user_id and request.user.is_authenticated:
                user_id = str(request.user.id)
            site_user_id = user_id or uuid.uuid4().hex
            code = ''.join(random.choices('0123456789', k=6))
            if tg_database:
                tg_database.save_code(site_user_id, code)
            return JsonResponse({'code': code, 'token': site_user_id, 'message': 'Отправьте код боту'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def generate_max_code(request):
    if request.method == 'POST':
        if not MAX_TOKEN:
            return JsonResponse({'error': 'MAX мессенджер не настроен'}, status=400)
        try:
            import random, uuid, json
            user_id = None
            if request.content_type == 'application/json':
                try:
                    payload = json.loads(request.body.decode('utf-8') or '{}')
                    user_id = payload.get('user_id')
                except Exception:
                    user_id = None
            else:
                user_id = request.POST.get('user_id')

            if not user_id and request.user.is_authenticated:
                user_id = str(request.user.id)
            site_user_id = user_id or uuid.uuid4().hex
            code = ''.join(random.choices('0123456789', k=6))
            if tg_database:
                tg_database.save_code(site_user_id, code)
            return JsonResponse({'code': code, 'token': site_user_id, 'message': 'Отправьте код MAX боту'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def bind_messengers(request):
    if request.method == 'POST' and request.user.is_authenticated:
        tg_token = request.POST.get('tg_token')
        max_token = request.POST.get('max_token')
        profile = request.user.profile
        if tg_database and tg_token:
            tg_link = tg_database.get_telegram(tg_token)
            if tg_link and tg_link[0]:
                profile.tg_code = str(tg_link[0])
        if tg_database and max_token:
            max_link = tg_database.get_max(max_token)
            if max_link and max_link[0]:
                profile.max_code = str(max_link[0])
        profile.save()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request'}, status=400)
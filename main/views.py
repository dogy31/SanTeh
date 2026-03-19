from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Profile, Request, Photo
import os, sys
import requests
from datetime import datetime

# add tg_bot folder to path so we can reuse its sqlite helper
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
tg_bot_path = os.path.join(project_root, 'tg_bot')
if tg_bot_path not in sys.path:
    sys.path.append(tg_bot_path)
try:
    import database as tg_database
    import config as tg_config
    BOT_TOKEN = getattr(tg_config, 'BOT_TOKEN', None)
except Exception:
    tg_database = None
    BOT_TOKEN = None
import json
from datetime import datetime, timedelta

# Регистрация
def register(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        role = request.POST.get('role')
        tg_token = request.POST.get('tg_token')

        # Проверяем привязку Telegram по сгенерированному токену
        if not tg_token:
            return render(request, 'main/register.html', {'error': 'Сначала получите код для привязки Telegram'})

        if tg_database:
            tg_link = tg_database.get_telegram(tg_token)
        else:
            tg_link = None

        if not tg_link or not tg_link[0]:
            return render(request, 'main/register.html', {'error': 'Telegram не привязан: отправьте код боту'})

        if User.objects.filter(username=email).exists():
            return render(request, 'main/register.html', {'error': 'Пользователь уже существует'})
        user = User.objects.create_user(username=email, email=email, password=password, first_name=name)
        # tg_link[0] содержит telegram_id, сохраним его в Profile.tg_code
        Profile.objects.create(user=user, phone=phone, role=role, tg_code=str(tg_link[0]))
        return redirect('login')
    return render(request, 'main/register.html')

# Вход
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
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
    return render(request, 'main/admin.html', {'workers': workers})

# Рабочая панель
@login_required
def worker_dashboard(request):
    if request.user.profile.role != 'worker':
        return redirect('admin_dashboard')
    return render(request, 'main/worker.html')

# Создание заявки (админ)
@login_required
def create_request(request):
    if request.method == 'POST':
        data = request.POST
        worker_id = data.get('worker_id')
        deadline = int(data.get('deadline', 3))
        req = Request.objects.create(
            description=data['description'],
            client_name=data['client_name'],
            client_phone=data['client_phone'],
            client_email=data.get('client_email', ''),
            client_address=data.get('client_address', ''),
            assigned_to_id=worker_id if worker_id else None,
            deadline_days=deadline,
        )
        # После создания отправим уведомление рабочему через локальный tg_bot API
        try:
            if worker_id:
                from django.contrib.auth.models import User as DjangoUser
                worker = DjangoUser.objects.filter(pk=worker_id).first()
                if worker and hasattr(worker, 'profile') and worker.profile.tg_code:
                    telegram_id = worker.profile.tg_code
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

⏳ СРОК: {req.deadline_days}
━━━━━━━━━━━━━
"""
                    try:
                        if BOT_TOKEN:
                            url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
                            requests.post(url, json={'chat_id': telegram_id, 'text': text}, timeout=3)
                        else:
                            # fallback: try local tg_bot api_server
                            requests.post('http://127.0.0.1:5000/create_ticket', json={'user_id': worker.email, 'text': text}, timeout=3)
                    except Exception:
                        print('Не удалось отправить уведомление в Telegram (создание заявки)')
        except Exception:
            pass
        return JsonResponse({'success': True, 'id': req.id})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Редактирование заявки (рабочий)
@login_required
def edit_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    # Проверка прав: только назначенный рабочий или админ
    if request.user.profile.role != 'admin' and req.assigned_to != request.user:
        return JsonResponse({'error': 'permission denied'}, status=403)

    if request.method == 'POST':
        # Обновляем поля (кроме телефона и описания)
        req.client_name = request.POST.get('client_name', req.client_name)
        req.client_email = request.POST.get('client_email', '')
        req.client_address = request.POST.get('client_address', '')
        price = request.POST.get('price')
        if price:
            req.price = price
        req.comment = request.POST.get('comment', '')
        if req.status == 'new':
            req.status = 'in-progress'  # автоматически в работу
        req.save()

        # Обработка фото
        files = request.FILES.getlist('photos')
        for f in files:
            if req.photos.count() < 5:  # ограничение 5 фото
                Photo.objects.create(request=req, image=f)
        return JsonResponse({'success': True})

    # GET — вернуть данные
    data = {
        'id': req.id,
        'description': req.description,
        'client_name': req.client_name,
        'client_phone': req.client_phone,  # нельзя менять
        'client_email': req.client_email,
        'client_address': req.client_address,
        'price': str(req.price) if req.price else None,
        'comment': req.comment,
        'photos': [p.image.url for p in req.photos.all()],
        'status': req.status,
    }
    return JsonResponse(data)

# Закрытие заявки (рабочий)
@login_required
def close_request(request, pk):
    if request.method == 'POST':
        req = get_object_or_404(Request, pk=pk)
        # Проверяем наличие цены и хотя бы одного фото
        if not req.price:
            return JsonResponse({'error': 'Цена не указана'}, status=400)
        if req.photos.count() == 0:
            return JsonResponse({'error': 'Не прикреплено ни одного фото'}, status=400)
        req.status = 'done'
        req.save()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Просмотр заявки (админ) — возвращает HTML-фрагмент или данные
@login_required
def view_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    # Вернём JSON для модального окна
    data = {
        'id': req.id,
        'description': req.description,
        'client_name': req.client_name,
        'client_phone': req.client_phone,
        'client_email': req.client_email,
        'client_address': req.client_address,
        'status': req.status,
        'price': str(req.price) if req.price else None,
        'money_delivered': req.money_delivered,
        'created_date': req.created_date.strftime('%d.%m.%Y %H:%M'),
        'comment': req.comment,
        'worker': req.assigned_to.first_name if req.assigned_to else '',
        'photos': [p.image.url for p in req.photos.all()],
    }
    return JsonResponse(data)

# Обновление чекбокса "деньги сданы" (админ)
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
    # Только для админа? Пока сделаем для всех, но потом ограничим
    requests = Request.objects.all().order_by('-created_date')
    # Фильтры
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    price_from = request.GET.get('price_from')
    price_to = request.GET.get('price_to')
    worker_id = request.GET.get('worker')
    status = request.GET.get('status')

    if date_from:
        requests = requests.filter(created_date__gte=date_from)
    if date_to:
        # Добавляем +1 день, чтобы включить конечную дату
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
        data.append({
            'id': r.id,
            'description': r.description,
            'client_name': r.client_name,
            'client_phone': r.client_phone,
            'client_address': r.client_address,
            'status': r.status,
            'price': str(r.price) if r.price else None,
            'money_delivered': r.money_delivered,
            'worker_name': r.assigned_to.first_name if r.assigned_to else '',
            'created_date': r.created_date.isoformat(),
            'deadline_days': r.deadline_days,
        })
    return JsonResponse(data, safe=False)
def get_worker_requests(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'auth required'}, status=401)
    # Показываем только заявки, назначенные на текущего пользователя
    requests = Request.objects.filter(assigned_to=request.user).order_by('-created_date')
    data = []
    for r in requests:
        data.append({
            'id': r.id,
            'description': r.description,
            'client_name': r.client_name,
            'client_phone': r.client_phone,
            'client_email': r.client_email,
            'client_address': r.client_address,
            'status': r.status,
            'price': str(r.price) if r.price else None,
            'money_delivered': r.money_delivered,
            'worker_name': r.assigned_to.first_name if r.assigned_to else '',
            'created_date': r.created_date.isoformat(),
            'deadline_days': r.deadline_days,
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
    """Генерирует код для привязки Telegram и сохраняет его в базе tg_bot."""
    if request.method == 'POST':
        try:
            # Генерируем уникальный site_user_id (токен) и цифровой код
            import random, uuid
            site_user_id = uuid.uuid4().hex
            code = ''.join(random.choices('0123456789', k=6))
            if tg_database:
                # save_code сохраняет site_user_id -> code
                tg_database.save_code(site_user_id, code)
            return JsonResponse({'code': code, 'token': site_user_id, 'message': 'Отправьте код боту'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
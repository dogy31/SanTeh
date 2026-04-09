from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from .models import Profile, Request, Photo, Part
import os, sys
import requests
from datetime import datetime, date
import decimal
from PIL import Image
import io

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def normalize_phone(phone):
    if not phone:
        return ''
    digits = ''.join(ch for ch in phone if ch.isdigit())
    if not digits:
        return ''
    if digits.startswith('8'):
        digits = '7' + digits[1:]
    elif digits.startswith('9'):
        digits = '7' + digits
    if len(digits) > 11:
        digits = digits[:11]
    return digits
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
import decimal

def validate_and_optimize_image(image_file, max_size_mb=10, max_width=2048, max_height=2048, quality=85):
    """
    Валидирует и оптимизирует изображение
    - Проверяет формат (только JPEG, PNG, WebP)
    - Проверяет размер файла
    - Оптимизирует размер и качество
    - Возвращает оптимизированное изображение или None при ошибке
    """
    try:
        # Проверка размера файла (max_size_mb мегабайт)
        if image_file.size > max_size_mb * 1024 * 1024:
            return None, f"Файл слишком большой. Максимальный размер: {max_size_mb}MB"

        # Проверка формата файла
        allowed_formats = ['JPEG', 'PNG', 'WEBP', 'JPG', 'jpeg', 'png', 'webp', 'jpg']
        file_extension = image_file.name.split('.')[-1].lower() if '.' in image_file.name else ''
        
        # Открываем изображение для проверки
        image = Image.open(image_file)
        
        # Проверяем формат через PIL
        if image.format not in ['JPEG', 'PNG', 'WEBP']:
            return None, "Неподдерживаемый формат изображения. Разрешены: JPEG, PNG, WebP"
        
        # Проверяем, что файл действительно является изображением
        # image.verify()  # Убрано, так как может быть слишком строгим
        
        # Снова открываем изображение после verify()
        image_file.seek(0)
        image = Image.open(image_file)
        
        # Конвертируем в RGB если необходимо (для прозрачных PNG)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Создаем белый фон
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Изменяем размер если слишком большой
        if image.width > max_width or image.height > max_height:
            # Сохраняем соотношение сторон
            ratio = min(max_width / image.width, max_height / image.height)
            new_width = int(image.width * ratio)
            new_height = int(image.height * ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Оптимизируем и сохраняем в памяти
        output = io.BytesIO()
        
        # Сохраняем как JPEG для лучшей совместимости
        image.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        # Создаем новый InMemoryUploadedFile
        from django.core.files.uploadedfile import InMemoryUploadedFile
        optimized_file = InMemoryUploadedFile(
            output,
            'ImageField',
            f"{os.path.splitext(image_file.name)[0]}.jpg",
            'image/jpeg',
            output.tell(),
            None
        )
        
        return optimized_file, None
        
    except Exception as e:
        return None, f"Ошибка обработки изображения: {str(e)}"

def register(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = normalize_phone(request.POST.get('phone'))
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        role = 'worker' 
        tg_token = request.POST.get('tg_token')
        max_token = request.POST.get('max_token')
        messengers = request.POST.getlist('messengers')

        if not name or not phone or not password or not password2:
            return render(request, 'main/register.html', {'error': 'Заполните все обязательные поля'})
        if len(phone) != 11:
            return render(request, 'main/register.html', {'error': 'Введите корректный номер телефона'})
        
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

def login_view(request):
    if request.method == 'POST':
        phone = normalize_phone(request.POST.get('phone'))
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

def logout_view(request):
    logout(request)
    return redirect('login')

def forgot_password(request):
    if request.method == 'POST':
        phone = normalize_phone(request.POST.get('phone'))
        if not phone or len(phone) != 11:
            return render(request, 'main/forgot_password.html', {'error': 'Введите корректный номер телефона'})
        try:
            user = User.objects.get(username=phone)
        except User.DoesNotExist:
            return render(request, 'main/forgot_password.html', {'error': 'Пользователь с таким номером не найден'})
        
        import random
        code = str(random.randint(100000, 999999))
        request.session['reset_phone'] = phone
        request.session['reset_code'] = code
        
        message = f"Код для сброса пароля: {code}"
        send_sms(phone, message)
        
        return redirect('reset_password')
    return render(request, 'main/forgot_password.html')

def reset_password(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if not code or not password1 or not password2:
            return render(request, 'main/reset_password.html', {'error': 'Заполните все поля'})
        if password1 != password2:
            return render(request, 'main/reset_password.html', {'error': 'Пароли не совпадают'})
        
        phone = request.session.get('reset_phone')
        reset_code = request.session.get('reset_code')
        if not phone or not reset_code or code != reset_code:
            return render(request, 'main/reset_password.html', {'error': 'Неверный код'})
        
        try:
            user = User.objects.get(username=phone)
            user.set_password(password1)
            user.save()
            del request.session['reset_phone']
            del request.session['reset_code']
            return redirect('login')
        except User.DoesNotExist:
            return render(request, 'main/reset_password.html', {'error': 'Пользователь не найден'})
    return render(request, 'main/reset_password.html')

@login_required
def admin_dashboard(request):
    if request.user.profile.role != 'admin':
        return redirect('worker_dashboard')
    workers = User.objects.filter(profile__role='worker')
    return render(request, 'main/admin.html', {'workers': workers, 'max_enabled': bool(MAX_TOKEN)})

@login_required
def worker_dashboard(request):
    if request.user.profile.role != 'worker':
        return redirect('admin_dashboard')
    return render(request, 'main/worker.html', {'max_enabled': bool(MAX_TOKEN)})

@login_required
def create_request(request):
    if request.method == 'POST':
        data = request.POST
        worker_id = data.get('worker_id')
        client_address = data.get('client_address', '').strip()
        if not client_address:
            return JsonResponse({'error': 'Адрес обязателен для заполнения'}, status=400)
        try:
            worker_percent = int(data.get('worker_percent', 50))
        except (ValueError, TypeError):
            worker_percent = 50
        if worker_percent < 0 or worker_percent > 100:
            worker_percent = 50
        client_phone = normalize_phone(data.get('client_phone', ''))
        req = Request.objects.create(
            description=data['description'],
            client_name=data['client_name'],
            client_phone=client_phone,
            client_email=data.get('client_email', ''),
            client_address=client_address,
            equipment_type=data.get('equipment_type', ''),
            assigned_to_id=worker_id if worker_id else None,
            deadline_date=data.get('deadline_date'),
            worker_percent=worker_percent
        )
        # Отправка уведомления
        try:
            if worker_id:
                worker = User.objects.filter(pk=worker_id).first()
                if worker and hasattr(worker, 'profile'):
                    profile = worker.profile
                    now = datetime.now()
                    text = f"""
━━━━━━━━━━━━━
НОВАЯ ЗАЯВКА #{req.id}
от {now.strftime('%d.%m.%Y %H:%M')}
━━━━━━━━━━━━━
ОПИСАНИЕ РАБОТ:
{req.description}
━━━━━━━━━━━━━
КЛИЕНТ: {req.client_name}
ТЕЛЕФОН: {req.client_phone}
АДРЕС: {req.client_address or '—'}
━━━━━━━━━━━━━
❗❗❗ВАЖНО: перезвоните клиенту в течении 30 минут и не опаздывайте к согласованому времени❗❗❗
"""
                    send_worker_notification(profile, text)
        except Exception:
            pass
        return JsonResponse({'success': True, 'id': req.id})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def edit_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.user.profile.role != 'admin' and req.assigned_to != request.user:
        return JsonResponse({'error': 'permission denied'}, status=403)

    if request.method == 'POST':
        if 'client_name' in request.POST:
            req.client_name = request.POST.get('client_name', req.client_name)
        if 'client_phone' in request.POST:
            req.client_phone = normalize_phone(request.POST.get('client_phone', req.client_phone))
        if 'client_email' in request.POST:
            req.client_email = request.POST.get('client_email', req.client_email)
        if 'client_address' in request.POST:
            req.client_address = request.POST.get('client_address', req.client_address)
        if 'equipment_type' in request.POST:
            req.equipment_type = request.POST.get('equipment_type', req.equipment_type)
        if 'price' in request.POST:
            price = request.POST.get('price')
            req.price = price if price else None
        if 'comment' in request.POST:
            req.comment = request.POST.get('comment', req.comment)
        if 'overdue_reason' in request.POST:
            req.overdue_reason = request.POST.get('overdue_reason', req.overdue_reason)
        if 'status' in request.POST:
            req.status = request.POST.get('status', req.status)

        previous_worker_id = req.assigned_to_id
        is_closed = req.status in ['done', 'cancelled']

        if 'worker_id' in request.POST:
            worker_id = request.POST.get('worker_id')
            req.assigned_to_id = worker_id if worker_id else None

        if 'deadline_date' in request.POST:
            deadline_date = request.POST.get('deadline_date')
            req.deadline_date = deadline_date if deadline_date else None

        if 'prepayment_amount' in request.POST:
            prepayment_amount = request.POST.get('prepayment_amount')
            if prepayment_amount != '':
                try:
                    prepayment_amount = decimal.Decimal(prepayment_amount)
                    req.prepayment_amount = prepayment_amount
                    if req.status == 'new' and prepayment_amount > 0:
                        req.status = 'in-progress'
                except Exception:
                    pass
            else:
                req.prepayment_amount = 0

        if 'worker_percent' in request.POST:
            try:
                percent = int(request.POST.get('worker_percent', req.worker_percent))
                if 0 <= percent <= 100:
                    req.worker_percent = percent
            except (TypeError, ValueError):
                pass

        req.save()

        if 'worker_id' in request.POST and not is_closed:
            new_worker_id = req.assigned_to_id
            if previous_worker_id != new_worker_id:
                if previous_worker_id:
                    old_worker = User.objects.filter(pk=previous_worker_id).first()
                    if old_worker and hasattr(old_worker, 'profile'):
                        cancel_text = f"""
━━━━━━━━━━━━━
   ❌ ЗАЯВКА #{req.id} ОТМЕНЕНА
━━━━━━━━━━━━━
Заявка была переназначена другому рабочему.
"""
                        send_worker_notification(old_worker.profile, cancel_text)
                if new_worker_id:
                    new_worker = User.objects.filter(pk=new_worker_id).first()
                    if new_worker and hasattr(new_worker, 'profile'):
                        now = datetime.now()
                        assignment_text = f"""
━━━━━━━━━━━━━
ПЕРЕНАЗНАЧЕНА ЗАЯВКА #{req.id}
от {now.strftime('%d.%m.%Y %H:%M')}
━━━━━━━━━━━━━
ОПИСАНИЕ РАБОТ:
{req.description}
━━━━━━━━━━━━━
КЛИЕНТ: {req.client_name}
ТЕЛЕФОН: {req.client_phone}
АДРЕС: {req.client_address or '—'}
━━━━━━━━━━━━━
❗❗❗ВАЖНО: перезвоните клиенту в течении 30 минут и не опаздывайте к согласованому времени❗❗❗
"""
                        send_worker_notification(new_worker.profile, assignment_text)

        # Обработка договора
        contract_files = request.FILES.getlist('contract_photos')
        if contract_files:
            if len(contract_files) > 5:
                return JsonResponse({'error': 'Максимум 5 фотографий договора'}, status=400)
            req.photos.filter(photo_type='contract').delete()
            for contract_file in contract_files:
                # Валидируем и оптимизируем изображение
                optimized_image, error_msg = validate_and_optimize_image(contract_file)
                if error_msg:
                    return JsonResponse({'error': f'Ошибка с изображением договора: {error_msg}'}, status=400)
                if optimized_image:
                    Photo.objects.create(request=req, image=optimized_image, photo_type='contract')
        else:
            existing_contract_ids = request.POST.get('existing_contract_ids')
            if existing_contract_ids is not None:
                try:
                    ids_to_keep = json.loads(existing_contract_ids)
                    req.photos.filter(photo_type='contract').exclude(id__in=ids_to_keep).delete()
                except Exception:
                    pass
            elif request.POST.get('delete_contract') == 'true':
                req.photos.filter(photo_type='contract').delete()

        # Обработка деталей
        parts_data_json = request.POST.get('parts_data')
        if parts_data_json:
            parts_data = json.loads(parts_data_json)
            existing_parts = {part.id: part for part in req.parts.all()}
            kept_part_ids = []
            for i, part in enumerate(parts_data):
                existing_id = part.get('existingId')
                if existing_id and existing_id in existing_parts:
                    part_obj = existing_parts[existing_id]
                    part_obj.name = part.get('name', '')
                    part_obj.price = part.get('price') if part.get('price') else None
                    photo_field = f'part_photo_{i}'
                    if photo_field in request.FILES:
                        # Валидируем и оптимизируем изображение
                        optimized_image, error_msg = validate_and_optimize_image(request.FILES[photo_field])
                        if error_msg:
                            return JsonResponse({'error': f'Ошибка с изображением чека для "{part.get("name", "детали")}"": {error_msg}'}, status=400)
                        if optimized_image:
                            part_obj.receipt_photo = optimized_image
                    part_obj.save()
                else:
                    part_obj = Part(
                        request=req,
                        name=part.get('name', ''),
                        price=part.get('price') if part.get('price') else None
                    )
                    photo_field = f'part_photo_{i}'
                    if photo_field in request.FILES:
                        # Валидируем и оптимизируем изображение
                        optimized_image, error_msg = validate_and_optimize_image(request.FILES[photo_field])
                        if error_msg:
                            return JsonResponse({'error': f'Ошибка с изображением чека для "{part.get("name", "детали")}"": {error_msg}'}, status=400)
                        if optimized_image:
                            part_obj.receipt_photo = optimized_image
                    part_obj.save()
                kept_part_ids.append(part_obj.id)
            req.parts.exclude(id__in=kept_part_ids).delete()

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
        'photos': [{'id': p.id, 'image': p.image.url, 'photo_type': p.photo_type} for p in req.photos.all()],
        'status': req.status,
        'parts': parts_data,
        'overdue_reason': req.overdue_reason,
        'is_overdue': date.today() > req.deadline_date if req.deadline_date else False,
        'worker_id': req.assigned_to.id if req.assigned_to else '',
        'prepayment_amount': str(req.prepayment_amount) if req.prepayment_amount else None,
        'worker_percent': req.worker_percent,
        'deadline_date': req.deadline_date.isoformat() if req.deadline_date else '',  # добавлено
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


def send_worker_notification(profile, text):
    try:
        site_user_id = str(profile.user.id) if profile.user and profile.user.id else None
        if site_user_id:
            requests.post('http://127.0.0.1:5000/create_ticket', json={'user_id': site_user_id, 'text': text}, timeout=3)
    except Exception:
        print('Не удалось отправить уведомление')

@login_required
def close_request(request, pk):
    if request.method == 'POST':
        req = get_object_or_404(Request, pk=pk)
        if not req.price:
            return JsonResponse({'error': 'Цена не указана'}, status=400)
        if not req.photos.filter(photo_type='contract').exists():
            return JsonResponse({'error': 'Не прикреплен договор'}, status=400)
        parts = req.parts.all()
        for part in parts:
            if not part.receipt_photo:
                return JsonResponse({'error': f'Отсутствует чек для детали "{part.name}"'}, status=400)
        req.status = 'done'
        req.save()
        if req.client_phone:
            message = f"Ваша заявка выполнена. Сумма {req.price} руб. Гарантия 14 дней. При несоответсвии данных свяжитесь {+79059883225}. При искажении данных гарантия онулируется"
            send_sms(req.client_phone, message)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def view_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    cost_price = sum(float(part.price) for part in req.parts.all() if part.price)
    net_profit = None
    worker_salary = None
    if req.price:
        net_profit = float(req.price) - cost_price
        worker_salary = net_profit * (req.worker_percent / 100) if net_profit else 0
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
        'prepayment_amount': str(req.prepayment_amount) if req.prepayment_amount else None,
        'created_date': req.created_date.strftime('%d.%m.%Y %H:%M'),
        'comment': req.comment,
        'worker': req.assigned_to.first_name if req.assigned_to else '',
        'photos': [{'image': p.image.url, 'photo_type': p.photo_type} for p in req.photos.all()],
        'parts': [{'id': p.id, 'name': p.name, 'price': str(p.price) if p.price else None, 'receipt_photo_url': p.receipt_photo.url if p.receipt_photo else None} for p in req.parts.all()],
        'overdue_reason': req.overdue_reason,
        'worker_percent': req.worker_percent,
    }
    return JsonResponse(data)

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
    search = request.GET.get('search')
    status_list = request.GET.getlist('status')

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
    if search:
        # Поиск по id, описанию задачи, client_address, client_name
        requests = requests.filter(
            Q(id__icontains=search) | Q(description__icontains=search) | Q(client_address__icontains=search) | Q(client_name__icontains=search)
        )
    status_list = [s for s in status_list if s]
    if status_list:
        requests = requests.filter(status__in=status_list)

    data = []
    for r in requests:
        cost_price = sum(float(part.price) for part in r.parts.all() if part.price)
        net_profit = float(r.price) - cost_price if r.price else 0
        worker_salary = net_profit * (r.worker_percent / 100) if net_profit else 0
        admin_profit = net_profit - worker_salary if net_profit else 0
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
            'admin_profit': round(admin_profit, 2) if admin_profit is not None else None,
            'worker_percent': r.worker_percent,
            'money_delivered': r.money_delivered,
            'prepayment_amount': str(r.prepayment_amount) if r.prepayment_amount else None,
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
    search = request.GET.get('search')
    status_list = request.GET.getlist('status')

    if date_from:
        requests = requests.filter(created_date__gte=date_from)
    if date_to:
        requests = requests.filter(created_date__lte=date_to + ' 23:59:59')
    if price_from:
        requests = requests.filter(price__gte=price_from)
    if price_to:
        requests = requests.filter(price__lte=price_to)
    if search:
        # Поиск по id, описанию задачи, client_address, client_name
        requests = requests.filter(
            Q(id__icontains=search) | Q(description__icontains=search) | Q(client_address__icontains=search) | Q(client_name__icontains=search)
        )
    status_list = [s for s in status_list if s]
    if status_list:
        requests = requests.filter(status__in=status_list)

    data = []
    for r in requests:
        # Расчёт себестоимости, чистой прибыли и зарплаты рабочего
        cost_price = sum(float(part.price) for part in r.parts.all() if part.price)
        net_profit = float(r.price) - cost_price if r.price else 0
        worker_salary = net_profit * (r.worker_percent / 100) if net_profit else 0

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
            'prepayment_amount': str(r.prepayment_amount) if r.prepayment_amount else None,
            'worker_name': r.assigned_to.first_name if r.assigned_to else '',
            'created_date': r.created_date.isoformat(),
            'photos': [{'image': p.image.url, 'photo_type': p.photo_type} for p in r.photos.all()],
            # Новые поля
            'cost_price': round(cost_price, 2),
            'net_profit': round(net_profit, 2) if net_profit else None,
            'worker_salary': round(worker_salary, 2) if worker_salary else None,
            'worker_percent': r.worker_percent,
        })
    return JsonResponse(data, safe=False)

@login_required
def get_workers(request):
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)
    workers = User.objects.filter(profile__role='worker').values('first_name', 'username', 'email', 'profile__phone')
    data = [{'first_name': w['first_name'], 'phone': w['profile__phone'], 'email': w['email']} for w in workers]
    return JsonResponse(data, safe=False)

def reopen_request(request, pk):
    if request.method == 'POST' and request.user.is_authenticated and request.user.profile.role == 'admin':
        req = get_object_or_404(Request, pk=pk)
        if req.status == 'done':
            req.status = 'in-progress'
            req.save()
            return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def cancel_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.user.profile.role != 'admin' and req.assigned_to != request.user:
        return JsonResponse({'error': 'permission denied'}, status=403)
    if req.status == 'done':
        return JsonResponse({'error': 'Cannot cancel completed request'}, status=400)
    if not req.price:
        return JsonResponse({'error': 'Цена не указана'}, status=400)
    req.status = 'cancelled'
    req.save()
    if req.client_phone:
        message = f"Ваша заявка отменена. Диагностика {req.price} руб. Гарантия на отмену не распространяется. При несоответсвии данных свяжитесь {+79059883225}"
        send_sms(req.client_phone, message)
    return JsonResponse({'success': True})

@csrf_exempt
def generate_tg_code(request):
    if request.method == 'POST':
        try:
            import random, uuid
            user_id = None
            if request.content_type and request.content_type.startswith('application/json'):
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
            import random, uuid
            user_id = None
            if request.content_type and request.content_type.startswith('application/json'):
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
        saved = False
        if tg_database and tg_token:
            tg_link = tg_database.get_telegram(tg_token)
            if tg_link and tg_link[0]:
                profile.tg_code = str(tg_link[0])
                saved = True
        if tg_database and max_token:
            max_link = tg_database.get_max(max_token)
            if max_link and max_link[0]:
                profile.max_code = str(max_link[0])
                saved = True
        if saved:
            profile.save()
            return JsonResponse({'success': True})
        return JsonResponse({'error': 'Код не найден или не подтверждён в боте'}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def update_worker_percent(request, pk):
    if request.method == 'POST' and request.user.is_authenticated and request.user.profile.role == 'admin':
        req = get_object_or_404(Request, pk=pk)
        try:
            data = json.loads(request.body)
            percent = int(data.get('percent', 50))
            if 0 <= percent <= 100:
                req.worker_percent = percent
                req.save()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'error': 'Процент должен быть от 0 до 100'}, status=400)
        except Exception:
            return JsonResponse({'error': 'Неверные данные'}, status=400)
    return JsonResponse({'error': 'Нет прав'}, status=403)
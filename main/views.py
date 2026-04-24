import logging
import os
import sys
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.forms import ValidationError as FormValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from .forms import RequestForm
from .models import Profile, Request, Photo, Part, EquipmentTypeOption, AddressBaseOption, Document, TransportExpense
from .utils.image_processor import (
    FileTooLargeError,
    ImageConversionError,
    NotAnImageError,
    process_uploaded_image,
)
import requests
from datetime import datetime, date
import decimal

logger = logging.getLogger(__name__)

DEFAULT_EQUIPMENT_TYPES = [
    'См - Cтиральные машины',
    'ПМ - Посудомоечные машины',
    'Хд - Холодильники',
    'Вд - Водонагреватели',
    'Дш - Духовые шкафы',
    'ВП - Варочные панель',
    'Тв - Телевизоры',
    'Км - Кофемашины',
    'Пром - Промышленная техника',
]

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


def compose_full_address(base_address, house_number='', entrance='', floor='', apartment=''):
    # Нормализуем базу, чтобы не дублировать "д. / под. / эт. / кв." при повторном сохранении.
    base = extract_base_address(base_address)
    parts = [base] if base else []
    if house_number:
        parts.append(f"д. {house_number.strip()}")
    if entrance:
        parts.append(f"под. {entrance.strip()}")
    if floor:
        parts.append(f"эт. {floor.strip()}")
    if apartment:
        parts.append(f"кв. {apartment.strip()}")
    return ', '.join(parts)


def extract_base_address(full_address):
    raw = (full_address or '').strip()
    if not raw:
        return ''
    markers = [', д.', ', под.', ', эт.', ', кв.']
    cut = len(raw)
    for marker in markers:
        idx = raw.find(marker)
        if idx != -1 and idx < cut:
            cut = idx
    return raw[:cut].strip()


def save_request_options(equipment_type='', base_address=''):
    eq = (equipment_type or '').strip()
    if eq:
        EquipmentTypeOption.objects.get_or_create(value=eq)
    base = (base_address or '').strip()
    if base:
        AddressBaseOption.objects.get_or_create(value=base)


def ensure_default_equipment_options():
    for item in DEFAULT_EQUIPMENT_TYPES:
        EquipmentTypeOption.objects.get_or_create(value=item)


def get_equipment_options():
    ensure_default_equipment_options()
    return list(EquipmentTypeOption.objects.values_list('value', flat=True))


def get_cancel_keep_amount_for_equipment(equipment_type):
    normalized = (equipment_type or '').strip()
    if not normalized:
        return float(decimal.Decimal('750'))
    option = EquipmentTypeOption.objects.filter(value__iexact=normalized).first()
    if option and option.cancel_keep_amount is not None:
        return float(option.cancel_keep_amount)
    return float(decimal.Decimal('750'))


def calc_cancelled_split(price_value, equipment_type):
    price = float(price_value) if price_value else 0
    keep_amount = get_cancel_keep_amount_for_equipment(equipment_type)
    worker_salary = min(price, keep_amount)
    admin_profit = max(price - worker_salary, 0)
    return {
        'cost_price': 0,
        'net_profit': price,
        'worker_salary': worker_salary,
        'admin_profit': admin_profit,
    }
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
from concurrent.futures import ThreadPoolExecutor, as_completed

def register(request):
    def register_context(**extra):
        ctx = {
            'max_enabled': bool(MAX_TOKEN),
            'worker_equipment_choices': sorted(get_equipment_options(), key=lambda x: x.lower()),
        }
        ctx.update(extra)
        return ctx

    if request.method == 'POST':
        name = request.POST.get('name')
        phone = normalize_phone(request.POST.get('phone'))
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        role = 'worker' 
        tg_token = request.POST.get('tg_token')
        max_token = request.POST.get('max_token')
        messengers = request.POST.getlist('messengers')
        worker_equipment_types = request.POST.getlist('worker_equipment_types')

        if not name or not phone or not password or not password2:
            return render(request, 'main/register.html', register_context(error='Заполните все обязательные поля'))
        if len(phone) != 11:
            return render(request, 'main/register.html', register_context(error='Введите корректный номер телефона'))
        
        if password != password2:
            return render(request, 'main/register.html', register_context(error='Пароли не совпадают'))

        if 'telegram' in messengers and not tg_token:
            return render(request, 'main/register.html', register_context(error='Если вы выбрали Telegram, то получите код'))
        if 'max' in messengers and not max_token:
            return render(request, 'main/register.html', register_context(error='Если вы выбрали MAX, то получите код'))

        tg_id = None
        max_id = None
        if tg_database:
            if 'telegram' in messengers:
                tg_link = tg_database.get_telegram(tg_token)
                if not tg_link or not tg_link[0]:
                    return render(request, 'main/register.html', register_context(error='Telegram не привязан: отправьте код боту'))
                tg_id = str(tg_link[0])
            if 'max' in messengers:
                max_link = tg_database.get_max(max_token)
                if not max_link or not max_link[0]:
                    return render(request, 'main/register.html', register_context(error='MAX не привязан: отправьте код боту'))
                max_id = str(max_link[0])

        if User.objects.filter(username=phone).exists():
            return render(request, 'main/register.html', register_context(error='Пользователь с таким номером телефона уже существует'))
        user = User.objects.create_user(username=phone, email=phone, password=password, first_name=name)
        profile = Profile(user=user, phone=phone, role=role, tg_code=tg_id, max_code=max_id)
        profile.set_worker_equipment_values(worker_equipment_types)
        profile.save()
        return redirect('login')
    return render(request, 'main/register.html', register_context())

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
    ensure_default_equipment_options()
    workers = User.objects.filter(profile__role='worker')
    return render(request, 'main/admin.html', {'workers': workers, 'max_enabled': bool(MAX_TOKEN)})

@login_required
def worker_dashboard(request):
    if request.user.profile.role != 'worker':
        return redirect('admin_dashboard')
    return render(
        request,
        'main/worker.html',
        {
            'max_enabled': bool(MAX_TOKEN),
            'worker_equipment_choices': sorted(get_equipment_options(), key=lambda x: x.lower()),
            'selected_worker_equipment': request.user.profile.get_worker_equipment_values(),
        }
    )

def _json_image_error(exc: Exception):
    if isinstance(exc, FileTooLargeError):
        return JsonResponse({'error': str(exc)}, status=400)
    if isinstance(exc, NotAnImageError):
        return JsonResponse({'error': str(exc)}, status=400)
    if isinstance(exc, ImageConversionError):
        logger.exception('Ошибка конвертации изображения')
        return JsonResponse({'error': str(exc)}, status=400)
    return None


def _process_images_in_parallel(files, upload_subdir: str):
    """
    Параллельная обработка пачки изображений для ускорения больших загрузок.
    Возвращает список относительных путей в исходном порядке.
    """
    file_list = list(files or [])
    if not file_list:
        return []
    if len(file_list) == 1:
        return [process_uploaded_image(file_list[0], upload_subdir=upload_subdir)]

    workers = min(4, len(file_list))
    results = [None] * len(file_list)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {
            pool.submit(process_uploaded_image, file_obj, upload_subdir=upload_subdir): idx
            for idx, file_obj in enumerate(file_list)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
    return results


@login_required
def create_request(request):
    if request.method == 'POST':
        form = RequestForm(request.POST)
        if not form.is_valid():
            msg = '; '.join(str(e) for errs in form.errors.values() for e in errs)
            return JsonResponse({'error': msg or 'Неверные данные'}, status=400)
        cd = form.cleaned_data
        worker_id = cd.get('worker_id')
        if worker_id is not None:
            worker_id = int(worker_id)
        worker_percent = cd['worker_percent']
        client_phone = normalize_phone(cd['client_phone'])
        visit_time = cd.get('visit_time')
        base_address = (cd.get('client_address') or '').strip()
        house_number = (cd.get('house_number') or '').strip()
        entrance = (cd.get('entrance') or '').strip()
        floor = (cd.get('floor') or '').strip()
        apartment = (cd.get('apartment') or '').strip()
        full_address = compose_full_address(base_address, house_number, entrance, floor, apartment)
        equipment_type = (cd.get('equipment_type') or '').strip()
        contract_files = request.FILES.getlist('contract_photos')
        if contract_files:
            try:
                RequestForm.validate_contract_photo_files(contract_files)
            except FormValidationError as e:
                return JsonResponse({'error': '; '.join(e.messages)}, status=400)

        try:
            with transaction.atomic():
                req = Request.objects.create(
                    description=cd['description'],
                    client_name=(cd.get('client_name') or '').strip(),
                    client_phone=client_phone,
                    client_email=cd.get('client_email') or '',
                    client_address=full_address,
                    house_number=house_number,
                    entrance=entrance,
                    floor=floor,
                    apartment=apartment,
                    equipment_type=equipment_type,
                    assigned_to_id=worker_id,
                    deadline_date=cd['deadline_date'],
                    visit_time=visit_time,
                    worker_percent=worker_percent,
                )
                save_request_options(equipment_type=equipment_type, base_address=base_address)
                if contract_files:
                    contract_photo_rows = []
                    rel_paths = _process_images_in_parallel(contract_files, upload_subdir='requests')
                    for rel in rel_paths:
                        contract_photo_rows.append(Photo(request=req, image=rel, photo_type='contract'))
                    if contract_photo_rows:
                        Photo.objects.bulk_create(contract_photo_rows)
        except (FileTooLargeError, NotAnImageError, ImageConversionError) as e:
            resp = _json_image_error(e)
            if resp:
                return resp
            raise
        except Exception:
            logger.exception('Ошибка при создании заявки')
            return JsonResponse({'error': 'Не удалось сохранить заявку'}, status=400)

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
            req.client_name = (request.POST.get('client_name', req.client_name) or '').strip()
        if 'client_phone' in request.POST:
            req.client_phone = normalize_phone(request.POST.get('client_phone', req.client_phone))
        if 'client_email' in request.POST:
            req.client_email = request.POST.get('client_email', req.client_email)
        has_base_address = 'client_address' in request.POST
        if has_base_address:
            req.client_address = (request.POST.get('client_address', req.client_address) or '').strip()
        if 'house_number' in request.POST:
            req.house_number = (request.POST.get('house_number', req.house_number) or '').strip()
        if 'entrance' in request.POST:
            req.entrance = (request.POST.get('entrance', req.entrance) or '').strip()
        if 'floor' in request.POST:
            req.floor = (request.POST.get('floor', req.floor) or '').strip()
        if 'apartment' in request.POST:
            req.apartment = (request.POST.get('apartment', req.apartment) or '').strip()
        if 'equipment_type' in request.POST:
            req.equipment_type = (request.POST.get('equipment_type', req.equipment_type) or '').strip()
        if has_base_address or 'house_number' in request.POST or 'entrance' in request.POST or 'floor' in request.POST or 'apartment' in request.POST:
            req.client_address = compose_full_address(
                request.POST.get('client_address', req.client_address),
                req.house_number,
                req.entrance,
                req.floor,
                req.apartment,
            )
            save_request_options(
                equipment_type=req.equipment_type,
                base_address=request.POST.get('client_address', ''),
            )
        elif 'equipment_type' in request.POST:
            save_request_options(equipment_type=req.equipment_type, base_address='')
        if 'price' in request.POST:
            price = request.POST.get('price')
            req.price = price if price else None
        if 'comment' in request.POST:
            req.comment = request.POST.get('comment', req.comment)
        if 'performed_work' in request.POST:
            req.performed_work = request.POST.get('performed_work', req.performed_work)
        if 'overdue_reason' in request.POST:
            req.overdue_reason = request.POST.get('overdue_reason', req.overdue_reason)
        if 'status' in request.POST:
            req.status = request.POST.get('status', req.status)

        previous_worker_id = req.assigned_to_id
        if 'worker_id' in request.POST:
            worker_id = request.POST.get('worker_id')
            req.assigned_to_id = worker_id if worker_id else None

        if 'deadline_date' in request.POST:
            deadline_date = request.POST.get('deadline_date')
            req.deadline_date = deadline_date if deadline_date else None
        if 'visit_time' in request.POST:
            visit_time = (request.POST.get('visit_time') or '').strip()
            req.visit_time = visit_time if visit_time else None

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

        req.save()

        if 'worker_id' in request.POST:
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
            try:
                RequestForm.validate_contract_photo_files(contract_files)
            except FormValidationError as e:
                return JsonResponse({'error': '; '.join(e.messages)}, status=400)
            try:
                with transaction.atomic():
                    req.photos.filter(photo_type='contract').delete()
                    contract_photo_rows = []
                    rel_paths = _process_images_in_parallel(contract_files, upload_subdir='requests')
                    for rel in rel_paths:
                        contract_photo_rows.append(Photo(request=req, image=rel, photo_type='contract'))
                    if contract_photo_rows:
                        Photo.objects.bulk_create(contract_photo_rows)
            except (FileTooLargeError, NotAnImageError, ImageConversionError) as e:
                resp = _json_image_error(e)
                if resp:
                    return resp
                raise
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
                        try:
                            rel = process_uploaded_image(
                                request.FILES[photo_field], upload_subdir='parts'
                            )
                            part_obj.receipt_photo = rel
                        except (FileTooLargeError, NotAnImageError, ImageConversionError) as e:
                            resp = _json_image_error(e)
                            if resp:
                                return resp
                            raise
                    part_obj.save()
                else:
                    part_obj = Part(
                        request=req,
                        name=part.get('name', ''),
                        price=part.get('price') if part.get('price') else None
                    )
                    photo_field = f'part_photo_{i}'
                    if photo_field in request.FILES:
                        try:
                            rel = process_uploaded_image(
                                request.FILES[photo_field], upload_subdir='parts'
                            )
                            part_obj.receipt_photo = rel
                        except (FileTooLargeError, NotAnImageError, ImageConversionError) as e:
                            resp = _json_image_error(e)
                            if resp:
                                return resp
                            raise
                    part_obj.save()
                kept_part_ids.append(part_obj.id)
            req.parts.exclude(id__in=kept_part_ids).delete()

        transport_data_json = request.POST.get('transport_data')
        if transport_data_json:
            transport_data = json.loads(transport_data_json)
            existing_items = {item.id: item for item in req.transport_expenses.all()}
            kept_transport_ids = []
            for i, item in enumerate(transport_data):
                existing_id = item.get('existingId')
                note = (item.get('note') or '').strip()
                if existing_id and existing_id in existing_items:
                    transport_obj = existing_items[existing_id]
                    transport_obj.note = note
                    photo_field = f'transport_photo_{i}'
                    if photo_field in request.FILES:
                        try:
                            rel = process_uploaded_image(
                                request.FILES[photo_field], upload_subdir='transport'
                            )
                            transport_obj.receipt_photo = rel
                        except (FileTooLargeError, NotAnImageError, ImageConversionError) as e:
                            resp = _json_image_error(e)
                            if resp:
                                return resp
                            raise
                    transport_obj.save()
                else:
                    transport_obj = TransportExpense(request=req, note=note)
                    photo_field = f'transport_photo_{i}'
                    if photo_field in request.FILES:
                        try:
                            rel = process_uploaded_image(
                                request.FILES[photo_field], upload_subdir='transport'
                            )
                            transport_obj.receipt_photo = rel
                        except (FileTooLargeError, NotAnImageError, ImageConversionError) as e:
                            resp = _json_image_error(e)
                            if resp:
                                return resp
                            raise
                    transport_obj.save()
                kept_transport_ids.append(transport_obj.id)
            req.transport_expenses.exclude(id__in=kept_transport_ids).delete()

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
    transport_data = []
    for item in req.transport_expenses.all():
        transport_data.append({
            'id': item.id,
            'note': item.note,
            'receipt_photo_url': item.receipt_photo.url if item.receipt_photo else None,
        })
    data = {
        'id': req.id,
        'description': req.description,
        'client_name': req.client_name,
        'client_phone': req.client_phone,
        'client_email': req.client_email,
        'client_address': req.client_address,
        'base_address': extract_base_address(req.client_address),
        'house_number': req.house_number,
        'entrance': req.entrance,
        'floor': req.floor,
        'apartment': req.apartment,
        'equipment_type': req.equipment_type,
        'price': str(req.price) if req.price else None,
        'comment': req.comment,
        'performed_work': req.performed_work,
        'photos': [{'id': p.id, 'image': p.image.url, 'photo_type': p.photo_type} for p in req.photos.all()],
        'status': req.status,
        'parts': parts_data,
        'transport': transport_data,
        'overdue_reason': req.overdue_reason,
        'is_overdue': date.today() > req.deadline_date if req.deadline_date else False,
        'worker_id': req.assigned_to.id if req.assigned_to else '',
        'prepayment_amount': str(req.prepayment_amount) if req.prepayment_amount else None,
        'worker_percent': req.worker_percent,
        'deadline_date': req.deadline_date.isoformat() if req.deadline_date else '',  # добавлено
        'visit_time': req.visit_time.isoformat(timespec='minutes') if req.visit_time else '',
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
        sent = False
        if profile.tg_code and BOT_TOKEN:
            url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
            requests.post(url, json={'chat_id': profile.tg_code, 'text': text}, timeout=3)
            sent = True
        if profile.max_code and MAX_TOKEN:
            url = f'https://api.max.org/bot{MAX_TOKEN}/sendMessage'
            requests.post(url, json={'chat_id': profile.max_code, 'text': text}, timeout=3)
            sent = True
        if not sent:
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
    if req.status == 'cancelled':
        cancelled = calc_cancelled_split(req.price, req.equipment_type)
        cost_price = cancelled['cost_price']
        net_profit = cancelled['net_profit']
        worker_salary = cancelled['worker_salary']
        admin_profit = cancelled['admin_profit']
    else:
        cost_price = sum(float(part.price) for part in req.parts.all() if part.price)
        net_profit = None
        worker_salary = None
        admin_profit = None
        if req.price:
            net_profit = float(req.price) - cost_price
            worker_salary = net_profit * (req.worker_percent / 100) if net_profit else 0
            admin_profit = net_profit - worker_salary if net_profit else 0
    data = {
        'id': req.id,
        'description': req.description,
        'client_name': req.client_name,
        'client_phone': req.client_phone,
        'client_email': req.client_email,
        'client_address': req.client_address,
        'base_address': extract_base_address(req.client_address),
        'equipment_type': req.equipment_type,
        'status': req.status,
        'visit_time': req.visit_time.isoformat(timespec='minutes') if req.visit_time else '',
        'price': str(req.price) if req.price else None,
        'cost_price': round(cost_price, 2),
        'net_profit': round(net_profit, 2) if net_profit is not None else None,
        'worker_salary': round(worker_salary, 2) if worker_salary is not None else None,
        'admin_profit': round(admin_profit, 2) if admin_profit is not None else None,
        'money_delivered': req.money_delivered,
        'prepayment_amount': str(req.prepayment_amount) if req.prepayment_amount else None,
        'created_date': req.created_date.strftime('%d.%m.%Y %H:%M'),
        'comment': req.comment,
        'performed_work': req.performed_work,
        'worker': req.assigned_to.first_name if req.assigned_to else '',
        'photos': [{'image': p.image.url, 'photo_type': p.photo_type} for p in req.photos.all()],
        'parts': [{'id': p.id, 'name': p.name, 'price': str(p.price) if p.price else None, 'receipt_photo_url': p.receipt_photo.url if p.receipt_photo else None} for p in req.parts.all()],
        'transport': [{'id': t.id, 'note': t.note, 'receipt_photo_url': t.receipt_photo.url if t.receipt_photo else None} for t in req.transport_expenses.all()],
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
        # Поиск по номеру заявки, имени, адресу, задаче и названию деталей
        requests = requests.filter(
            Q(id__icontains=search)
            | Q(client_address__icontains=search)
            | Q(client_name__icontains=search)
            | Q(description__icontains=search)
            | Q(parts__name__icontains=search)
        ).distinct()
    status_list = [s for s in status_list if s]
    if status_list:
        requests = requests.filter(status__in=status_list)

    data = []
    for r in requests:
        if r.status == 'cancelled':
            cancelled = calc_cancelled_split(r.price, r.equipment_type)
            cost_price = cancelled['cost_price']
            net_profit = cancelled['net_profit']
            worker_salary = cancelled['worker_salary']
            admin_profit = cancelled['admin_profit']
        else:
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
            'base_address': extract_base_address(r.client_address),
            'house_number': r.house_number,
            'entrance': r.entrance,
            'floor': r.floor,
            'apartment': r.apartment,
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
            'visit_time': r.visit_time.isoformat(timespec='minutes') if r.visit_time else '',
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
        # Поиск по номеру заявки, имени, адресу, задаче и названию деталей
        requests = requests.filter(
            Q(id__icontains=search)
            | Q(client_address__icontains=search)
            | Q(client_name__icontains=search)
            | Q(description__icontains=search)
            | Q(parts__name__icontains=search)
        ).distinct()
    status_list = [s for s in status_list if s]
    if status_list:
        requests = requests.filter(status__in=status_list)

    data = []
    for r in requests:
        # Расчёт себестоимости, чистой прибыли и зарплаты рабочего
        if r.status == 'cancelled':
            cancelled = calc_cancelled_split(r.price, r.equipment_type)
            cost_price = cancelled['cost_price']
            net_profit = cancelled['net_profit']
            worker_salary = cancelled['worker_salary']
        else:
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
            'base_address': extract_base_address(r.client_address),
            'house_number': r.house_number,
            'entrance': r.entrance,
            'floor': r.floor,
            'apartment': r.apartment,
            'equipment_type': r.equipment_type,
            'status': r.status,
            'price': str(r.price) if r.price else None,
            'money_delivered': r.money_delivered,
            'prepayment_amount': str(r.prepayment_amount) if r.prepayment_amount else None,
            'worker_name': r.assigned_to.first_name if r.assigned_to else '',
            'created_date': r.created_date.isoformat(),
            'deadline_date': r.deadline_date.isoformat() if r.deadline_date else None,
            'visit_time': r.visit_time.isoformat(timespec='minutes') if r.visit_time else '',
            'photos': [{'image': p.image.url, 'photo_type': p.photo_type} for p in r.photos.all()],
            'transport': [{'id': t.id, 'note': t.note, 'receipt_photo_url': t.receipt_photo.url if t.receipt_photo else None} for t in r.transport_expenses.all()],
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
    workers = User.objects.filter(profile__role='worker').select_related('profile')
    data = []
    for worker in workers:
        profile = worker.profile
        data.append({
            'id': worker.id,
            'first_name': worker.first_name,
            'phone': profile.phone,
            'email': worker.email,
            'equipment_types': profile.get_worker_equipment_labels(),
        })
    return JsonResponse(data, safe=False)


@login_required
def update_worker_equipment_types(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.profile.role != 'worker':
        return JsonResponse({'error': 'permission denied'}, status=403)
    equipment_types = request.POST.getlist('worker_equipment_types')
    profile = request.user.profile
    profile.set_worker_equipment_values(equipment_types)
    profile.save(update_fields=['worker_equipment_types'])
    return JsonResponse({'success': True, 'equipment_types': profile.get_worker_equipment_labels()})


@login_required
def get_request_options(request):
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)
    equipment_types = set(get_equipment_options())
    equipment_types.update(Request.objects.exclude(equipment_type='').values_list('equipment_type', flat=True).distinct())
    address_rows = list(AddressBaseOption.objects.all().order_by('value'))
    address_bases = set(row.value for row in address_rows if row.value)
    address_bases.update([
        extract_base_address(item) for item in Request.objects.exclude(client_address='').values_list('client_address', flat=True).distinct()
    ])
    address_items = [{
        'value': row.value,
        'house_number': row.house_number or '',
        'entrance': row.entrance or '',
        'floor': row.floor or '',
        'apartment': row.apartment or '',
    } for row in address_rows if row.value]
    return JsonResponse({
        'equipment_types': sorted([item for item in equipment_types if item], key=lambda x: x.lower()),
        'address_bases': sorted([item for item in address_bases if item], key=lambda x: x.lower()),
        'address_items': address_items,
    })


@login_required
def add_request_option(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)
    option_type = (request.POST.get('type') or '').strip()
    value = (request.POST.get('value') or '').strip()
    if not value:
        return JsonResponse({'error': 'Пустое значение'}, status=400)
    if option_type == 'equipment':
        EquipmentTypeOption.objects.get_or_create(value=value)
    elif option_type == 'address':
        defaults = {
            'house_number': (request.POST.get('house_number') or '').strip(),
            'entrance': (request.POST.get('entrance') or '').strip(),
            'floor': (request.POST.get('floor') or '').strip(),
            'apartment': (request.POST.get('apartment') or '').strip(),
        }
        AddressBaseOption.objects.get_or_create(value=value, defaults=defaults)
    else:
        return JsonResponse({'error': 'Неверный тип справочника'}, status=400)
    return JsonResponse({'success': True})


@login_required
def delete_request_option(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)
    option_type = (request.POST.get('type') or '').strip()
    value = (request.POST.get('value') or '').strip()
    if not value:
        return JsonResponse({'error': 'Пустое значение'}, status=400)
    if option_type == 'equipment':
        EquipmentTypeOption.objects.filter(value=value).delete()
    elif option_type == 'address':
        AddressBaseOption.objects.filter(value=value).delete()
    else:
        return JsonResponse({'error': 'Неверный тип справочника'}, status=400)
    return JsonResponse({'success': True})


@login_required
def get_cancel_amount_settings(request):
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)
    ensure_default_equipment_options()
    for used in Request.objects.exclude(equipment_type='').values_list('equipment_type', flat=True).distinct():
        normalized = (used or '').strip()
        if normalized:
            EquipmentTypeOption.objects.get_or_create(value=normalized)
    rows = EquipmentTypeOption.objects.all().order_by('value')
    data = [{
        'equipment_type': row.value,
        'cancel_keep_amount': str(row.cancel_keep_amount if row.cancel_keep_amount is not None else decimal.Decimal('750')),
    } for row in rows]
    return JsonResponse({'items': data})


@login_required
def update_cancel_amount_settings(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)
    raw_items = request.POST.get('items_json') or '[]'
    try:
        items = json.loads(raw_items)
    except Exception:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    if not isinstance(items, list):
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    with transaction.atomic():
        for row in items:
            if not isinstance(row, dict):
                continue
            equipment_type = (row.get('equipment_type') or '').strip()
            if not equipment_type:
                continue
            try:
                amount = decimal.Decimal(str(row.get('cancel_keep_amount') or '0'))
            except Exception:
                return JsonResponse({'error': f'Некорректная сумма для "{equipment_type}"'}, status=400)
            if amount < 0:
                return JsonResponse({'error': f'Сумма не может быть отрицательной для "{equipment_type}"'}, status=400)
            option, _ = EquipmentTypeOption.objects.get_or_create(value=equipment_type)
            option.cancel_keep_amount = amount
            option.save(update_fields=['cancel_keep_amount'])
    return JsonResponse({'success': True})


@login_required
def accept_request(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    req = get_object_or_404(Request, pk=pk)
    is_admin = request.user.profile.role == 'admin'
    is_assigned_worker = req.assigned_to_id == request.user.id
    if not is_admin and not is_assigned_worker:
        return JsonResponse({'error': 'permission denied'}, status=403)
    if req.status in ('done', 'cancelled'):
        return JsonResponse({'error': 'Нельзя принять закрытую заявку'}, status=400)
    req.status = 'accepted'
    req.save(update_fields=['status'])
    return JsonResponse({'success': True, 'status': req.status})


@login_required
def get_documents(request):
    if request.user.profile.role not in ('admin', 'worker'):
        return JsonResponse({'error': 'permission denied'}, status=403)
    data = [{
        'id': d.id,
        'title': d.title,
        'file_url': d.file.url if d.file else '',
        'filename': os.path.basename(d.file.name) if d.file else '',
        'created_at': d.created_at.isoformat(),
    } for d in Document.objects.all()]
    return JsonResponse(data, safe=False)


@login_required
def upload_document(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)
    title = (request.POST.get('title') or '').strip()
    doc_file = request.FILES.get('file')
    if not title:
        return JsonResponse({'error': 'Укажите название документа'}, status=400)
    if not doc_file:
        return JsonResponse({'error': 'Выберите файл документа'}, status=400)
    doc = Document.objects.create(title=title, file=doc_file, uploaded_by=request.user)
    return JsonResponse({
        'success': True,
        'document': {
            'id': doc.id,
            'title': doc.title,
            'file_url': doc.file.url if doc.file else '',
            'filename': os.path.basename(doc.file.name) if doc.file else '',
            'created_at': doc.created_at.isoformat(),
        }
    })


@login_required
def delete_document(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)
    doc = get_object_or_404(Document, pk=pk)
    try:
        if doc.file:
            doc.file.delete(save=False)
    except Exception:
        logger.exception("Не удалось удалить файл документа %s", doc.id)
    doc.delete()
    return JsonResponse({'success': True})


def _delete_request_files(req):
    # Физически удаляем изображения из хранилища перед удалением заявки из БД.
    for photo in req.photos.all():
        try:
            if photo.image:
                photo.image.delete(save=False)
        except Exception:
            logger.exception("Не удалось удалить фото заявки %s", req.id)
    for part in req.parts.all():
        try:
            if part.receipt_photo:
                part.receipt_photo.delete(save=False)
        except Exception:
            logger.exception("Не удалось удалить чек детали %s для заявки %s", part.id, req.id)
    for item in req.transport_expenses.all():
        try:
            if item.receipt_photo:
                item.receipt_photo.delete(save=False)
        except Exception:
            logger.exception("Не удалось удалить транспортный файл %s для заявки %s", item.id, req.id)


@login_required
def delete_request(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)

    req = get_object_or_404(Request, pk=pk)
    with transaction.atomic():
        _delete_request_files(req)
        req.delete()
    return JsonResponse({'success': True})


@login_required
def delete_worker(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.profile.role != 'admin':
        return JsonResponse({'error': 'permission denied'}, status=403)

    worker = get_object_or_404(User, pk=pk, profile__role='worker')
    worker_name = worker.first_name or worker.username
    worker.delete()
    return JsonResponse({'success': True, 'worker_name': worker_name})

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

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # Комментарий обязателен при отмене. Может прийти в этом POST,
    # либо быть уже сохранён через /edit-request/ перед отменой.
    cancel_comment = ''
    try:
        if request.content_type and request.content_type.startswith('application/json'):
            payload = json.loads((request.body or b'{}').decode('utf-8'))
            cancel_comment = (payload.get('comment') or '').strip()
        else:
            cancel_comment = (request.POST.get('comment') or '').strip()
    except Exception:
        cancel_comment = ''

    effective_comment = cancel_comment or (req.comment or '').strip()
    if not effective_comment:
        return JsonResponse({'error': 'Комментарий обязателен при отмене заявки'}, status=400)
    if cancel_comment:
        req.comment = cancel_comment

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
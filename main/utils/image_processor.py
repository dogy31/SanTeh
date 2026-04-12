"""
Обработка загруженных изображений: HEIC/WEBP/TIFF/GIF и т.д. → JPG, ресайз, без EXIF.
"""
from __future__ import annotations

import logging
import uuid
from io import BytesIO
from time import time

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_LONG_SIDE = 1920
JPEG_QUALITY = 85

ALLOWED_CONTENT_TYPES = frozenset({
    'image/jpeg',
    'image/jpg',
    'image/pjpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/tiff',
    'image/x-tiff',
    'image/heic',
    'image/heif',
})

ALLOWED_SUFFIXES = frozenset({
    '.jpg', '.jpeg', '.png', '.webp', '.gif', '.tif', '.tiff', '.heic', '.heif',
})


class ImageProcessingUserError(Exception):
    """Ошибка, которую можно показать пользователю (или обернуть в 400)."""
    pass


class FileTooLargeError(ImageProcessingUserError):
    def __init__(self, message: str = 'Файл слишком большой (макс. 20МБ)'):
        super().__init__(message)


class NotAnImageError(ImageProcessingUserError):
    def __init__(self, message: str = 'Только изображения'):
        super().__init__(message)


class ImageConversionError(ImageProcessingUserError):
    def __init__(self, message: str = 'Не удалось обработать изображение'):
        super().__init__(message)


def _register_heif():
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception as e:
        logger.warning('pillow_heif недоступен, HEIC может не открываться: %s', e)


_register_heif()


def _normalize_upload_subdir(upload_subdir: str) -> str:
    sub = (upload_subdir or 'requests').strip().strip('/').replace('\\', '/')
    if not sub or '..' in sub.split('/'):
        return 'requests'
    return sub


def validate_image_upload_preflight(file: UploadedFile) -> None:
    """Быстрая проверка размера и типа до тяжёлой конвертации."""
    if not file:
        raise NotAnImageError()
    try:
        size = file.size
    except (TypeError, AttributeError):
        size = None
    if size is not None and size > MAX_UPLOAD_BYTES:
        raise FileTooLargeError()

    name = (getattr(file, 'name', '') or '').lower()
    suffix = ''
    if '.' in name:
        suffix = name[name.rfind('.'):]

    ctype = (getattr(file, 'content_type', '') or '').split(';')[0].strip().lower()
    if ctype and ctype not in ALLOWED_CONTENT_TYPES and ctype != 'application/octet-stream':
        if suffix not in ALLOWED_SUFFIXES:
            raise NotAnImageError()

    if not ctype or ctype == 'application/octet-stream':
        if suffix and suffix not in ALLOWED_SUFFIXES:
            raise NotAnImageError()


def _open_raster_image(file: UploadedFile) -> Image.Image:
    file.seek(0)
    try:
        img = Image.open(file)
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as e:
        logger.info('Файл не распознан как изображение: %s', e)
        raise NotAnImageError() from e

    if getattr(img, 'is_animated', False):
        img.seek(0)
    img = img.copy()
    return img


def _to_rgb_jpeg_ready(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode in ('RGBA', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img)
        img = background
    elif img.mode == 'P':
        img = img.convert('RGBA')
        return _to_rgb_jpeg_ready(img)
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    return img


def _resize_long_side(img: Image.Image, max_side: int) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    if longest <= max_side:
        return img
    if w >= h:
        nw = max_side
        nh = max(1, int(round(h * max_side / w)))
    else:
        nh = max_side
        nw = max(1, int(round(w * max_side / h)))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def process_uploaded_image(file: UploadedFile, *, upload_subdir: str = 'requests') -> str:
    """
    Принимает Django UploadedFile, сохраняет JPEG в MEDIA через default_storage.
    Возвращает относительный путь (например requests/<uuid>_<ts>.jpg).
    """
    validate_image_upload_preflight(file)

    try:
        img = _open_raster_image(file)
        img = _to_rgb_jpeg_ready(img)
        img = _resize_long_side(img, MAX_LONG_SIDE)
    except NotAnImageError:
        raise
    except Exception as e:
        logger.exception('Ошибка конвертации изображения')
        raise ImageConversionError() from e

    buf = BytesIO()
    try:
        img.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
    except Exception as e:
        logger.exception('Ошибка сохранения JPEG')
        raise ImageConversionError() from e

    raw = buf.getvalue()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise FileTooLargeError()

    sub = _normalize_upload_subdir(upload_subdir)
    ts = int(time())
    fname = f'{uuid.uuid4().hex}_{ts}.jpg'
    rel_path = f'{sub}/{fname}'

    try:
        saved = default_storage.save(rel_path, ContentFile(raw))
    except Exception as e:
        logger.exception('Ошибка записи файла в хранилище')
        raise ImageConversionError() from e

    return saved

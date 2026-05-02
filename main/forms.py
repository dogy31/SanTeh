from django import forms

from .phone_utils import normalize_phone
from .utils.image_processor import (
    FileTooLargeError,
    NotAnImageError,
    validate_image_upload_preflight,
)


class RequestForm(forms.Form):
    """Поля создания заявки (POST) и вспомогательные проверки файлов."""

    description = forms.CharField()
    client_name = forms.CharField(max_length=100, required=False)
    client_phone = forms.CharField(max_length=32)
    client_phone_2 = forms.CharField(max_length=32, required=False)
    client_address = forms.CharField(max_length=200)
    house_number = forms.CharField(max_length=20, required=False)
    entrance = forms.CharField(max_length=20, required=False)
    floor = forms.CharField(max_length=20, required=False)
    apartment = forms.CharField(max_length=20, required=False)
    equipment_type = forms.CharField(max_length=100, required=False)
    worker_id = forms.IntegerField(required=False)
    deadline_date = forms.DateField()
    visit_time = forms.TimeField(required=False)
    worker_percent = forms.IntegerField(min_value=0, max_value=100, initial=50)

    def clean_client_address(self):
        addr = (self.cleaned_data.get('client_address') or '').strip()
        if not addr:
            raise forms.ValidationError('Адрес обязателен для заполнения')
        return addr

    def clean_client_phone_2(self):
        raw = self.cleaned_data.get('client_phone_2')
        normalized = normalize_phone(raw or '')
        if not normalized:
            return ''
        if len(normalized) != 11:
            raise forms.ValidationError('Второй телефон: введите 11 цифр в формате +7')
        return normalized

    def clean_worker_percent(self):
        val = self.cleaned_data.get('worker_percent')
        if val is None:
            return 50
        return val

    @staticmethod
    def validate_single_image_file(uploaded) -> None:
        """Проверка одного файла до конвертации (размер, тип)."""
        try:
            validate_image_upload_preflight(uploaded)
        except FileTooLargeError as e:
            raise forms.ValidationError(str(e)) from e
        except NotAnImageError as e:
            raise forms.ValidationError(str(e)) from e

    @classmethod
    def validate_contract_photo_files(cls, files, max_count: int = 5) -> None:
        if len(files) > max_count:
            raise forms.ValidationError(f'Максимум {max_count} фотографий договора')
        for f in files:
            cls.validate_single_image_file(f)

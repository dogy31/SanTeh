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

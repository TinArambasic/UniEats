def validate_student_card_number(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Broj kartice je obavezan")
    if not normalized.isdigit():
        raise ValueError("Broj kartice smije sadrzavati samo znamenke")
    if len(normalized) < 6 or len(normalized) > 32:
        raise ValueError("Broj kartice mora imati izmedu 6 i 32 znamenke")
    return normalized

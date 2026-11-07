import re

KENYAN_MOBILE = re.compile(r"254[17]\d{8}")


def normalise_phone(value: str) -> str:
    """Return a Kenyan mobile number as 2547XXXXXXXX, the form M-Pesa expects."""
    digits = re.sub(r"[\s()+-]", "", value or "")
    if digits.startswith("0"):
        digits = "254" + digits[1:]
    if not KENYAN_MOBILE.fullmatch(digits):
        raise ValueError("Enter a Kenyan mobile number, like 0712345678")
    return digits

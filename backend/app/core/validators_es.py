"""
Validadores de formato real para identificadores fiscales y bancarios españoles.

- NIF (persona física): 8 dígitos + letra de control calculada por módulo 23.
- CIF (persona jurídica): letra inicial + 7 dígitos + dígito/letra de control
  calculado con el algoritmo estándar de la Agencia Tributaria.
- IBAN: checksum mod-97 estándar (ISO 7064 MOD 97-10), no solo longitud/prefijo.

Estos validadores se usan tanto en el schema Pydantic del backend (fuente de
verdad, nunca confiar solo en el frontend) como para generar el mensaje de
error que ve el usuario.
"""
import re

_NIF_CONTROL_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_CIF_CONTROL_LETTERS = "JABCDEFGHI"
_CIF_LETTER_ONLY = set("KPQS")  # organismos que exigen SIEMPRE letra de control
_CIF_DIGIT_ONLY = set("ABEH")  # sociedades que exigen SIEMPRE dígito de control


def _clean(value: str) -> str:
    return re.sub(r"[\s-]", "", str(value or "")).upper()


def validar_nif(value: str) -> bool:
    """NIF de persona física: 8 dígitos + letra de control (mod 23)."""
    v = _clean(value)
    m = re.fullmatch(r"(\d{8})([A-Z])", v)
    if not m:
        return False
    numero, letra = m.groups()
    return _NIF_CONTROL_LETTERS[int(numero) % 23] == letra


def validar_cif(value: str) -> bool:
    """CIF de persona jurídica: letra inicial + 7 dígitos + dígito/letra de control."""
    v = _clean(value)
    m = re.fullmatch(r"([A-HJNPQRSUVW])(\d{7})([0-9A-J])", v)
    if not m:
        return False
    letra_inicial, numero, control = m.groups()

    suma_par = 0
    suma_impar = 0
    for idx, ch in enumerate(numero):
        digito = int(ch)
        if idx % 2 == 0:
            # posiciones 1, 3, 5, 7 (1-indexadas) se duplican
            digito *= 2
            if digito > 9:
                digito -= 9
            suma_impar += digito
        else:
            suma_par += digito

    total = suma_par + suma_impar
    digito_control = (10 - (total % 10)) % 10
    letra_control = _CIF_CONTROL_LETTERS[digito_control]

    if letra_inicial in _CIF_LETTER_ONLY:
        return control == letra_control
    if letra_inicial in _CIF_DIGIT_ONLY:
        return control == str(digito_control)
    # el resto de letras admiten históricamente dígito o letra de control
    return control == str(digito_control) or control == letra_control


def validar_nif_cif(value: str) -> bool:
    """Valida indistintamente un NIF (persona física) o un CIF (empresa)."""
    v = _clean(value)
    if re.fullmatch(r"\d{8}[A-Z]", v):
        return validar_nif(v)
    if re.fullmatch(r"[A-HJNPQRSUVW]\d{7}[0-9A-J]", v):
        return validar_cif(v)
    return False


def validar_iban(value: str) -> bool:
    """Checksum mod-97 estándar (ISO 7064 MOD 97-10) sobre el IBAN completo."""
    v = _clean(value)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", v):
        return False
    rearranged = v[4:] + v[:4]
    numeric_chars = []
    for ch in rearranged:
        if ch.isdigit():
            numeric_chars.append(ch)
        else:
            numeric_chars.append(str(ord(ch) - 55))  # A=10 ... Z=35
    numeric = "".join(numeric_chars)
    return int(numeric) % 97 == 1


def mask_iban(value: str) -> str:
    """Enmascara el IBAN dejando visibles solo el código de país y los últimos 4 caracteres."""
    v = _clean(value)
    if len(v) < 8:
        return "*" * len(v)
    country = v[:2]
    last4 = v[-4:]
    middle_len = len(v) - len(country) - len(last4)
    masked = f"{country}{'*' * middle_len}{last4}"
    return " ".join(masked[i:i + 4] for i in range(0, len(masked), 4))

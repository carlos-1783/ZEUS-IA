"""
Parser MRZ ICAO 9303 con validación de checksums (DNIe / TD1 / TD2).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def _char_value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    return 0


def _check_digit(data: str) -> str:
    weights = (7, 3, 1)
    total = sum(_char_value(c) * weights[i % 3] for i, c in enumerate(data))
    return str(total % 10)


def _validate_check(data: str, expected: str) -> bool:
    if not expected or expected == "<":
        return True
    return _check_digit(data) == expected


def _compact_mrz(raw: str) -> str:
    return re.sub(r"[^A-Z0-9<]", "", (raw or "").upper())


def _clean_lines(mrz: str) -> List[str]:
    return [re.sub(r"\s+", "", ln.upper()) for ln in (mrz or "").strip().splitlines() if ln.strip()]


def _coerce_lines(mrz: str) -> List[str]:
    lines = _clean_lines(mrz)
    if len(lines) >= 2:
        return lines

    compact = _compact_mrz(mrz)
    if not compact:
        return []
    if len(compact) == 90:
        return [compact[0:30], compact[30:60], compact[60:90]]
    if len(compact) == 72:
        return [compact[0:36], compact[36:72]]
    return lines or [compact]


def _parse_td1(lines: List[str]) -> Dict[str, Any]:
    if len(lines) < 3:
        raise ValueError("MRZ TD1 incompleto (se requieren 3 líneas)")
    l1 = lines[0].ljust(30, "<")[:30]
    l2 = lines[1].ljust(30, "<")[:30]
    l3 = lines[2].ljust(30, "<")[:30]
    if len(l1) < 30 or len(l2) < 30:
        raise ValueError("Líneas MRZ TD1 demasiado cortas")

    doc_number = l1[5:14].replace("<", "")
    doc_check = l1[14]
    if not _validate_check(doc_number, doc_check):
        raise ValueError("Checksum de número de documento inválido")

    birth_raw = l2[0:6]
    birth_check = l2[6]
    if not _validate_check(birth_raw, birth_check):
        raise ValueError("Checksum de fecha de nacimiento inválido")

    sex = l2[7]
    expiry_raw = l2[8:14]
    expiry_check = l2[14]
    if not _validate_check(expiry_raw, expiry_check):
        raise ValueError("Checksum de fecha de caducidad inválido")

    nationality = l2[15:18].replace("<", "")
    composite = l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29]
    composite_check = l2[29] if len(l2) > 29 else ""
    if composite_check and composite_check != "<" and not _validate_check(composite, composite_check):
        raise ValueError("Checksum compuesto inválido")

    names_raw = l3.replace("<", " ").strip()
    name_parts = [p for p in names_raw.split() if p]
    surname = name_parts[0] if name_parts else ""
    given_names = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    return {
        "format": "TD1",
        "document_number": doc_number,
        "birth_date": f"19{birth_raw[0:2]}-{birth_raw[2:4]}-{birth_raw[4:6]}" if int(birth_raw[0:2]) > 30 else f"20{birth_raw[0:2]}-{birth_raw[2:4]}-{birth_raw[4:6]}",
        "expiry_date": f"20{expiry_raw[0:2]}-{expiry_raw[2:4]}-{expiry_raw[4:6]}",
        "sex": sex,
        "nationality": nationality,
        "surname": surname,
        "given_names": given_names,
        "full_name": f"{given_names} {surname}".strip() or surname,
    }


def _parse_td2(lines: List[str]) -> Dict[str, Any]:
    if len(lines) < 2:
        raise ValueError("MRZ TD2/TD3 incompleto (se requieren 2 líneas)")
    l1, l2 = lines[0], lines[1]
    if len(l1) < 36 or len(l2) < 36:
        raise ValueError("Líneas MRZ demasiado cortas")

    doc_number = l1[5:14].replace("<", "")
    doc_check = l1[14]
    if not _validate_check(doc_number, doc_check):
        raise ValueError("Checksum de número de documento inválido")

    birth_raw = l2[0:6]
    birth_check = l2[6]
    if not _validate_check(birth_raw, birth_check):
        raise ValueError("Checksum de fecha de nacimiento inválido")

    expiry_raw = l2[8:14]
    expiry_check = l2[14]
    if not _validate_check(expiry_raw, expiry_check):
        raise ValueError("Checksum de fecha de caducidad inválido")

    nationality = l2[10:13].replace("<", "")
    names_raw = l1[5:].split("<<", 1)
    surname = (names_raw[0] if names_raw else "").replace("<", " ").strip()
    given = (names_raw[1] if len(names_raw) > 1 else "").replace("<", " ").strip()

    return {
        "format": "TD2",
        "document_number": doc_number,
        "birth_date": f"19{birth_raw[0:2]}-{birth_raw[2:4]}-{birth_raw[4:6]}" if int(birth_raw[0:2]) > 30 else f"20{birth_raw[0:2]}-{birth_raw[2:4]}-{birth_raw[4:6]}",
        "expiry_date": f"20{expiry_raw[0:2]}-{expiry_raw[2:4]}-{expiry_raw[4:6]}",
        "nationality": nationality,
        "surname": surname,
        "given_names": given,
        "full_name": f"{given} {surname}".strip() or surname,
    }


def parse_mrz(mrz: str) -> Dict[str, Any]:
    """Parsear MRZ con validación de checksums ICAO."""
    lines = _coerce_lines(mrz)
    if not lines:
        raise ValueError("MRZ vacío")
    if len(lines) >= 3:
        return _parse_td1(lines[:3])
    if len(lines) == 1:
        raise ValueError("MRZ incompleto: pega cada línea en su propia línea.")
    if len(lines) == 2 and max(len(lines[0]), len(lines[1])) < 36:
        raise ValueError("MRZ incompleto: para DNIe/TD1 pega las 3 líneas completas.")
    return _parse_td2(lines[:2])

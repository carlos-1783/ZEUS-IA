"""
La limpieza del texto de PERSEO no debe alterar cifras: antes la regex `\\b\\d+\\.\\s*` borraba
decimales e importes («3.5» -> «5», «9.20€» -> «20€»). Solo se quita la numeración de lista
a inicio de línea («1. uno»).
"""

import pytest

from services.workspace_deliverables import _clean_marketing_text, normalize_perseo_chat_message


@pytest.mark.parametrize(
    "texto, cifra",
    [
        ("Tu valoración media es 3.5 sobre 5.", "3.5"),
        ("El menú del día cuesta 9.20€ con bebida.", "9.20€"),
        ("La facturación del mes fue de 1.234,56 € en total.", "1.234,56 €"),
    ],
)
def test_cifras_intactas(texto, cifra):
    assert cifra in _clean_marketing_text(texto)
    assert cifra in normalize_perseo_chat_message(texto)


def test_cifras_intactas_entre_parrafos():
    texto = "Tu valoración media es 3.5 sobre 5.\n\nEl menú cuesta 9.20€ y facturaste 1.234,56 €."
    limpio = normalize_perseo_chat_message(texto)
    for cifra in ("3.5 sobre 5.", "9.20€", "1.234,56 €"):
        assert cifra in limpio
    # Los párrafos no se fusionan.
    assert "\n\n" in limpio


def test_cifra_al_inicio_de_linea_sin_espacio_se_conserva():
    assert _clean_marketing_text("1.234,56 € es lo que facturaste.").startswith("1.234,56 €")


def test_numeracion_de_lista_se_quita():
    assert _clean_marketing_text("1. uno\n2. dos") == "uno\ndos"


def test_lista_tras_parrafo_no_pega_los_parrafos():
    texto = "Intro del plan:\n\n1. uno\n2. dos\n\nCierre."
    assert normalize_perseo_chat_message(texto) == "Intro del plan:\n\nuno\ndos\n\nCierre."
    assert normalize_perseo_chat_message("Linea a\r\n\r\n1. uno\r\n2. dos\r\n") == "Linea a\n\nuno\ndos"

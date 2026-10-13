"""Fase 2 #7 — fetch seguro anti-SSRF (services/safe_http_fetch.py).

Sin red real: se sustituye la resolución DNS y el "opener" HTTP por dobles de test
para comprobar que NUNCA se conecta a una IP no pública, que el esquema/puerto se
validan y que cada redirección se revalida desde cero.
"""

from __future__ import annotations

import socket

import pytest

import services.safe_http_fetch as sf


@pytest.fixture
def dns(monkeypatch):
    table = {}

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host not in table:
            raise socket.gaierror("no such host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in table[host]]

    monkeypatch.setattr(sf.socket, "getaddrinfo", fake_getaddrinfo)
    return table


@pytest.fixture
def opener(monkeypatch):
    calls = []
    responses = {}

    def fake_open(scheme, ip, port, hostname, path, timeout):
        calls.append((scheme, ip, port, hostname, path))
        status, headers, body = responses[(hostname, path)]
        return status, headers, [body]

    monkeypatch.setattr(sf, "_opener", fake_open)
    return calls, responses


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.16.3.4",
        "192.168.1.1",
        "169.254.169.254",  # metadata cloud
        "100.64.0.1",  # CGNAT
        "0.0.0.0",
        "224.0.0.1",  # multicast
        "240.0.0.1",  # reservada
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",  # IPv4 mapeada
        "ff02::1",
    ],
)
def test_bloquea_ips_no_publicas_por_dns(dns, opener, ip):
    calls, _ = opener
    dns["interno.example"] = [ip]
    with pytest.raises(sf.UnsafeUrlError):
        sf.safe_fetch("https://interno.example/x", allowed_content_types=["text/html"])
    assert calls == [], "no debe abrirse conexion hacia una IP no publica"


def test_bloquea_ip_literal_privada(opener):
    calls, _ = opener
    with pytest.raises(sf.UnsafeUrlError):
        sf.safe_fetch("https://192.168.0.10/admin", allowed_content_types=["text/html"])
    with pytest.raises(sf.UnsafeUrlError):
        sf.safe_fetch("https://[::1]/", allowed_content_types=["text/html"])
    assert calls == []


def test_bloquea_si_alguna_de_las_ips_resueltas_es_privada(dns, opener):
    calls, _ = opener
    dns["mixto.example"] = ["93.184.216.34", "10.1.1.1"]
    with pytest.raises(sf.UnsafeUrlError):
        sf.safe_fetch("https://mixto.example/", allowed_content_types=["text/html"])
    assert calls == []


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://example.com/",
        "ftp://example.com/x",
        "http://example.com/",  # http no permitido por defecto
        "https://user:pass@example.com/",
        "https://example.com:8443/",
        "https:///sinhost",
        "",
    ],
)
def test_rechaza_esquemas_credenciales_y_puertos(dns, opener, url):
    calls, _ = opener
    dns["example.com"] = ["93.184.216.34"]
    with pytest.raises(sf.UnsafeUrlError):
        sf.safe_fetch(url, allowed_content_types=["text/html"])
    assert calls == []


def test_http_solo_si_se_permite_explicitamente(dns, opener):
    calls, responses = opener
    dns["example.com"] = ["93.184.216.34"]
    responses[("example.com", "/")] = (200, {"content-type": "text/html"}, b"<html></html>")
    res = sf.safe_fetch("http://example.com/", allowed_content_types=["text/html"], allow_http=True)
    assert res.status == 200
    assert calls[0][:3] == ("http", "93.184.216.34", 80)


def test_descarga_publica_conecta_a_la_ip_validada(dns, opener):
    calls, responses = opener
    dns["example.com"] = ["93.184.216.34"]
    responses[("example.com", "/pagina?a=1")] = (200, {"content-type": "text/html; charset=utf-8"}, b"<title>Hola</title>")
    res = sf.safe_fetch("https://example.com/pagina?a=1", allowed_content_types=["text/html"])
    assert res.text() == "<title>Hola</title>"
    assert calls == [("https", "93.184.216.34", 443, "example.com", "/pagina?a=1")]


def test_redireccion_a_ip_interna_se_bloquea(dns, opener):
    calls, responses = opener
    dns["example.com"] = ["93.184.216.34"]
    dns["metadata.internal"] = ["169.254.169.254"]
    responses[("example.com", "/")] = (302, {"location": "https://metadata.internal/latest/meta-data"}, b"")
    with pytest.raises(sf.UnsafeUrlError):
        sf.safe_fetch("https://example.com/", allowed_content_types=["text/html"])
    assert len(calls) == 1, "el segundo salto no debe llegar a conectarse"


def test_redireccion_a_http_se_bloquea_si_no_se_permite(dns, opener):
    _, responses = opener
    dns["example.com"] = ["93.184.216.34"]
    responses[("example.com", "/")] = (301, {"location": "http://example.com/"}, b"")
    with pytest.raises(sf.UnsafeUrlError):
        sf.safe_fetch("https://example.com/", allowed_content_types=["text/html"])


def test_redireccion_valida_se_sigue_y_demasiadas_fallan(dns, opener):
    calls, responses = opener
    dns["a.example"] = ["93.184.216.34"]
    dns["b.example"] = ["93.184.216.35"]
    responses[("a.example", "/")] = (301, {"location": "https://b.example/final"}, b"")
    responses[("b.example", "/final")] = (200, {"content-type": "text/html"}, b"ok")
    res = sf.safe_fetch("https://a.example/", allowed_content_types=["text/html"])
    assert res.final_url == "https://b.example/final"
    assert res.redirects == ["https://b.example/final"]

    responses[("a.example", "/loop")] = (302, {"location": "/loop"}, b"")
    with pytest.raises(sf.FetchFailedError):
        sf.safe_fetch("https://a.example/loop", allowed_content_types=["text/html"], max_redirects=2)


def test_content_type_tamano_y_http_error(dns, opener):
    _, responses = opener
    dns["example.com"] = ["93.184.216.34"]
    responses[("example.com", "/img")] = (200, {"content-type": "text/html"}, b"<html>")
    with pytest.raises(sf.FetchFailedError):
        sf.safe_fetch("https://example.com/img", allowed_content_types=["image/"])

    responses[("example.com", "/big")] = (200, {"content-type": "image/png"}, b"x" * 2000)
    with pytest.raises(sf.FetchFailedError):
        sf.safe_fetch("https://example.com/big", allowed_content_types=["image/"], max_bytes=1000)

    responses[("example.com", "/404")] = (404, {"content-type": "text/html"}, b"")
    with pytest.raises(sf.FetchFailedError):
        sf.safe_fetch("https://example.com/404", allowed_content_types=["text/html"])

    responses[("example.com", "/ok.png")] = (200, {"content-type": "image/png"}, b"\x89PNG")
    assert sf.safe_fetch("https://example.com/ok.png", allowed_content_types=["image/"]).body == b"\x89PNG"


def test_dominio_que_no_resuelve_falla_controlado(dns, opener):
    with pytest.raises(sf.FetchFailedError):
        sf.safe_fetch("https://no-existe.example/", allowed_content_types=["text/html"])


def test_fallo_de_red_prueba_la_siguiente_ip_validada_y_luego_falla_controlado(dns, monkeypatch):
    dns["example.com"] = ["93.184.216.34", "93.184.216.35"]
    tried = []

    def flaky(scheme, ip, port, hostname, path, timeout):
        tried.append(ip)
        if ip.endswith(".34"):
            raise ConnectionResetError("reset")
        return 200, {"content-type": "text/html"}, [b"ok"]

    monkeypatch.setattr(sf, "_opener", flaky)
    assert sf.safe_fetch("https://example.com/", allowed_content_types=["text/html"]).body == b"ok"
    assert tried == ["93.184.216.34", "93.184.216.35"]

    def down(*a, **k):
        raise ConnectionResetError("reset")

    monkeypatch.setattr(sf, "_opener", down)
    with pytest.raises(sf.FetchFailedError):
        sf.safe_fetch("https://example.com/", allowed_content_types=["text/html"])

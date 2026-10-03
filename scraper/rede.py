"""HTTP compartilhado pelos scrapers.

- User-Agent de navegador real e headers em pt-BR.
- Delay aleatório de 1-3s entre requests (reduz risco de bloqueio).
- Se o `requests` levar 403/429/503 ou cair num desafio anti-bot (Cloudflare),
  tenta de novo com `curl_cffi`, que imita a impressão digital TLS do Chrome.
"""

import random
import time

import requests

try:
    from curl_cffi import requests as cffi_requests
except ImportError:  # dependência opcional em ambiente local
    cffi_requests = None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
]

TIMEOUT = 25
STATUS_BLOQUEIO = {403, 429, 503}
MARCAS_DESAFIO = (
    "cf-chl", "challenge-platform", "Just a moment...", "Attention Required!",  # Cloudflare
    "suspicious-traffic-frontend", "account-verification",  # Mercado Livre
    "bm-verify", "validateCaptcha",  # Amazon
)

_ultimo_request = 0.0
_sessao: requests.Session | None = None


class ErroHTTP(Exception):
    pass


def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }


def _sessao_requests() -> requests.Session:
    global _sessao
    if _sessao is None:
        _sessao = requests.Session()
        _sessao.headers.update(_headers())
    return _sessao


def aguardar() -> None:
    """Garante 1-3s aleatórios desde o último request."""
    global _ultimo_request
    espera = random.uniform(1.0, 3.0) - (time.monotonic() - _ultimo_request)
    if _ultimo_request and espera > 0:
        time.sleep(espera)
    _ultimo_request = time.monotonic()


def _parece_bloqueado(status: int, texto: str) -> bool:
    if status in STATUS_BLOQUEIO:
        return True
    return any(m in texto[:5000] for m in MARCAS_DESAFIO)


def get(url: str, *, json_api: bool = False, extra_headers: dict | None = None) -> tuple[int, str]:
    """GET com delay e fallback. Devolve (status, corpo). Lança ErroHTTP em falha de rede."""
    aguardar()
    headers = dict(extra_headers or {})
    if json_api:
        headers["Accept"] = "application/json"

    status, texto = 0, ""
    try:
        resp = _sessao_requests().get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        status, texto = resp.status_code, resp.text
        if not _parece_bloqueado(status, texto):
            return status, texto
        print(f"  [http] requests bloqueado (HTTP {status}) em {url[:80]}")
    except requests.RequestException as e:
        print(f"  [http] erro com requests: {type(e).__name__}: {e}")

    if cffi_requests is None:
        if status:
            return status, texto
        raise ErroHTTP("falha de rede e curl_cffi não instalado")

    aguardar()
    try:
        resp = cffi_requests.get(
            url,
            impersonate="chrome",
            headers={"Accept-Language": "pt-BR,pt;q=0.9", **headers},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        print(f"  [http] curl_cffi: HTTP {resp.status_code}")
        return resp.status_code, resp.text
    except Exception as e:  # curl_cffi tem hierarquia própria de exceções
        if status:
            return status, texto
        raise ErroHTTP(f"falha de rede ({type(e).__name__}: {e})") from None


def get_html(url: str) -> str:
    """GET que exige HTTP 200 e não-desafio; devolve o HTML."""
    status, texto = get(url)
    if status != 200:
        raise ErroHTTP(f"HTTP {status}")
    if _parece_bloqueado(status, texto):
        raise ErroHTTP("página de desafio anti-bot (Cloudflare/captcha)")
    return texto


def resolver_redirect(url: str) -> str:
    """Segue redirects (ex.: amzn.to, links encurtados) e devolve a URL final."""
    try:
        resp = _sessao_requests().head(url, allow_redirects=True, timeout=TIMEOUT)
        if resp.url and resp.status_code < 400:
            return resp.url
        resp = _sessao_requests().get(url, allow_redirects=True, timeout=TIMEOUT, stream=True)
        resp.close()
        return resp.url or url
    except requests.RequestException:
        return url

"""Amazon (scraping direto do HTML).

AVISO DE FRAGILIDADE: a Amazon combate scraping ativamente. A partir de IPs
de datacenter (como os runners do GitHub Actions) é comum receber página de
captcha ou HTTP 503, e o layout muda com frequência. Por isso este site roda
num workflow separado e mais espaçado (a cada 3h). Se parar de funcionar,
os logs vão mostrar "captcha"/"bloqueado" — não é bug do resto do bot.
Raspar a Amazon também pode violar os Termos de Uso dela; use com moderação.
"""

import re

from scraper import rede
from scraper.sites._parse import PrecoNaoEncontrado, parse_brl, preco_meta, primeiro_preco, sopa

RE_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})", re.I)

SELETORES = [
    "#corePrice_feature_div .a-price .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    "#apex_desktop .a-price .a-offscreen",
    "#priceblock_dealprice",
    "#priceblock_ourprice",
    "#price_inside_buybox",
    "#tp_price_block_total_price_ww .a-offscreen",
    ".a-price .a-offscreen",
]


def url_canonica(url: str) -> str:
    """Reduz a URL a amazon.com.br/dp/ASIN (menos parâmetros de rastreio)."""
    m = RE_ASIN.search(url)
    return f"https://www.amazon.com.br/dp/{m.group(1).upper()}" if m else url


def obter_preco(url: str) -> tuple[float, str | None]:
    status, html = rede.get(url_canonica(url))
    if any(m in html for m in ("validateCaptcha", "bm-verify", "api-services-support@amazon.com")):
        raise PrecoNaoEncontrado("Amazon devolveu captcha (bloqueio anti-bot)")
    if status != 200:
        raise PrecoNaoEncontrado(f"Amazon respondeu HTTP {status}")

    soup = sopa(html)

    def via_seletores():
        for sel in SELETORES:
            tag = soup.select_one(sel)
            if tag and parse_brl(tag.get_text()):
                return parse_brl(tag.get_text())
        return None

    def via_partes():
        inteiro = soup.select_one("#corePrice_feature_div .a-price-whole, .a-price-whole")
        if not inteiro:
            return None
        fracao = soup.select_one("#corePrice_feature_div .a-price-fraction, .a-price-fraction")
        texto = inteiro.get_text(strip=True).rstrip(",.")
        return parse_brl(f"{texto},{fracao.get_text(strip=True) if fracao else '00'}")

    preco = primeiro_preco("amazon", [
        ("seletores .a-offscreen", via_seletores),
        ("a-price-whole/fraction", via_partes),
        ("meta", lambda: preco_meta(soup)),
    ])
    tag_nome = soup.select_one("#productTitle")
    return preco, tag_nome.get_text(strip=True) if tag_nome else None

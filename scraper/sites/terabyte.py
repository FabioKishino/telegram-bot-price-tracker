"""Terabyte (requests + BeautifulSoup).

Preço à vista fica em `#valVista`; há também `.val-prod`. Fallbacks:
JSON-LD e meta tags. A loja usa Cloudflare, por isso o fallback curl_cffi
em scraper/rede.py. O HTML pode mudar sem aviso.
"""

from scraper import rede
from scraper.sites._parse import parse_brl, preco_jsonld, preco_meta, primeiro_preco, sopa, titulo


def obter_preco(url: str) -> tuple[float, str | None]:
    soup = sopa(rede.get_html(url))
    nome = {}

    def via_seletor():
        for sel in ("#valVista", "#prod-new-price", ".val-prod", "p.valVista"):
            tag = soup.select_one(sel)
            if tag and parse_brl(tag.get_text()):
                return parse_brl(tag.get_text())
        return None

    def via_jsonld():
        preco, n = preco_jsonld(soup)
        nome["v"] = n
        return preco

    preco = primeiro_preco("terabyte", [
        ("seletor #valVista", via_seletor),
        ("json-ld", via_jsonld),
        ("meta", lambda: preco_meta(soup)),
    ])
    tag_nome = soup.select_one("h1.tit-prod, h1")
    return preco, nome.get("v") or (tag_nome.get_text(strip=True) if tag_nome else titulo(soup))

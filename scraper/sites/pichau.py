"""Pichau (requests + BeautifulSoup).

A página é Next.js e traz JSON-LD de Product com `offers.price`. Fallbacks:
`__NEXT_DATA__` (preço à vista em chaves como `price_pix`/`final_price`) e
meta tags. Usa Cloudflare; o HTML pode mudar sem aviso.
"""

from scraper import rede
from scraper.sites._parse import (
    buscar_chaves,
    next_data,
    parse_brl,
    preco_jsonld,
    preco_meta,
    primeiro_preco,
    sopa,
    titulo,
)

CHAVES_PRECO = ("price_pix", "final_price", "special_price", "price")


def obter_preco(url: str) -> tuple[float, str | None]:
    soup = sopa(rede.get_html(url))
    nome = {}

    def via_jsonld():
        preco, n = preco_jsonld(soup)
        nome["v"] = n
        return preco

    def via_next_data():
        dados = next_data(soup)
        if not dados:
            return None
        for valor in buscar_chaves(dados, CHAVES_PRECO):
            preco = parse_brl(valor)
            if preco:
                return preco
        return None

    preco = primeiro_preco("pichau", [
        ("json-ld", via_jsonld),
        ("__NEXT_DATA__", via_next_data),
        ("meta", lambda: preco_meta(soup)),
    ])
    return preco, nome.get("v") or titulo(soup)

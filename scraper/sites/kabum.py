"""Kabum (requests + BeautifulSoup).

A página de produto é Next.js: o preço costuma estar no JSON de
`__NEXT_DATA__` (chaves `priceWithDiscount` = preço à vista/PIX, `price`).
Fallbacks: JSON-LD e meta tags. O HTML pode mudar sem aviso.
"""

import json

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

CHAVES_PRECO = ("priceWithDiscount", "discountPrice", "price")


def obter_preco(url: str) -> tuple[float, str | None]:
    soup = sopa(rede.get_html(url))
    dados = next_data(soup)
    nome = {}

    def via_next_data():
        if not dados:
            return None
        produto = buscar_chaves(dados, ("productData",))
        alvo = dados
        if produto and isinstance(produto[0], str):  # às vezes vem serializado como string
            try:
                alvo = json.loads(produto[0])
            except json.JSONDecodeError:
                pass
        nomes = buscar_chaves(alvo, ("name", "title"))
        nome["v"] = next((n for n in nomes if isinstance(n, str) and len(n) > 10), None)
        for valor in buscar_chaves(alvo, CHAVES_PRECO):
            preco = parse_brl(valor)
            if preco:
                return preco
        return None

    def via_jsonld():
        preco, n = preco_jsonld(soup)
        nome.setdefault("v", n)
        return preco

    def via_seletor():
        tag = soup.select_one("h4.finalPrice, [class*='finalPrice']")
        return parse_brl(tag.get_text()) if tag else None

    preco = primeiro_preco("kabum", [
        ("json-ld", via_jsonld),
        ("__NEXT_DATA__", via_next_data),
        ("meta", lambda: preco_meta(soup)),
        ("seletor finalPrice", via_seletor),
    ])
    return preco, nome.get("v") or titulo(soup)

"""Mercado Livre via API pública (api.mercadolibre.com), sem scraping.

- Anúncio:  produto.mercadolivre.com.br/MLB-1234567890-...  -> /items/MLB1234567890
- Catálogo: www.mercadolivre.com.br/.../p/MLB12345678       -> /products/MLB12345678

ATENÇÃO (testado em out/2026): a API responde 403 "PA_UNAUTHORIZED_RESULT_FROM_POLICIES"
para /items e /products sem token, e a página do produto, para clientes que
parecem robôs, vem como "micro-landing" (só título, sem preço) ou redireciona
para verificação de conta. Mantemos API -> HTML como cadeia de tentativas
para o caso de o bloqueio ser relaxado, mas hoje espere falhas neste site.
"""

import json
import re

from scraper import rede
from scraper.sites._parse import (
    PrecoNaoEncontrado,
    preco_jsonld,
    preco_meta,
    primeiro_preco,
    sopa,
    titulo,
)

API = "https://api.mercadolibre.com"
RE_CATALOGO = re.compile(r"/p/(MLB\d+)", re.I)
RE_ITEM = re.compile(r"(MLB)-?(\d{6,})", re.I)
RE_ITEM_QUERY = re.compile(r"[?&#](?:item_id|wid)[=:](MLB\d+)", re.I)


def _ids(url: str) -> tuple[str | None, str | None]:
    """Devolve (item_id, catalog_id)."""
    item = None
    m = RE_ITEM_QUERY.search(url)
    if m:
        item = m.group(1).upper()
    catalogo = RE_CATALOGO.search(url)
    if not item and not catalogo:
        m = RE_ITEM.search(url)
        if m:
            item = f"MLB{m.group(2)}"
    return item, catalogo.group(1).upper() if catalogo else None


def _api_json(caminho: str) -> dict | None:
    status, corpo = rede.get(f"{API}{caminho}", json_api=True)
    if status != 200:
        print(f"  [mercadolivre] API {caminho}: HTTP {status}")
        return None
    try:
        return json.loads(corpo)
    except json.JSONDecodeError:
        print(f"  [mercadolivre] API {caminho}: resposta não-JSON")
        return None


def _via_api(item_id: str | None, catalog_id: str | None) -> tuple[float | None, str | None]:
    if item_id:
        dados = _api_json(f"/items/{item_id}")
        if dados and dados.get("price"):
            return float(dados["price"]), dados.get("title")
    if catalog_id:
        dados = _api_json(f"/products/{catalog_id}")
        if dados:
            vencedor = dados.get("buy_box_winner") or {}
            if vencedor.get("price"):
                return float(vencedor["price"]), dados.get("name")
    return None, None


def _via_html(url: str) -> tuple[float, str | None]:
    html = rede.get_html(url)
    if "micro-landing" in html:
        # Página "leve" que o ML serve a clientes suspeitos de serem robôs: só título, sem preço.
        raise PrecoNaoEncontrado("ML devolveu página sem preço (bloqueio anti-bot)")
    soup = sopa(html)
    nome_ld = {}

    def jsonld():
        preco, nome = preco_jsonld(soup)
        nome_ld["v"] = nome
        return preco

    def andes_money():
        # Bloco de preço principal: <meta itemprop="price"> ou o componente andes-money-amount
        bloco = soup.select_one(".ui-pdp-price__second-line .andes-money-amount")
        if not bloco:
            return None
        fracao = bloco.select_one(".andes-money-amount__fraction")
        centavos = bloco.select_one(".andes-money-amount__cents")
        if not fracao:
            return None
        texto = fracao.get_text(strip=True).replace(".", "")
        if centavos:
            texto += "." + centavos.get_text(strip=True)
        return float(texto)

    preco = primeiro_preco("mercadolivre", [
        ("json-ld", jsonld),
        ("meta", lambda: preco_meta(soup)),
        ("andes-money", andes_money),
    ])
    return preco, nome_ld.get("v") or titulo(soup)


def obter_preco(url: str) -> tuple[float, str | None]:
    item_id, catalog_id = _ids(url)
    if item_id or catalog_id:
        preco, nome = _via_api(item_id, catalog_id)
        if preco:
            print(f"  [mercadolivre] preço via API: {preco:.2f}")
            return preco, nome
        print("  [mercadolivre] API sem preço; tentando a página HTML")
    else:
        print("  [mercadolivre] não achei id MLB na URL; tentando a página HTML")

    try:
        return _via_html(url)
    except PrecoNaoEncontrado:
        raise
    except rede.ErroHTTP as e:
        raise PrecoNaoEncontrado(f"API e HTML falharam ({e})") from None

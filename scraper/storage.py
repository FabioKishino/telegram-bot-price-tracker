"""Leitura e escrita dos arquivos JSON de estado em data/."""

import json
import os
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA_DIR = RAIZ / "data"
PRODUTOS = DATA_DIR / "produtos.json"
ESTADO = DATA_DIR / "estado.json"
LAST_UPDATE_ID = DATA_DIR / "last_update_id.json"


def ler_json(caminho: Path, padrao):
    """Lê um JSON; devolve `padrao` se o arquivo não existir ou estiver corrompido."""
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return padrao
    except json.JSONDecodeError as e:
        print(f"[storage] AVISO: {caminho.name} inválido ({e}); usando valor padrão")
        return padrao


def gravar_json(caminho: Path, dados) -> None:
    """Grava de forma atômica (arquivo temporário + rename)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, caminho)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def ler_produtos() -> list[dict]:
    dados = ler_json(PRODUTOS, [])
    return dados if isinstance(dados, list) else []


def ler_estado() -> dict:
    dados = ler_json(ESTADO, {})
    return dados if isinstance(dados, dict) else {}


def ler_last_update_id() -> int:
    dados = ler_json(LAST_UPDATE_ID, {})
    try:
        return int(dados.get("last_update_id", 0))
    except (AttributeError, TypeError, ValueError):
        return 0

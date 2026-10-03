"""Commit + push dos arquivos de estado, tolerante a workflows escrevendo em paralelo.

Fluxo: add -> commit -> pull --rebase -> push. Se o rebase conflitar, o
resultado não for JSON válido, ou o push for rejeitado, descartamos o commit
local, alinhamos com origin, chamamos `reaplicar()` (que relê os arquivos
remotos e reaplica só as mudanças desta execução) e tentamos mais uma vez.

Só roda dentro do GitHub Actions (GITHUB_ACTIONS=true), porque usa
`git reset --hard` — localmente isso apagaria alterações não commitadas.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable

from scraper.storage import RAIZ

BOT_NOME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


def _git(*args: str, checar: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)
    if checar and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} falhou: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def _json_valido(arquivos: list[str]) -> bool:
    for arq in arquivos:
        try:
            json.loads(Path(RAIZ, arq).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print(f"[git] {arq} ficou inválido após o rebase")
            return False
    return True


def _alinhar_com_origin(branch: str, reaplicar: Callable[[], None]) -> None:
    _git("rebase", "--abort", checar=False)
    _git("fetch", "origin", branch)
    _git("reset", "--hard", f"origin/{branch}")
    reaplicar()


def commit_e_push(
    arquivos: list[str],
    mensagem: str,
    reaplicar: Callable[[], None],
    tentativas: int = 2,
) -> bool:
    """Devolve True se não havia nada a commitar ou se o push deu certo."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print("[git] fora do GitHub Actions: pulando commit/push (arquivos gravados só localmente)")
        return True

    _git("config", "user.name", BOT_NOME)
    _git("config", "user.email", BOT_EMAIL)
    branch = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    for tentativa in range(1, tentativas + 1):
        _git("add", "--", *arquivos)
        if _git("diff", "--cached", "--quiet", checar=False).returncode == 0:
            print("[git] nada mudou; sem commit")
            return True

        _git("commit", "-m", mensagem)

        rebase = _git("pull", "--rebase", "origin", branch, checar=False)
        if rebase.returncode != 0 or not _json_valido(arquivos):
            print(f"[git] tentativa {tentativa}: pull --rebase falhou/conflitou; reaplicando sobre origin")
            _alinhar_com_origin(branch, reaplicar)
            continue

        push = _git("push", "origin", f"HEAD:{branch}", checar=False)
        if push.returncode == 0:
            print(f"[git] push ok (tentativa {tentativa})")
            return True

        print(f"[git] tentativa {tentativa}: push rejeitado: {push.stderr.strip()[:300]}")
        time.sleep(3)
        _alinhar_com_origin(branch, reaplicar)

    print("[git] ERRO: não consegui fazer push após as tentativas")
    return False

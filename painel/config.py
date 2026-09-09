# -*- coding: utf-8 -*-
"""Constantes do recorte "Escritório externo" e leitura das credenciais.

Credenciais SÓ vêm do ambiente ou de um .env local (não versionado).
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_VARS = ("ODOO_URL", "ODOO_DB", "ODOO_LOGIN", "ODOO_PASSWORD")


def load_dotenv(path: Path) -> None:
    """Carrega um .env simples (KEY=valor). O ambiente vence — é o esperado em CI."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_credentials(dotenv: Path | None = None) -> dict[str, str]:
    """Lê as credenciais do ambiente, ou de um .env indicado.

    Só olha o caminho pedido (padrão `./.env`) — nunca sai vasculhando o disco
    atrás de um arquivo de credencial. Quem quiser apontar para outro lugar usa
    `--env`, e aí é uma escolha visível na linha de comando.
    """
    load_dotenv(dotenv or Path(".env"))
    missing = [n for n in ENV_VARS if not os.environ.get(n)]
    if missing:
        raise RuntimeError(
            "Variáveis ausentes: " + ", ".join(missing)
            + ".\nCopie .env.example para .env e preencha, aponte outro arquivo com --env,"
            + " ou exporte as variáveis no ambiente/CI."
        )
    return {
        "url": os.environ["ODOO_URL"].rstrip("/"),
        "db": os.environ["ODOO_DB"],
        "login": os.environ["ODOO_LOGIN"],
        "password": os.environ["ODOO_PASSWORD"],
    }


# --------------------------------------------------------------------------
# O recorte (ids conferidos no servidor em set/2026)
# --------------------------------------------------------------------------

# "Escritório externo" não é um projeto: é uma família de 11 registros em
# project.project. Seis têm caso hoje; os outros cinco ficam na lista de
# propósito, para que um caso novo caia no painel sem precisar mexer no código.
PROJETOS_EXOFFICE = {
    427: "Consignado",
    428: "Revisionais",
    429: "Cautelar - Exibição",
    487: "Migrados",
    488: "Cessão de Crédito",
    489: "Indenizatória",
    490: "Migrados - Cautelar - Exibição",
    491: "Migrados - Revisionais",
    492: "Migrados - Indenizatória",
    493: "Migrados - Consignado",
    502: "Indenizatórias",
}
IDS_EXOFFICE = sorted(PROJETOS_EXOFFICE)

# Projetos que vieram da migração — viram um filtro próprio na página.
IDS_MIGRADOS = [487, 490, 491, 492, 493]

# tipo.sentenca
TIPO_IMPROCEDENTE = "1"
TIPO_PROCEDENTE = "2"
TIPO_EXTINCAO_SEM_MERITO = "3"
TIPO_PARCIALMENTE_PROCEDENTE = "4"
TIPO_HOMOLOGACAO_ACORDO = "5"
TIPO_EXTINCAO_EXECUCAO = "7"
TIPO_FAVORAVEL = "9"
TIPO_DESFAVORAVEL = "10"

# Êxito = Improcedente + Extinção (sem mérito ou da execução). Homologação de
# acordo fica no denominador; "sem tipo" fica fora e aparece em coluna própria.
# Mesma definição do painel "Êxito e Reversão" já publicado — os dois têm que
# conversar entre si.
NOMES_EXITO = ("Improcedente", "Extinção sem Julgamento do Mérito", "Extinção da Execução", "Favorável")
NOMES_DERROTA = ("Procedente", "Parcialmente Procedente", "Desfavorável")
NOME_ACORDO = "Homologação de Acordo"

CLASSE_FAVORAVEL = set(NOMES_EXITO)
CLASSE_DESFAVORAVEL = set(NOMES_DERROTA)

# dossie_recurso: o que conta como "recurso nosso". Recurso da parte contrária
# é defesa, não reversão, e entra em bloco separado.
RECURSO_NOSSO = {"representada", "ambos"}

# Ações do catálogo project.task.action usadas aqui.
ACAO_PROTOCOLAR_MINUTA = 1001      # acordo fechado: a minuta foi protocolada
ACAO_ALTERACAO_OBJETO = 1658       # "Solicitar alteração de objeto"
STATE_CONCLUIDO = "d"              # i=Pending, d=Done, c=Cancelled

# Piso abaixo do qual uma taxa é ruído e a página diz isso na cara.
MIN_AMOSTRA = 10

# O programa começou em out/2025. Sentença e caso anteriores existem (processo
# antigo que entrou depois) e não são erro — a página os soma numa linha
# "antes de out/2025" em vez de esticar o eixo por um punhado de registros.
JANELA_INICIO = "2025-10"

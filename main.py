# -*- coding: utf-8 -*-
"""Gera o Painel de Atuação — Escritório externo.

    python main.py --as-of 09/09/2026 --last-full-month 8

Busca no Odoo (somente leitura), monta o JSON, confere os totais contra o próprio
servidor e grava `out/painel-exoffice.html` + `out/dados.json`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from painel import coleta
from painel import config as C
from painel.build import montar_pagina
from painel.odoo import Odoo, OdooError


def parse_args(argv=None):
    hoje = dt.date.today()
    p = argparse.ArgumentParser(description="Painel de Atuação — Escritório externo")
    p.add_argument("--as-of", default=hoje.strftime("%d/%m/%Y"),
                   help="data que aparece na página (dd/mm/aaaa). Padrão: hoje.")
    p.add_argument("--last-full-month", type=int, default=(hoje.month - 1) or 12,
                   help="último mês FECHADO (1-12). O mês seguinte aparece como parcial.")
    p.add_argument("--year", type=int, default=hoje.year, help="ano corrente do painel.")
    p.add_argument("--out", default="out", help="diretório de saída. Padrão: ./out")
    p.add_argument("--env", type=Path, default=None,
                   help="arquivo .env com as credenciais. Padrão: ./.env")
    p.add_argument("--no-check", action="store_true", help="pula a conferência contra o servidor.")
    return p.parse_args(argv)


def conferir(odoo: Odoo, dados: dict) -> list[tuple[bool, str]]:
    """Compara o que o JSON diz com `search_count` feito no próprio servidor.

    Não é decoração: se a soma dos meses não reproduz a contagem do servidor,
    algum grupo se perdeu no caminho e o painel está mentindo.
    """
    checagens = []

    total_painel = sum(sum(v.values()) for v in dados["entradas"]["serie"].values())
    total_servidor = odoo.search_count("dossie.dossie", [("projeto_id", "in", C.IDS_EXOFFICE)])
    checagens.append((total_painel == total_servidor,
                      "casos no recorte: %s no painel · %s no servidor" % (total_painel, total_servidor)))

    enc_painel = sum(sum(v.values()) for v in dados["encerramentos"]["motivo"].values())
    enc_servidor = odoo.search_count("dossie.dossie",
                                     [("projeto_id", "in", C.IDS_EXOFFICE),
                                      ("data_encerramento", "!=", False)])
    checagens.append((enc_painel == enc_servidor,
                      "encerramentos: %s no painel · %s no servidor" % (enc_painel, enc_servidor)))

    sent_painel = sum(sum(v.values()) for v in dados["sentencas"]["serie"].values())
    sent_servidor = odoo.search_count("dossie.dossie",
                                      [("projeto_id", "in", C.IDS_EXOFFICE),
                                       ("data_sentenca", "!=", False)])
    checagens.append((sent_painel == sent_servidor,
                      "sentenças: %s no painel · %s no servidor" % (sent_painel, sent_servidor)))

    # A quebra por projeto e a quebra por mês são duas consultas independentes ao
    # Odoo; é a igualdade entre elas que garante que os projetos particionam o
    # recorte em vez de recontá-lo.
    proj_painel = sum(sum(v.values()) for v in dados["sentencas"]["projeto"].values())
    checagens.append((proj_painel == sent_painel,
                      "sentenças por projeto × por mês: %s · %s" % (proj_painel, sent_painel)))

    ac_painel = sum(dados["acordos"]["serie"].values())
    checagens.append((ac_painel == dados["acordos"]["casos"],
                      "acordos: %s na série · %s casos distintos" % (ac_painel, dados["acordos"]["casos"])))

    rev_painel = sum(sum(v.values()) for v in dados["reversao"]["serie"].values())
    rev_servidor = odoo.search_count("dossie.dossie",
                                     [("projeto_id", "in", C.IDS_EXOFFICE),
                                      ("data_acordao", "!=", False)])
    checagens.append((rev_painel == rev_servidor,
                      "acórdãos: %s no painel · %s no servidor" % (rev_painel, rev_servidor)))
    return checagens


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        cred = C.load_credentials(args.env)
        odoo = Odoo(**cred)
    except (RuntimeError, OdooError) as exc:
        print("erro: %s" % exc, file=sys.stderr)
        return 2

    print("Conectado em %s — %s" % (cred["url"], odoo.whoami()))
    print("Recorte: %d projetos 'Escritório externo'" % len(C.IDS_EXOFFICE))

    casos = coleta.ids_dos_casos(odoo)
    print("  %d casos" % len(casos))

    dados = {
        "as_of": args.as_of,
        "ano": args.year,
        "ultimo_mes_fechado": args.last_full_month,
        "janela_inicio": C.JANELA_INICIO,
        "min_amostra": C.MIN_AMOSTRA,
        "projetos": C.PROJETOS_EXOFFICE,
        "migrados": C.IDS_MIGRADOS,
        "total_casos": len(casos),
        "entradas": coleta.entradas(odoo),
        "encerramentos": coleta.encerramentos(odoo),
        "acordos": coleta.acordos(odoo, casos),
        "sentencas": coleta.sentencas(odoo),
        "reversao": coleta.reversao(odoo),
        "paralelos": coleta.paralelos(odoo, casos),
    }
    # A lista de ids serve só à conferência local; não vai para a página.
    dados["acordos"].pop("ids", None)

    falhou = False
    if not args.no_check:
        print("Conferindo contra o servidor:")
        for ok, texto in conferir(odoo, dados):
            print("  [%s] %s" % ("ok" if ok else "FALHA", texto))
            falhou = falhou or not ok

    destino = Path(args.out)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "dados.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    pagina = destino / "painel-exoffice.html"
    pagina.write_text(montar_pagina(dados), encoding="utf-8")
    print("Gravado: %s" % pagina)

    return 3 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())

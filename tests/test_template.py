# -*- coding: utf-8 -*-
"""Testes do template.

Existe por um motivo concreto: o JS do template só roda no navegador, então um
erro de sintaxe lá passa por toda a pipeline Python sem levantar nada — o script
grava o HTML, imprime "ok" nas seis conferências, e a página abre em branco.
Aconteceu. Estes testes fecham essa porta.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from painel.build import TEMPLATE, montar_pagina

DADOS_MINIMOS = {
    "as_of": "09/09/2026", "ano": 2026, "ultimo_mes_fechado": 8,
    "janela_inicio": "2025-10", "min_amostra": 10,
    "projetos": {"427": "Consignado"}, "migrados": [487], "total_casos": 2,
    "entradas": {"campo": "create_date", "serie": {"2026-01": {"Consignado": 2}}},
    "encerramentos": {"motivo": {"2026-01": {"Acordo": 1}},
                      "projeto": {"2026-01": {"Consignado": 1}}},
    "acordos": {"linhas": 1, "casos": 1, "serie": {"2026-01": 1}},
    "sentencas": {"serie": {"2026-01": {"Improcedente": 1, "Procedente": 1}},
                  "projeto": {"Consignado": {"Improcedente": 1, "Procedente": 1}}},
    "reversao": {"serie": {"2026-01": {"nosso:DF": 1}}},
    "paralelos": {
        "alteracao_objeto": {"estado": {"Concluída": 1}, "serie": {"2026-01": {"Concluída": 1}}},
        "causa_raiz": {"preenchidos": 0, "distribuicao": {"(vazio)": 2}},
        "decisor": {"preenchidos": 0},
        "motivo_vitoria_derrota": {"instrumentado": False},
        "litispendencia": {"instrumentado": False},
    },
}


def _script_do_template() -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    inicio = html.rindex("<script>") + len("<script>")
    return html[inicio:html.rindex("</script>")]


def test_template_tem_o_marcador():
    assert "__DADOS__" in TEMPLATE.read_text(encoding="utf-8")


def test_build_substitui_tudo():
    """A data do cabeçalho não tem marcador próprio: vem no JSON, como o resto."""
    pagina = montar_pagina(DADOS_MINIMOS)
    assert "__DADOS__" not in pagina
    assert "09/09/2026" in pagina


def test_build_escapa_fechamento_de_script():
    """Um `</script>` dentro de um texto do JSON fecharia a tag hospedeira antes
    da hora e cortaria a página no meio."""
    dados = dict(DADOS_MINIMOS)
    dados["projetos"] = {"427": "peça </script> maliciosa"}
    pagina = montar_pagina(dados)
    corpo = pagina[pagina.index('<script id="dados"'):]
    assert corpo.index("</script>") > corpo.index("maliciosa")


def test_json_embutido_volta_a_ser_lido():
    pagina = montar_pagina(DADOS_MINIMOS)
    bruto = re.search(r'<script id="dados" type="application/json">(.*?)</script>',
                      pagina, re.S).group(1)
    assert json.loads(bruto.replace("<\\/", "</"))["total_casos"] == 2


def test_o_template_declara_charset():
    """Servido sem cabeçalho de charset, o navegador chuta latin-1 e a página
    inteira vira mojibake."""
    assert '<meta charset="utf-8">' in TEMPLATE.read_text(encoding="utf-8")[:400]


def test_toda_cor_existe_no_bloco_raiz_puro():
    """Um token definido só dentro de @media/[data-theme] não se aplica no estado
    'sistema', e a página renderiza o texto de um tema sobre o fundo do outro."""
    html = TEMPLATE.read_text(encoding="utf-8")
    raiz = html[html.index(":root{"):html.index("@media (prefers-color-scheme: dark)")]
    declarados = set(re.findall(r"(--[a-z0-9-]+)\s*:", raiz))
    usados = set(re.findall(r"var\((--[a-z0-9-]+)", html))
    assert not (usados - declarados), sorted(usados - declarados)


@pytest.mark.skipif(shutil.which("node") is None, reason="node não está no PATH")
def test_o_javascript_do_template_compila():
    """`node --check` sobre o script inline. É o gate que faltava no dia em que um
    `}` a menos derrubou a página inteira sem nenhum teste reclamar."""
    script = _script_do_template()
    resultado = subprocess.run([shutil.which("node"), "--check", "-"],
                               input=script, capture_output=True, text=True, encoding="utf-8")
    assert resultado.returncode == 0, resultado.stderr

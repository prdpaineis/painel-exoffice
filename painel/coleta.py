# -*- coding: utf-8 -*-
"""As consultas ao Odoo. Uma função por bloco do painel.

Regra da casa: quem soma é o servidor (`read_group`), não trazemos linha a linha.
A única exceção é a lista de ids dos casos do recorte — `project.task.action.line`
não tem `projeto_id`, então filtramos as ações por `dossie_id in [...]`. São 8 mil
ids; filtrar por caminho relacionado (`dossie_id.projeto_id`) estoura o tempo numa
tabela de 16 milhões de linhas.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from . import config as C
from .odoo import Odoo
from .util import nome_de, parse_ano_mes, rotulo_exoffice


def _dominio_recorte() -> list:
    return [("projeto_id", "in", C.IDS_EXOFFICE)]


def _serie_mensal(linhas: list[dict], campo_data: str, chave) -> dict:
    """read_group por `campo:month` + uma dimensão -> {"aaaa-mm": {chave: n}}."""
    saida: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for linha in linhas:
        rotulo = linha.get(campo_data + ":month")
        if not rotulo:
            continue
        ano, mes = parse_ano_mes(rotulo, linha.get("__domain"))
        saida["%04d-%02d" % (ano, mes)][chave(linha)] += linha["__count"]
    return {k: dict(v) for k, v in sorted(saida.items())}


def ids_dos_casos(odoo: Odoo) -> list[int]:
    return odoo.search("dossie.dossie", _dominio_recorte())


def entradas(odoo: Odoo) -> dict[str, Any]:
    """Casos criados por mês e por projeto.

    `data_entrada_cadastro` está vazio em 100% deste recorte (conferido em
    set/2026), então a entrada é o `create_date` — o cadastro no Odoo. Está
    escrito na página para ninguém confundir com data de distribuição.
    """
    linhas = odoo.read_group(
        "dossie.dossie", _dominio_recorte(), ["create_date", "projeto_id"],
        ["create_date:month", "projeto_id"],
    )
    return {
        "campo": "create_date",
        "serie": _serie_mensal(linhas, "create_date",
                               lambda l: rotulo_exoffice(nome_de(l["projeto_id"], "(sem projeto)"))),
    }


def encerramentos(odoo: Odoo) -> dict[str, Any]:
    """Encerramentos por mês, por motivo e por projeto."""
    base = _dominio_recorte() + [("data_encerramento", "!=", False)]
    por_motivo = odoo.read_group(
        "dossie.dossie", base, ["data_encerramento", "motivo_encerramento_id"],
        ["data_encerramento:month", "motivo_encerramento_id"],
    )
    por_projeto = odoo.read_group(
        "dossie.dossie", base, ["data_encerramento", "projeto_id"],
        ["data_encerramento:month", "projeto_id"],
    )
    return {
        "motivo": _serie_mensal(por_motivo, "data_encerramento",
                                lambda l: nome_de(l["motivo_encerramento_id"], "(sem motivo)")),
        "projeto": _serie_mensal(por_projeto, "data_encerramento",
                                 lambda l: rotulo_exoffice(nome_de(l["projeto_id"], "(sem projeto)"))),
    }


def acordos(odoo: Odoo, casos: list[int]) -> dict[str, Any]:
    """Acordo fechado = ação "Protocolar minuta" concluída.

    Contamos **casos distintos**, não linhas de ação: um caso pode ter a ação
    repetida. O mês vem do `create_date` da linha — quando a ação de protocolar
    foi aberta. Não usamos `write_date` (muda a cada edição posterior) nem
    `data_conclusao_acordo` (vazio em todo o recorte).
    """
    dominio = [("dossie_id", "in", casos),
               ("action_id", "=", C.ACAO_PROTOCOLAR_MINUTA),
               ("state", "=", C.STATE_CONCLUIDO)]
    linhas = odoo.search_read("project.task.action.line", dominio,
                              ["dossie_id", "create_date"], limit=5000)
    primeiro_por_caso: dict[int, str] = {}
    for linha in linhas:
        caso = linha["dossie_id"][0]
        quando = (linha["create_date"] or "")[:7]
        if quando and (caso not in primeiro_por_caso or quando < primeiro_por_caso[caso]):
            primeiro_por_caso[caso] = quando
    serie: dict[str, int] = defaultdict(int)
    for quando in primeiro_por_caso.values():
        serie[quando] += 1
    return {
        "linhas": len(linhas),
        "casos": len(primeiro_por_caso),
        "serie": dict(sorted(serie.items())),
        "ids": sorted(primeiro_por_caso),
    }


def sentencas(odoo: Odoo) -> dict[str, Any]:
    """Sentenças por mês, tipo e projeto — a base do êxito."""
    base = _dominio_recorte() + [("data_sentenca", "!=", False)]
    por_tipo = odoo.read_group(
        "dossie.dossie", base, ["data_sentenca", "tipo_sentenca_id"],
        ["data_sentenca:month", "tipo_sentenca_id"],
    )
    por_projeto = odoo.read_group(
        "dossie.dossie", base, ["tipo_sentenca_id", "projeto_id"],
        ["tipo_sentenca_id", "projeto_id"],
    )
    quebra: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for linha in por_projeto:
        projeto = rotulo_exoffice(nome_de(linha["projeto_id"], "(sem projeto)"))
        quebra[projeto][nome_de(linha["tipo_sentenca_id"], "(sem tipo)")] += linha["__count"]
    return {
        "serie": _serie_mensal(por_tipo, "data_sentenca",
                               lambda l: nome_de(l["tipo_sentenca_id"], "(sem tipo)")),
        "projeto": {k: dict(v) for k, v in sorted(quebra.items())},
    }


def _transicao(origem: str, depois: str) -> str:
    """FF manteve favorável · FD reverteu contra · DF reverteu a favor · DD manteve.

    `X` = não classificável (falta a sentença de origem ou o resultado do acórdão).
    Mudança de tipo dentro da mesma classe não é reversão — é o mesmo resultado.
    """
    def classe(nome: str):
        if nome in C.CLASSE_FAVORAVEL:
            return "F"
        if nome in C.CLASSE_DESFAVORAVEL:
            return "D"
        return None

    a, b = classe(origem), classe(depois)
    return (a + b) if a and b else "X"


def reversao(odoo: Odoo) -> dict[str, Any]:
    """Acórdãos classificados pela transição sentença de origem -> resultado.

    Só conta como reversão o caso em que **nós** recorremos (`dossie_recurso` em
    representada/ambos) de uma sentença desfavorável e o acórdão virou o
    resultado. Recurso da parte contrária é defesa e vai em bloco separado; o
    `dossie_recurso` vazio vira uma terceira coluna, nunca some na conta.
    """
    base = _dominio_recorte() + [("data_acordao", "!=", False)]
    linhas = odoo.read_group(
        "dossie.dossie", base,
        ["data_acordao", "tipo_sentenca_id", "tipo_sentenca_modificada_id", "dossie_recurso"],
        ["data_acordao:month", "tipo_sentenca_id", "tipo_sentenca_modificada_id", "dossie_recurso"],
    )
    serie: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for linha in linhas:
        rotulo = linha.get("data_acordao:month")
        if not rotulo:
            continue
        ano, mes = parse_ano_mes(rotulo, linha.get("__domain"))
        quem = linha.get("dossie_recurso")
        prefixo = "nosso" if quem in C.RECURSO_NOSSO else ("vazio" if not quem else "contraria")
        chave = _transicao(nome_de(linha["tipo_sentenca_id"]),
                           nome_de(linha["tipo_sentenca_modificada_id"]))
        serie["%04d-%02d" % (ano, mes)][prefixo + ":" + chave] += linha["__count"]
    return {"serie": {k: dict(v) for k, v in sorted(serie.items())}}


def paralelos(odoo: Odoo, casos: list[int]) -> dict[str, Any]:
    """Os projetos em paralelo dentro do Escritório externo.

    Hoje só "Alteração de objeto" tem dado. `causa_raiz_id`, `subcausa_raiz_id` e
    `decisor` existem como campo em `dossie.dossie` mas estão vazios em todo o
    recorte (conferido em set/2026); "Motivo de vitória e derrota" e
    "Litispendência" ainda não têm campo nenhum no MMP. Medimos os três primeiros
    de verdade e devolvemos zero honesto nos outros — a página diz "ainda não
    instrumentado" em vez de desenhar um gráfico vazio que parece resultado.
    """
    dominio = [("dossie_id", "in", casos), ("action_id", "=", C.ACAO_ALTERACAO_OBJETO)]
    por_estado = odoo.read_group("project.task.action.line", dominio, ["state"], ["state"])
    por_mes = odoo.read_group("project.task.action.line", dominio,
                              ["create_date", "state"], ["create_date:month", "state"])
    rotulo = {"i": "Pendente", "d": "Concluída", "c": "Cancelada"}

    causa = odoo.read_group("dossie.dossie", _dominio_recorte(),
                            ["causa_raiz_id"], ["causa_raiz_id"])
    return {
        "alteracao_objeto": {
            "estado": {rotulo.get(l["state"], l["state"] or "?"): l["__count"] for l in por_estado},
            "serie": _serie_mensal(por_mes, "create_date",
                                   lambda l: rotulo.get(l["state"], l["state"] or "?")),
        },
        "causa_raiz": {
            "preenchidos": odoo.search_count(
                "dossie.dossie", _dominio_recorte() + [("causa_raiz_id", "!=", False)]),
            "distribuicao": {nome_de(l["causa_raiz_id"], "(vazio)"): l["__count"] for l in causa},
        },
        "decisor": {
            "preenchidos": odoo.search_count(
                "dossie.dossie", _dominio_recorte() + [("decisor", "!=", False)]),
        },
        # Sem campo no MMP: a estrutura fica pronta, o número fica honesto.
        "motivo_vitoria_derrota": {"instrumentado": False},
        "litispendencia": {"instrumentado": False},
    }

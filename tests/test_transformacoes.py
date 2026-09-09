# -*- coding: utf-8 -*-
"""Testes das transformações puras. Nenhum toca a rede.

O que interessa aqui é o que já mordeu: o rótulo de mês que vem traduzido, o
nome de projeto que repete cliente e programa, a classificação da transição do
acórdão (onde "mudou de tipo" não é o mesmo que "mudou de classe") e a contagem
de acordo, que é por caso e não por linha de ação.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from painel import coleta
from painel import config as C
from painel.util import parse_ano_mes, rotulo_exoffice


# --------------------------------------------------------------------------
# rótulo de mês
# --------------------------------------------------------------------------

def test_mes_em_ingles():
    assert parse_ano_mes("January 2026") == (2026, 1)
    assert parse_ano_mes("December 2025") == (2025, 12)


def test_mes_em_portugues():
    """O rótulo vem traduzido conforme o idioma do usuário do Odoo. Fixamos
    lang=en_US no contexto, mas quem roda com outro login não pode quebrar."""
    assert parse_ano_mes("março 2026") == (2026, 3)
    assert parse_ano_mes("Setembro 2026") == (2026, 9)


def test_mes_pelo_dominio_quando_o_rotulo_nao_ajuda():
    """Último recurso, e o único independente de idioma: a data que o próprio
    grupo carrega no __domain."""
    dominio = [["data_sentenca", ">=", "2026-07-01"], ["data_sentenca", "<", "2026-08-01"]]
    assert parse_ano_mes("Julho-2026-desconhecido-xyz", dominio) == (2026, 7)


def test_mes_ilegivel_levanta():
    with pytest.raises(ValueError):
        parse_ano_mes("mês que não existe", [])


# --------------------------------------------------------------------------
# nome curto do projeto
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bruto,esperado", [
    ("Santander - Consignado - Escritório externo", "Consignado"),
    ("Santander - Revisionais - Escritório externo", "Revisionais"),
    ("Santander - Cessão de Crédito - Escritório externo", "Cessão de Crédito"),
    ("Santander - Cautelar - Exibição - Escritório externo", "Cautelar - Exibição"),
    ("Santander - Escritório externo migrados - Consignado", "Consignado (migrados)"),
    ("Santander - Escritório externo migrados - Revisionais", "Revisionais (migrados)"),
    # "Indenizatória - Indenizatórias" é a mesma coisa dita duas vezes.
    ("Santander - Indenizatória - Indenizatórias - Escritório externo", "Indenizatórias"),
])
def test_rotulo_exoffice(bruto, esperado):
    assert rotulo_exoffice(bruto) == esperado


def test_rotulo_de_nome_inesperado_nao_some():
    """Projeto novo, fora do padrão, tem que aparecer inteiro em vez de virar
    string vazia — sumir de silêncio é pior que ficar feio."""
    assert rotulo_exoffice("Outro Cliente - Coisa Nova") == "Outro Cliente - Coisa Nova"


def test_migrado_e_reconhecivel_no_painel():
    """A página separa carga de migração de demanda procurando '(migrados)'."""
    assert "(migrados)" in rotulo_exoffice("Santander - Escritório externo migrados - Consignado")
    assert "(migrados)" not in rotulo_exoffice("Santander - Consignado - Escritório externo")


# --------------------------------------------------------------------------
# transição do acórdão
# --------------------------------------------------------------------------

def test_transicao_reverteu_a_favor():
    assert coleta._transicao("Procedente", "Improcedente") == "DF"


def test_transicao_manteve_a_derrota():
    assert coleta._transicao("Procedente", "Parcialmente Procedente") == "DD"


def test_transicao_manteve_o_exito():
    assert coleta._transicao("Improcedente", "Extinção sem Julgamento do Mérito") == "FF"


def test_transicao_perdeu_no_acordao():
    assert coleta._transicao("Improcedente", "Procedente") == "FD"


def test_mudar_de_tipo_dentro_da_classe_nao_e_reversao():
    """"Parcial -> Procedente" é como o MMP registra condenação mantida. Contar
    isso como reversão inflaria a taxa com o mesmo resultado dito de outro jeito."""
    assert coleta._transicao("Parcialmente Procedente", "Procedente") == "DD"
    assert coleta._transicao("Improcedente", "Extinção da Execução") == "FF"


def test_sem_classificacao_vira_X():
    assert coleta._transicao("", "Improcedente") == "X"
    assert coleta._transicao("Procedente", "") == "X"
    assert coleta._transicao("Homologação de Acordo", "Improcedente") == "X"


# --------------------------------------------------------------------------
# série mensal
# --------------------------------------------------------------------------

def test_serie_mensal_agrega_e_ordena():
    linhas = [
        {"data_sentenca:month": "March 2026", "tipo": "a", "__count": 3},
        {"data_sentenca:month": "January 2026", "tipo": "a", "__count": 1},
        {"data_sentenca:month": "March 2026", "tipo": "b", "__count": 2},
        {"data_sentenca:month": "March 2026", "tipo": "a", "__count": 4},
    ]
    saida = coleta._serie_mensal(linhas, "data_sentenca", lambda l: l["tipo"])
    assert list(saida) == ["2026-01", "2026-03"]          # ordenado
    assert saida["2026-03"] == {"a": 7, "b": 2}           # mesma chave soma


def test_serie_mensal_ignora_grupo_sem_data():
    """read_group devolve um grupo com data nula quando o campo está vazio; ele
    não tem mês para cair, e somá-lo em qualquer mês seria inventar."""
    linhas = [
        {"data_sentenca:month": False, "tipo": "a", "__count": 9},
        {"data_sentenca:month": "May 2026", "tipo": "a", "__count": 1},
    ]
    saida = coleta._serie_mensal(linhas, "data_sentenca", lambda l: l["tipo"])
    assert saida == {"2026-05": {"a": 1}}


# --------------------------------------------------------------------------
# acordo: conta por caso, não por linha de ação
# --------------------------------------------------------------------------

class OdooFalso:
    """Só o suficiente para `coleta.acordos`. Registra o domínio recebido para
    que o teste possa conferir o filtro, além do resultado."""

    def __init__(self, linhas):
        self._linhas = linhas
        self.dominio = None

    def search_read(self, model, domain, fields, limit=5000):
        self.dominio = list(domain)
        return self._linhas


def test_acordo_conta_caso_distinto_e_pega_o_primeiro_mes():
    """A mesma ação aparece repetida em alguns casos: 3 linhas, 2 casos. E o
    caso 10, protocolado duas vezes, entra no mês mais antigo."""
    odoo = OdooFalso([
        {"dossie_id": [10, "x"], "create_date": "2026-03-04 10:00:00"},
        {"dossie_id": [10, "x"], "create_date": "2026-01-20 09:00:00"},
        {"dossie_id": [11, "y"], "create_date": "2026-03-15 11:00:00"},
    ])
    saida = coleta.acordos(odoo, [10, 11])
    assert saida["linhas"] == 3
    assert saida["casos"] == 2
    assert saida["serie"] == {"2026-01": 1, "2026-03": 1}
    assert sum(saida["serie"].values()) == saida["casos"]   # a invariante do gate


def test_acordo_filtra_pela_acao_e_pelo_estado_concluido():
    odoo = OdooFalso([])
    coleta.acordos(odoo, [1, 2])
    assert ("action_id", "=", C.ACAO_PROTOCOLAR_MINUTA) in odoo.dominio
    assert ("state", "=", C.STATE_CONCLUIDO) in odoo.dominio
    assert ("dossie_id", "in", [1, 2]) in odoo.dominio


def test_acordo_ignora_linha_sem_data():
    odoo = OdooFalso([
        {"dossie_id": [10, "x"], "create_date": False},
        {"dossie_id": [11, "y"], "create_date": "2026-05-02 08:00:00"},
    ])
    saida = coleta.acordos(odoo, [10, 11])
    assert saida["casos"] == 1
    assert saida["serie"] == {"2026-05": 1}


# --------------------------------------------------------------------------
# o recorte
# --------------------------------------------------------------------------

def test_recorte_tem_os_onze_projetos_e_nenhum_repetido():
    assert len(C.IDS_EXOFFICE) == 11
    assert len(set(C.IDS_EXOFFICE)) == 11
    assert C.IDS_EXOFFICE == sorted(C.PROJETOS_EXOFFICE)


def test_migrados_sao_subconjunto_do_recorte():
    assert set(C.IDS_MIGRADOS) <= set(C.IDS_EXOFFICE)


def test_classes_de_sentenca_nao_se_sobrepoem():
    """Um tipo em ambas as classes faria a matriz de transição contar duas vezes."""
    assert not (C.CLASSE_FAVORAVEL & C.CLASSE_DESFAVORAVEL)


def test_recurso_nosso_exclui_a_parte_contraria():
    """Recurso da parte contrária é defesa, não reversão."""
    assert "contraria" not in C.RECURSO_NOSSO
    assert C.RECURSO_NOSSO == {"representada", "ambos"}

# Painel de Atuação — Escritório externo

Gera a página HTML do painel do programa **Escritório externo** (Santander) a partir do
Odoo do MMP, via XML-RPC, **somente leitura**. Cinco abas: Entradas, Encerramentos e
acordo, Êxito, Reversão recursal e Projetos paralelos.

Irmão do painel `painel-mmp` ("Êxito e Reversão"): usa as mesmas definições de êxito e de
reversão, de propósito, para os dois conversarem. O que muda é o recorte — aqui é um
programa só, e o eixo é sempre o mês.

> **Use repositório privado.** Não há credencial nenhuma neste repositório — mas o
> template carrega os textos, as definições e a estrutura de atuação do escritório, e o
> README traz volumes reais do cliente. Isso não é material para repositório público.

## Requisitos

* Python 3.8+ — **sem dependências de runtime** (só a biblioteca padrão).
* Rede até o servidor Odoo.
* Um usuário do Odoo com leitura em `dossie.dossie` e `project.task.action.line`.

## Configuração

```bash
cp .env.example .env      # preencha ODOO_URL, ODOO_DB, ODOO_LOGIN, ODOO_PASSWORD
```

O `.env` está no `.gitignore`. Em CI, use os *secrets* do repositório — variáveis de
ambiente têm precedência sobre o arquivo.

O script **só olha o caminho que você pedir**: `./.env` por padrão, ou o que vier em
`--env`. Ele não sai procurando arquivo de credencial pelo disco, então um clone em outra
máquina nunca pega um `.env` alheio por acidente.

```bash
python main.py --env ../odoo-mmp.env     # credencial fora da árvore do repositório
```

Prefira um **usuário de integração só-leitura** em vez da conta de uma pessoa: o MMP tem
regras de visibilidade por empresa, e os números mudam se o login mudar.

### O que nunca entra no repositório

| | Por quê |
|---|---|
| `.env`, `*.env` (menos `.env.example`) | credencial |
| `out/` | a página e o `dados.json` trazem volumes reais do cliente |

O workflow `segredos` no CI falha o build se um `.env` for versionado à força ou se
aparecer `ODOO_PASSWORD` com valor literal no código. É rede de segurança rasa — quem
protege de verdade é o `.gitignore`.

## Uso

```bash
python main.py --as-of 09/09/2026 --last-full-month 8
```

| Opção | Para que serve |
|---|---|
| `--as-of` | data que aparece na página (`dd/mm/aaaa`). Padrão: hoje. |
| `--last-full-month` | último mês **fechado** (1–12). O mês seguinte aparece marcado como parcial. Padrão: mês anterior ao de hoje. |
| `--year` | ano corrente do painel. Padrão: ano de hoje. |
| `--out` | diretório de saída. Padrão: `./out`. |
| `--env` | arquivo com as credenciais. Padrão: `./.env`. |
| `--no-check` | pula a conferência contra o servidor (não recomendado). |

Saída em `out/`: `painel-exoffice.html` (a página) e `dados.json` (os dados, úteis para
diff entre execuções).

**Ao virar o mês, suba o `--last-full-month`.** É a única coisa que muda de rotina.

### Conferência automática

Antes de gravar, o script compara os totais do JSON com `search_count` feito no próprio
servidor:

```
Conferindo contra o servidor:
  [ok] casos no recorte: 8467 no painel · 8467 no servidor
  [ok] encerramentos: 1332 no painel · 1332 no servidor
  [ok] sentenças: 2437 no painel · 2437 no servidor
  [ok] sentenças por projeto × por mês: 2437 · 2437
  [ok] acordos: 50 na série · 50 casos distintos
  [ok] acórdãos: 278 no painel · 278 no servidor
```

A quarta linha não vai ao servidor: confere a quebra por projeto contra a quebra por mês
dentro do próprio JSON. São duas consultas independentes, e é essa igualdade que garante
que os projetos **particionam** o recorte em vez de recontá-lo.

Se algum total divergir, a saída ainda é gravada mas o processo termina com código **3** —
dá para usar como gate no CI.

## O recorte

"Escritório externo" não é um projeto: é uma família de **11 registros** em
`project.project` (`painel/config.py` → `PROJETOS_EXOFFICE`). Seis têm caso hoje; os outros
cinco estão na lista de propósito, para que um caso novo caia no painel sem mexer no
código. Os cinco projetos "migrados" estão marcados em `IDS_MIGRADOS`.

O programa começou em **out/2025**. Existem casos e sentenças anteriores — processos
antigos que entraram depois. Não são erro: entram no total e ficam fora do eixo, somados
numa nota ao pé de cada tabela, porque esticar o gráfico até 2015 por causa de uma
sentença deixaria o resto ilegível (`JANELA_INICIO`).

Duas ressalvas de leitura que valem para **todas** as quebras por projeto:

* **O projeto é o de hoje, não o da entrada.** Agrupamos `create_date` × `projeto_id`
  atual. Reclassificar um caso reescreve o passado do gráfico — ele troca de faixa
  retroativamente. Se um mês mudar de composição sem explicação (ago/26: Consignado cai de
  852 para 108 enquanto Indenizatórias sobe de 29 para 677), suspeite de reclassificação
  antes de suspeitar de mudança na demanda.
* **Migração não é demanda.** 718 dos 8.467 casos vieram dos projetos *migrados*, 699 deles
  em jan/26. Aquele mês tem 1.100 "entradas", das quais quase dois terços são carga de
  carteira. A página marca isso; a média móvel dos três últimos meses não pega o pico, mas
  qualquer comparação com janeiro pega.

## O que cada aba mede

**Entradas.** Casos criados, por mês e por projeto do caso. O campo é o `create_date` —
`data_entrada_cadastro` está **vazio em 100% deste recorte** (conferido em set/2026), e a
página diz isso, para ninguém ler como data de distribuição.

**Encerramentos e acordo.** Casos com `data_encerramento`, quebrados por
`motivo_encerramento_id` e por projeto. O acordo é medido **à parte**: conta a ação
`Protocolar minuta` (id 1001) com `state = 'd'`, **uma vez por caso** — a mesma ação
aparece repetida em alguns casos. As duas contas ficam lado a lado na página de propósito:
50 casos pela minuta e 54 pelo motivo de encerramento, e a diferença é trabalho a
conferir antes de fechar o mês, não erro do painel.

> **A minuta não serve para o eixo do tempo.** `data_conclusao_acordo` está vazio em todo o
> recorte e o `write_date` da linha muda a cada edição posterior, então o único carimbo
> disponível é o `create_date` — a **abertura** do protocolo, não a conclusão. Há linhas
> abertas em janeiro e escritas em junho. Por isso o gráfico mensal usa
> `data_encerramento` + motivo *Acordo*, que tem data do fato, e a coluna da minuta fica na
> tabela só para conferência. **O total pela minuta é sólido; a distribuição mensal dele
> não é.**

**Êxito.** Êxito = `Improcedente` + `Extinção` (sem mérito ou da execução), sobre as
sentenças com tipo informado. Homologação de acordo entra no denominador — é um desfecho.
"Sem tipo" fica de fora e aparece em coluna própria. Mês pelo `data_sentenca`.

> **A taxa fechada esconde o que importa neste recorte.** Os 80,4% de êxito são
> **34,0% de mérito** (improcedente: o pedido foi julgado e rejeitado) e **46,4%
> processual** (extinção sem mérito: o pedido não chegou a ser julgado, e parte volta como
> ação nova, mesma parte e mesmo pedido). A parcela processual é **maior** que a de mérito,
> o que não acontece no painel geral. Por isso toda tabela desta aba abre as duas parcelas,
> e a página traz um aviso sempre que a processual supera a de mérito.

A definição fechada é a mesma do `painel-mmp` de propósito, para os dois conversarem — a
abertura é adicional, não a substitui.

O campo `exito_encerramento` do MMP existe, mas está **vazio nos 8.467 casos**; por isso o
painel usa a definição por sentença, que é a mesma do painel `painel-mmp`.

A quebra por projeto traz o intervalo de Wilson a 95% e marca *amostra pequena* abaixo de
`MIN_AMOSTRA` sentenças: com 3 ou 4 casos a faixa passa de 40 pontos percentuais, e ali
não há conclusão possível, só ruído.

**Reversão recursal.** Dos casos em que **nós** recorremos de uma sentença desfavorável, a
fração em que o acórdão mudou o resultado a nosso favor. Cada acórdão é classificado pela
transição entre a classe da sentença original e a do resultado depois do acórdão:

| | favorável | desfavorável |
|---|---|---|
| **favorável** | `FF` manteve | `FD` reverteu contra |
| **desfavorável** | `DF` **reverteu a favor** | `DD` manteve |

`favorável` = Improcedente, Extinção, Favorável · `desfavorável` = Procedente,
Parcialmente Procedente, Desfavorável. Mudança de tipo dentro da mesma classe **não** é
reversão.

Recurso da parte contrária é defesa, não reversão: sai da taxa e aparece em bloco próprio,
junto com os acórdãos sem `dossie_recurso` preenchido — que hoje são **59 de 278**. É a
maior fragilidade do indicador neste recorte, e está escrito na página.

O denominador é pequeno: dos 278 acórdãos, apenas **50** têm recurso nosso partindo de
sentença desfavorável, e a reversão hoje é 12 desses 50. A página mostra a taxa **sempre
com o intervalo de Wilson ao lado**, porque nesse volume a faixa é larga demais para
sustentar meta ou comparação entre meses.

**Projetos paralelos.** Cinco projetos dentro do programa. Um tem dado; quatro não têm, e a
página diz exatamente o quê falta em cada um em vez de desenhar um gráfico vazio que
parece resultado:

| Projeto | Onde mora | Situação em set/2026 |
|---|---|---|
| Alteração de objeto e assunto | ação `Solicitar alteração de objeto` (id 1658) | **medindo** — 1.484 solicitações, e o que importa é o desfecho: 71% canceladas, concentradas em mai/26 e jul/26 (parece lote reprocessado, não decisão caso a caso) |
| Análise de causa raiz | `causa_raiz_id` / `subcausa_raiz_id` | campo existe (Sistêmico / Formalização / Procedimento), zerado no recorte |
| Decisor | `decisor` (texto livre) | campo existe, zerado. Texto livre não agrupa — vale virar lista antes de medir |
| Motivo de vitória e derrota | — | existe o modelo `motivos.perda` (5 motivos), mas **nenhum campo do caso aponta para ele** |
| Litispendência | — | o mais próximo é o motivo de encerramento *Extinto por perempção, litispendência ou coisa julgada*, que junta três coisas |

Os quatro já estão ligados ao painel. Quando o campo começar a ser preenchido, a seção
acende na geração seguinte, sem mexer no código.

## Como o template funciona

`templates/painel.html` é a página completa (HTML + CSS + JS, sem dependência externa além
das fontes do Google) com **um** marcador que o build substitui: `__DADOS__`, que vira o
JSON inteiro dentro de `<script id="dados">`. Tudo que a página mostra — inclusive a data
do cabeçalho — sai desse JSON, e não de outro marcador.

Para mexer no visual, edite o template — os módulos Python não geram HTML.

As cores dos gráficos entram por `style="fill:var(--…)"` e não por atributo, para que a
troca de tema no CSS repinte o SVG sem redesenhar nada.

## Armadilhas do Odoo 10 (já custaram tempo)

* `execute_kw(db, uid, pw, model, method, args, kwargs)` — em `search`/`read_group` o
  `args[0]` é o domínio **sem envelope extra**; em `read` é a lista de ids crua. Errar isso
  devolve traceback de Python 2 apontando para módulos customizados, não "domínio inválido".
* Todo campo usado em `groupby` precisa aparecer **também** em `fields`, inclusive o campo
  de data que leva o sufixo `:month`.
* `limit=0` significa *sem limite* neste servidor. Nunca passe zero em tabela grande.
* `project.task.action.line` tem **1.219 colunas**. Nunca faça `search_read` nela sem
  `fields=[...]`.
* Ela também **não tem `projeto_id`**: para filtrar as ações do recorte, passamos a lista
  de ids dos casos. Filtrar por caminho relacionado (`dossie_id.projeto_id`) estoura o
  tempo numa tabela de 16 milhões de linhas.
* Registros arquivados só aparecem com `active_test: False` no contexto — o painel os
  inclui (caso encerrado é caso).
* O rótulo de `:month` vem traduzido conforme o idioma do usuário. Fixamos `lang: en_US` no
  contexto e há fallback que lê a data do `__domain` do grupo.

## Testes

```bash
pip install -r requirements-dev.txt
pytest -q
```

Cobrem as transformações puras — nada toca a rede: leitura do mês em inglês, em português e
pelo `__domain`; o encurtamento do nome de projeto (inclusive o `(migrados)`, de que a
página depende para separar carga de demanda); a classificação da transição do acórdão, com
o caso em que mudar de tipo **dentro** da mesma classe não é reversão; e a contagem de
acordo por caso distinto, com a invariante de que a soma da série mensal reproduz o total.

Dois testes existem por causa de erro que já aconteceu:

* **`node --check` sobre o JS do template.** O script inline só roda no navegador, então um
  `}` a menos atravessa a pipeline inteira sem levantar nada: o build grava o HTML, imprime
  "ok" nas seis conferências, e a página abre em branco. O teste é pulado se `node` não
  estiver no PATH; **no CI ele é obrigatório**, e o job falha se for pulado.
* **Todo token de cor declarado no `:root` puro.** Uma cor definida só dentro de
  `@media (prefers-color-scheme: dark)` não se aplica no estado "sistema", e a página
  renderiza o texto de um tema sobre o fundo do outro.

## Estrutura

```
main.py                       CLI: busca → monta → confere → grava
painel/config.py              credenciais (env) e o recorte (ids, classes, ações)
painel/odoo.py                cliente XML-RPC só-leitura
painel/coleta.py              uma função por bloco do painel
painel/build.py               injeta o JSON no template
painel/util.py                parsing de mês, nomes curtos de projeto, helpers
templates/painel.html         a página (edite aqui para mudar o visual)
tests/                        transformações puras + gates do template
.github/workflows/testes.yml  pytest em 3.9 e 3.12, gate do JS, varredura de segredo
```

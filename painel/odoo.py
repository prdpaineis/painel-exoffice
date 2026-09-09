# -*- coding: utf-8 -*-
"""Cliente XML-RPC mínimo e somente-leitura para o Odoo do MMP.

Duas armadilhas do Odoo 10 que já custaram tempo e estão embutidas aqui:

* `execute_kw(db, uid, pw, model, method, args, kwargs)` — para `search`/`read_group`
  o `args[0]` é o domínio **sem envelope extra**; para `read` é a lista de ids crua.
  Errar isso devolve um traceback de Python 2 apontando para módulos customizados,
  não uma mensagem de "domínio inválido".
* `limit=0` significa *sem limite* neste servidor. Nunca passe zero em tabela grande.
"""
from __future__ import annotations

import xmlrpc.client
from typing import Any, Iterable, Sequence

# Rótulos de mês em inglês nos agrupamentos `:month` (o parser não fica refém do
# idioma de quem roda) e registros arquivados incluídos — caso encerrado é caso.
BASE_CONTEXT = {"lang": "en_US", "active_test": False}


class OdooError(RuntimeError):
    pass


class Odoo:
    def __init__(self, url: str, db: str, login: str, password: str) -> None:
        self._db, self._pw = db, password
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
        self._models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
        try:
            self.version = common.version().get("server_version", "?")
            uid = common.authenticate(db, login, password, {})
        except Exception as exc:
            raise OdooError(f"Não foi possível falar com {url}: {exc}") from exc
        if not uid:
            raise OdooError("Autenticação recusada (uid vazio). Confira ODOO_DB, ODOO_LOGIN e ODOO_PASSWORD.")
        self.uid: int = uid

    def _call(self, model: str, method: str, args: Sequence[Any], **kw: Any) -> Any:
        kw.setdefault("context", dict(BASE_CONTEXT))
        try:
            return self._models.execute_kw(self._db, self.uid, self._pw, model, method, list(args), kw)
        except xmlrpc.client.Fault as fault:
            raise OdooError(f"{model}.{method} falhou: {fault.faultString.strip()[-400:]}") from fault

    def search_count(self, model: str, domain: Iterable[Any]) -> int:
        return self._call(model, "search_count", [list(domain)])

    def search(self, model: str, domain: Iterable[Any], limit: int = 20000) -> list[int]:
        return self._call(model, "search", [list(domain)], limit=limit)

    def read(self, model: str, ids: Sequence[int], fields: Sequence[str]) -> list[dict]:
        return self._call(model, "read", [list(ids)], fields=list(fields))

    def search_read(self, model: str, domain: Iterable[Any], fields: Sequence[str],
                    limit: int = 5000) -> list[dict]:
        """Sempre com `fields` explícito: `project.task.action.line` tem 1.219
        colunas, e sem a lista o servidor devolve todas elas por linha."""
        return self._call(model, "search_read", [list(domain)], fields=list(fields), limit=limit)

    def read_group(self, model: str, domain: Iterable[Any], fields: Sequence[str],
                   groupby: Sequence[str]) -> list[dict]:
        """Em Odoo 10 todo campo do `groupby` precisa aparecer também em `fields`,
        inclusive o de data que recebe o sufixo `:month`."""
        return self._call(model, "read_group", [list(domain), list(fields), list(groupby)], lazy=False)

    def whoami(self) -> str:
        rec = self.read("res.users", [self.uid], ["name", "login"])[0]
        return f"{rec['name']} ({rec['login']}, uid {self.uid})"

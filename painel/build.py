# -*- coding: utf-8 -*-
"""Injeta o JSON no template. Os módulos Python não geram HTML — para mexer no
visual, edite `templates/painel.html`."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "painel.html"


def montar_pagina(dados: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    # `</script>` dentro do JSON fecharia a tag hospedeira antes da hora.
    payload = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return html.replace("__DADOS__", payload)

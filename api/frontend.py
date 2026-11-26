"""Entrega o frontend React já compilado (frontend/dist) em /.

O React cuida das próprias rotas (/alvos, /mudancas...): qualquer endereço que não seja arquivo nem
API recebe o index.html, para que recarregar a página ou abrir um link direto funcione.
Sem o build, / mostra como gerá-lo em vez de um 404 sem explicação.
"""

from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException
from starlette.routing import get_route_path
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

SEM_BUILD = """<!doctype html>
<html lang="pt-BR"><meta charset="utf-8"><title>Monitor de Normas</title>
<body style="font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem;line-height:1.5">
<h1>Monitor de Normas</h1>
<p>O servidor está no ar, mas as telas ainda não foram compiladas.</p>
<p>Na pasta do projeto, rode <code>./setup.sh</code> (ou <code>cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</code>)
e reinicie o servidor.</p>
<p>A API continua disponível em <a href="/docs">/docs</a>.</p>
</body></html>"""


class AplicacaoReact(StaticFiles):
    """StaticFiles que devolve o index.html para as rotas do React."""

    async def get_response(self, path: str, scope: Scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as erro:
            rota = get_route_path(scope)
            eh_arquivo = "." in PurePosixPath(rota).name  # /assets/x.js que não existe continua 404
            if erro.status_code != 404 or rota.startswith("/api/") or eh_arquivo:
                raise
            return await super().get_response("index.html", scope)


def montar_frontend(app: FastAPI, pasta: Path) -> None:
    """Chamar depois de registrar as rotas da API, que têm prioridade."""
    if (pasta / "index.html").is_file():
        app.mount("/", AplicacaoReact(directory=pasta, html=True), name="frontend")
        return

    @app.get("/{caminho:path}", include_in_schema=False)
    def sem_build(caminho: str):
        if caminho.startswith("api/"):
            raise HTTPException(404)
        return HTMLResponse(SEM_BUILD, status_code=503)

"""Senha de acesso (HTTP Basic), ligada quando MONITOR_NORMAS_SENHA está definida.

Sem a variável, nada é exigido (uso local em 127.0.0.1). No servidor, a senha protege as telas e a
API inteira; só a rota de saúde fica aberta, para o monitoramento. Use sempre atrás de HTTPS.
"""

import base64
import binascii
import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

VARIAVEL_USUARIO = "MONITOR_NORMAS_USUARIO"
VARIAVEL_SENHA = "MONITOR_NORMAS_SENHA"
USUARIO_PADRAO = "admin"


def credenciais_do_ambiente() -> tuple[str, str] | None:
    senha = os.environ.get(VARIAVEL_SENHA)
    if not senha:
        return None
    return os.environ.get(VARIAVEL_USUARIO) or USUARIO_PADRAO, senha


def confere(cabecalho: str | None, usuario: str, senha: str) -> bool:
    esquema, _, valor = (cabecalho or "").partition(" ")
    if esquema.lower() != "basic":
        return False
    try:
        recebido_usuario, _, recebida_senha = base64.b64decode(valor, validate=True).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    # As duas comparações sempre rodam, para o tempo de resposta não revelar qual errou.
    usuario_ok = secrets.compare_digest(recebido_usuario.encode("utf-8"), usuario.encode("utf-8"))
    senha_ok = secrets.compare_digest(recebida_senha.encode("utf-8"), senha.encode("utf-8"))
    return usuario_ok and senha_ok


def exigir_senha(app: FastAPI, usuario: str, senha: str, livres: set[str]) -> None:
    @app.middleware("http")
    async def autenticar(request: Request, chamar_proximo):
        if request.url.path in livres or confere(request.headers.get("authorization"), usuario, senha):
            return await chamar_proximo(request)
        return JSONResponse(status_code=401, content={"detail": "usuário ou senha inválidos"},
                            headers={"WWW-Authenticate": 'Basic realm="Monitor de Normas", charset="UTF-8"'})

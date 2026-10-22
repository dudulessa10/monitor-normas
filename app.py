"""Ponto de entrada do servidor web: uvicorn app:app --reload"""

from api.main import criar_app

app = criar_app()

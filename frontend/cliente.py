"""Cliente independente: o único contato com o back-end é HTTP."""

import os
import requests


def requisitar(metodo: str, rota: str, dados: dict | None = None):
    try:
        resposta = requests.request(metodo, os.getenv("API_URL", "http://127.0.0.1:8000") + rota,
                                    json=dados, timeout=(5, 2700))
        if not resposta.ok:
            try:
                detalhe = resposta.json().get("detail", "Erro na API.")
            except ValueError:
                detalhe = "A API retornou uma resposta inválida."
            raise RuntimeError(str(detalhe))
        return resposta.json()
    except requests.Timeout as erro:
        raise RuntimeError("A API excedeu o tempo limite. Aguarde a etapa terminar e atualize a página.") from erro
    except requests.RequestException as erro:
        raise RuntimeError("Não foi possível acessar a API. Inicie o back-end na porta configurada em API_URL.") from erro

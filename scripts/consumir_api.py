"""Exemplo de consumo independente com requests. Execute com a API iniciada."""

import json
import os

import requests

BASE = os.getenv("API_URL", "http://127.0.0.1:8000")


def chamar(metodo, rota, dados=None):
    resposta = requests.request(metodo, BASE + rota, json=dados, timeout=2700)
    resposta.raise_for_status()
    return resposta.json()


if __name__ == "__main__":
    chamar("POST", "/documentos/processar", {"tamanho": 120, "sobreposicao": 20})
    chamar("POST", "/personas", {"personas": []})
    chamar("POST", "/dataset/gerar", {"quantidade": 3})
    chamar("POST", "/rag/executar", {"top_k": 3})
    chamar("POST", "/avaliacao/executar")
    print(json.dumps(chamar("GET", "/dataset"), ensure_ascii=False, indent=2))

import json
import pytest
import requests
from pydantic import ValidationError

from backend.llm import Julgamento, PerguntaGerada, solicitar


def test_chave_ausente_e_metrica_invalida(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        solicitar("Gere uma pergunta", {}, PerguntaGerada)
    with pytest.raises(ValidationError):
        Julgamento.model_validate({m: {"nota": 1.5, "justificativa": "Inválida"}
                                  for m in ["faithfulness", "answer_relevancy", "context_utilization"]})


def test_cliente_envia_contextos_e_valida_json(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "chave-ficticia-de-teste")
    def post(url, **kwargs):
        assert url.endswith("/chat/completions")
        assert json.loads(kwargs["json"]["messages"][1]["content"])["fonte"] == "Conteúdo real"
        class Resposta:
            def raise_for_status(self):
                pass
            def json(self):
                return {"choices": [{"message": {"content": '{"pergunta": "Como funciona a biblioteca?"}'}}]}
        return Resposta()
    monkeypatch.setattr(requests, "post", post)
    assert solicitar("Gere", {"fonte": "Conteúdo real"}, PerguntaGerada)["pergunta"].endswith("?")


def test_timeout_nao_expoe_chave(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "chave-ficticia-de-teste")
    def falhar(*args, **kwargs):
        raise requests.Timeout("detalhes internos")
    monkeypatch.setattr(requests, "post", falhar)
    with pytest.raises(ValueError, match="tempo limite"):
        solicitar("Gere", {}, PerguntaGerada)

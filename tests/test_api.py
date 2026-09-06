import pytest
from fastapi.testclient import TestClient

from backend import llm
from backend.main import criar_app


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    pasta = tmp_path / "documentos"
    pasta.mkdir()
    (pasta / "biblioteca.txt").write_text("A biblioteca empresta três livros por quatorze dias. " * 30, encoding="utf-8")
    contador = iter(range(100))
    monkeypatch.setattr(llm, "gerar_pergunta", lambda *args: f"Qual é o prazo dos livros da biblioteca? Variação {next(contador)}")
    monkeypatch.setattr(llm, "responder", lambda pergunta, contextos: "O prazo é quatorze dias.")
    monkeypatch.setattr(llm, "avaliar", lambda *args: {
        m: {"nota": 0.75, "justificativa": "Justificativa simulada exclusivamente para teste."}
        for m in ["faithfulness", "answer_relevancy", "context_utilization"]})
    return TestClient(criar_app(pasta, tmp_path / "estado.json"))


def preparar(cliente):
    assert cliente.post("/documentos/processar", json={}).status_code == 200
    assert cliente.post("/dataset/gerar", json={"quantidade": 2}).status_code == 200


def test_fluxo_completo_preserva_contextos_metricas_e_persona(cliente):
    assert cliente.post("/personas", json={"personas": ["Estudante"]}).status_code == 200
    preparar(cliente)
    assert cliente.post("/rag/executar", json={}).status_code == 200
    assert cliente.post("/avaliacao/executar").status_code == 200
    item = cliente.get("/dataset").json()["dataset"][0]
    assert item["contextos"] and item["resposta"] and item["metricas"]
    assert item["persona"] == "Estudante"
    assert item["fonte"]["chunk_id"]
    assert cliente.get("/avaliacao/resultados").json()["medias"]["faithfulness"] == 0.75
    documento = cliente.get("/documentos").json()["documentos"][0]
    assert cliente.get(f"/documentos/{documento['id']}/chunks").json()["quantidade"] > 0


def test_ordem_das_etapas_e_validacao(cliente):
    assert cliente.post("/dataset/gerar", json={}).status_code == 400
    assert cliente.post("/rag/executar", json={}).status_code == 400
    assert cliente.post("/avaliacao/executar").status_code == 400
    assert cliente.post("/documentos/processar", json={"tamanho": 30, "sobreposicao": 30}).status_code == 422
    assert cliente.post("/dataset/gerar", json={"quantidade": 0}).status_code == 422
    assert cliente.post("/personas", json={"personas": [" "]}).status_code == 422
    assert cliente.get("/documentos/inexistente/chunks").status_code == 404


def test_falha_na_llm_preserva_dataset_anterior(cliente, monkeypatch):
    preparar(cliente)
    anterior = cliente.get("/dataset").json()
    def falhar(*args):
        raise ValueError("Falha simulada no provedor")
    monkeypatch.setattr(llm, "gerar_pergunta", falhar)
    assert cliente.post("/dataset/gerar", json={}).status_code == 400
    assert cliente.get("/dataset").json() == anterior


def test_reexecucao_invalida_metricas_e_reprocessamento_limpa_dataset(cliente):
    preparar(cliente)
    cliente.post("/rag/executar", json={})
    cliente.post("/avaliacao/executar")
    cliente.post("/rag/executar", json={})
    assert cliente.get("/avaliacao/resultados").json()["quantidade"] == 0
    cliente.post("/documentos/processar", json={})
    assert cliente.get("/dataset").json()["dataset"] == []

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_interface_sem_chave_carrega_e_desabilita_geracao(monkeypatch):
    pasta = Path(__file__).resolve().parents[1] / "frontend"
    monkeypatch.syspath_prepend(str(pasta))
    import cliente
    respostas = {
        "/saude": {"llm_configurada": False, "modelo": "modelo de teste", "modelo_juiz": "juiz de teste"},
        "/documentos": {"documentos": [], "total_documentos": 0, "total_chunks": 0},
        "/dataset": {"dataset": [], "personas": []},
        "/avaliacao/resultados": {"quantidade": 0, "medias": {}},
    }
    monkeypatch.setattr(cliente, "requisitar", lambda metodo, rota, dados=None: respostas[rota])
    app = AppTest.from_file(str(pasta / "app.py")).run(timeout=20)
    assert not app.exception
    assert app.title[0].value == "RAG Avalia"
    assert next(b for b in app.button if b.label == "Gerar dataset").disabled
    assert not next(b for b in app.button if b.label == "Processar documentos").disabled

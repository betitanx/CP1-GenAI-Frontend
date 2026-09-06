from backend.documentos import processar, recuperar


def test_chunkizacao_preserva_origem_e_sobreposicao(tmp_path):
    (tmp_path / "base.txt").write_text(" ".join(f"palavra{i}" for i in range(21)), encoding="utf-8")
    docs, chunks = processar(tmp_path, 10, 2)
    assert docs[0]["chunks"] == 3
    assert chunks[0]["texto"].split()[-2:] == chunks[1]["texto"].split()[:2]
    assert chunks[-1]["fim_palavra"] == 21
    assert len({c["id"] for c in chunks}) == 3


def test_recuperacao_seleciona_documento_relevante():
    chunks = [{"id": "1", "texto": "Empréstimos de livros na biblioteca"},
              {"id": "2", "texto": "Cultivo de morangos e tomates"}]
    assert recuperar("livros biblioteca", chunks, 1)[0]["id"] == "1"
    assert recuperar("astronauta", chunks, 2) == []

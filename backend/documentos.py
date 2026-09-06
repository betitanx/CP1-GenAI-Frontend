"""Leitura, chunkização por palavras e recuperação lexical."""

from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def processar(pasta: Path, tamanho: int, sobreposicao: int) -> tuple[list, list]:
    documentos, chunks = [], []
    for arquivo in sorted(pasta.iterdir()):
        if not arquivo.is_file() or arquivo.suffix.lower() not in {".pdf", ".txt", ".md"}:
            continue
        if arquivo.suffix.lower() == ".pdf":
            texto = "\n".join(p.extract_text() or "" for p in PdfReader(arquivo).pages)
        else:
            texto = arquivo.read_text(encoding="utf-8")
        palavras = texto.split()
        if not palavras:
            raise ValueError(f"Documento sem texto: {arquivo.name}. PDFs digitalizados precisam de OCR.")
        documento_id = sha256(arquivo.name.encode()).hexdigest()[:12]
        inicio = len(chunks)
        for numero, posicao in enumerate(range(0, len(palavras), tamanho - sobreposicao), 1):
            trecho = " ".join(palavras[posicao:posicao + tamanho])
            chunks.append({"id": f"{documento_id}-{numero}", "documento_id": documento_id,
                           "documento": arquivo.name, "texto": trecho,
                           "inicio_palavra": posicao, "fim_palavra": min(posicao + tamanho, len(palavras))})
            if posicao + tamanho >= len(palavras):
                break
        documentos.append({"id": documento_id, "nome": arquivo.name, "chunks": len(chunks) - inicio})
    if not chunks:
        raise ValueError("Coloque arquivos PDF, TXT ou MD na pasta backend/documentos.")
    return documentos, chunks


def recuperar(pergunta: str, chunks: list, quantidade: int) -> list:
    vetorizador = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2))
    matriz = vetorizador.fit_transform([c["texto"] for c in chunks])
    notas = cosine_similarity(vetorizador.transform([pergunta]), matriz)[0]
    indices = notas.argsort()[::-1][:quantidade]
    return [{**chunks[i], "similaridade": round(float(notas[i]), 5)} for i in indices if notas[i] > 0]

"""Endpoints do checkpoint integrado de IA Generativa e Front-end."""

from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Lock
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend import llm
from backend.armazenamento import Armazenamento
from backend.documentos import processar, recuperar

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


class Chunkizacao(BaseModel):
    tamanho: int = Field(default=120, ge=30, le=1000)
    sobreposicao: int = Field(default=20, ge=0, le=300)

    @model_validator(mode="after")
    def validar(self):
        if self.sobreposicao >= self.tamanho:
            raise ValueError("A sobreposição deve ser menor que o tamanho do chunk.")
        return self


class Personas(BaseModel):
    personas: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validar(self):
        if any(not p.strip() or len(p) > 300 for p in self.personas):
            raise ValueError("Cada persona deve conter entre 1 e 300 caracteres.")
        return self


class Geracao(BaseModel):
    quantidade: int = Field(default=5, ge=1, le=20)


class Execucao(BaseModel):
    top_k: int = Field(default=3, ge=1, le=10)


def criar_app(pasta_documentos: Path | None = None, caminho_estado: Path | None = None) -> FastAPI:
    app = FastAPI(title="RAG Avalia", description="API de avaliação RAG sem ground truth", version="1.0.0")
    banco = Armazenamento(caminho_estado or RAIZ / "backend/dados/estado.json")
    pasta = pasta_documentos or RAIZ / "backend/documentos"
    trava = Lock()

    def alterar(operacao):
        if not trava.acquire(blocking=False):
            raise HTTPException(409, "Outra etapa está em execução. Aguarde sua conclusão.")
        try:
            estado = banco.ler()
            resultado = operacao(estado)
            banco.salvar(estado)
            return resultado
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro
        finally:
            trava.release()

    @app.get("/saude")
    def saude():
        return {"status": "disponível", "llm_configurada": bool(os.getenv("LLM_API_KEY")),
                "modelo": os.getenv("LLM_MODEL", "gpt-4o-mini"),
                "modelo_juiz": os.getenv("LLM_JUDGE_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))}

    @app.post("/documentos/processar")
    def chunkizar(config: Chunkizacao):
        def operacao(estado):
            documentos, chunks = processar(pasta, config.tamanho, config.sobreposicao)
            estado.update(documentos=documentos, chunks=chunks, dataset=[], configuracao=config.model_dump())
            return {"documentos": documentos, "total_documentos": len(documentos), "total_chunks": len(chunks)}
        return alterar(operacao)

    @app.get("/documentos")
    def documentos():
        estado = banco.ler()
        return {"documentos": estado["documentos"], "total_documentos": len(estado["documentos"]),
                "total_chunks": len(estado["chunks"]), "configuracao": estado["configuracao"]}

    @app.get("/documentos/{documento_id}/chunks")
    def chunks_documento(documento_id: str):
        chunks = [c for c in banco.ler()["chunks"] if c["documento_id"] == documento_id]
        if not chunks:
            raise HTTPException(404, "Documento não encontrado. Processe a base primeiro.")
        return {"chunks": chunks, "quantidade": len(chunks)}

    @app.post("/personas")
    def configurar_personas(config: Personas):
        def operacao(estado):
            estado["personas"] = [p.strip() for p in config.personas]
            return {"personas": estado["personas"]}
        return alterar(operacao)

    @app.post("/dataset/gerar")
    def gerar(config: Geracao):
        def operacao(estado):
            if not estado["chunks"]:
                raise ValueError("Processe os documentos antes de gerar perguntas.")
            dataset = []
            personas = estado["personas"] or ["Usuário genérico interessado no conteúdo"]
            for i in range(config.quantidade):
                indice = (i * len(estado["chunks"]) // config.quantidade) % len(estado["chunks"])
                chunk = estado["chunks"][indice]
                persona = personas[i % len(personas)]
                anteriores = [item["pergunta"] for item in dataset]
                pergunta = llm.gerar_pergunta(chunk, persona, anteriores).strip()
                if pergunta.casefold() in {p.casefold() for p in anteriores}:
                    raise ValueError("A LLM repetiu uma pergunta. Gere o dataset novamente.")
                dataset.append({"id": str(uuid4()), "pergunta": pergunta,
                                "persona": persona if estado["personas"] else None,
                                "fonte": {"documento": chunk["documento"], "chunk_id": chunk["id"]},
                                "contextos": [], "resposta": None, "metricas": None,
                                "modelo_gerador": os.getenv("LLM_MODEL", "gpt-4o-mini"),
                                "criado_em": datetime.now(timezone.utc).isoformat()})
            estado["dataset"] = dataset
            return {"quantidade": len(dataset), "dataset": dataset}
        return alterar(operacao)

    @app.post("/rag/executar")
    def executar(config: Execucao):
        def operacao(estado):
            if not estado["dataset"]:
                raise ValueError("Gere o dataset antes de executar o RAG.")
            for item in estado["dataset"]:
                contextos = recuperar(item["pergunta"], estado["chunks"], config.top_k)
                resposta = llm.responder(item["pergunta"], contextos)
                item.update(contextos=contextos, resposta=resposta, metricas=None, top_k=config.top_k,
                            modelo_resposta=os.getenv("LLM_MODEL", "gpt-4o-mini"))
            return {"quantidade": len(estado["dataset"]), "status": "respondido"}
        return alterar(operacao)

    @app.post("/avaliacao/executar")
    def avaliar():
        def operacao(estado):
            if not estado["dataset"] or any(i["resposta"] is None for i in estado["dataset"]):
                raise ValueError("Execute o RAG antes de avaliar as respostas.")
            for item in estado["dataset"]:
                item["metricas"] = llm.avaliar(item["pergunta"], item["contextos"], item["resposta"])
                item["modelo_juiz"] = os.getenv("LLM_JUDGE_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
                item["avaliado_em"] = datetime.now(timezone.utc).isoformat()
            return {"quantidade": len(estado["dataset"]), "status": "avaliado"}
        return alterar(operacao)

    @app.get("/avaliacao/resultados")
    def resultados():
        itens = [i for i in banco.ler()["dataset"] if i["metricas"] is not None]
        medias = {m: sum(i["metricas"][m]["nota"] for i in itens) / len(itens)
                  for m in ("faithfulness", "answer_relevancy", "context_utilization")} if itens else {}
        return {"quantidade": len(itens), "medias": medias,
                "resultados": [{"id": i["id"], "pergunta": i["pergunta"], "metricas": i["metricas"]} for i in itens]}

    @app.get("/dataset")
    def dataset():
        estado = banco.ler()
        return {"dataset": estado["dataset"], "personas": estado["personas"]}

    return app


app = criar_app()

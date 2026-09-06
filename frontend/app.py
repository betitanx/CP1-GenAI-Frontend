"""Interface Streamlit consumindo exclusivamente a API FastAPI."""

import json
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

from cliente import requisitar

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
st.set_page_config(page_title="RAG Avalia", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp {background: #f7f8fa;}
[data-testid="stSidebar"] {background: #edf1f5;}
h1,h2,h3 {letter-spacing:-.035em;}
[data-testid="stMetric"] {background:white;padding:20px;border:1px solid #dce2e8;border-radius:12px;}
.stButton button {border-radius:8px;}
</style>""", unsafe_allow_html=True)


def acionar(rotulo, rota, dados=None, desabilitado=False):
    if st.button(rotulo, disabled=desabilitado, use_container_width=True, type="primary"):
        try:
            with st.spinner("Processando…"):
                requisitar("POST", rota, dados)
            st.rerun()
        except RuntimeError as erro:
            st.error(str(erro))


st.title("RAG Avalia")
try:
    saude = requisitar("GET", "/saude")
    documentos = requisitar("GET", "/documentos")
    estado = requisitar("GET", "/dataset")
    avaliacao = requisitar("GET", "/avaliacao/resultados")
except RuntimeError as erro:
    st.error(str(erro))
    st.stop()

dataset = estado["dataset"]
with st.sidebar:
    st.header("Configuração")
    st.badge("API conectada")
    if not saude["llm_configurada"]:
        st.warning("Configure LLM_API_KEY no .env do back-end e reinicie a API.")
    st.text(f"Modelo: {saude['modelo']}")
    st.text(f"Juiz: {saude['modelo_juiz']}")
    tamanho = st.number_input("Palavras por chunk", 30, 1000, 120, step=10)
    sobreposicao = st.number_input("Sobreposição em palavras", 0, min(tamanho - 1, 300), min(20, tamanho - 1))
    quantidade = st.number_input("Quantidade de perguntas", 1, 20, 5)
    top_k = st.number_input("Contextos por pergunta", 1, 10, 3)
    usar_personas = st.toggle("Utilizar personas", value=bool(estado["personas"]))
    personas = st.text_area("Personas — uma por linha", value="\n".join(estado["personas"]),
                           disabled=not usar_personas, placeholder="Estudante: busca explicações didáticas")
    if st.button("Salvar personas", use_container_width=True):
        try:
            requisitar("POST", "/personas", {"personas": [p.strip() for p in personas.splitlines() if p.strip()] if usar_personas else []})
            st.rerun()
        except RuntimeError as erro:
            st.error(str(erro))

colunas = st.columns(4)
for coluna, nome, valor in zip(colunas, ["Documentos", "Chunks", "Perguntas", "Avaliadas"],
                              [documentos["total_documentos"], documentos["total_chunks"], len(dataset), avaliacao["quantidade"]]):
    coluna.metric(nome, valor)

base, perguntas, resultados = st.tabs(["01 · Documentos", "02 · Dataset e RAG", "03 · Avaliação"])
with base:
    st.header("Base de conhecimento")
    if dataset:
        confirmar = st.checkbox("Reprocessar documentos e apagar o dataset atual")
    else:
        confirmar = True
    acionar("Processar documentos", "/documentos/processar", {"tamanho": tamanho, "sobreposicao": sobreposicao}, not confirmar)
    if not documentos["documentos"]:
        st.info("Adicione arquivos PDF, TXT ou MD à pasta backend/documentos e clique em Processar documentos.")
    for documento in documentos["documentos"]:
        with st.expander(f"{documento['nome']} · {documento['chunks']} chunks"):
            try:
                chunks = requisitar("GET", f"/documentos/{documento['id']}/chunks")["chunks"]
                for chunk in chunks:
                    st.markdown(f"**{chunk['id']}**")
                    st.text(chunk["texto"])
            except RuntimeError as erro:
                st.error(str(erro))

with perguntas:
    st.header("Perguntas sintéticas")
    substituir = st.checkbox("Substituir o dataset e os resultados atuais") if dataset else True
    acionar("Gerar dataset", "/dataset/gerar", {"quantidade": quantidade},
            not documentos["total_chunks"] or not saude["llm_configurada"] or not substituir)
    acionar("Executar perguntas no RAG", "/rag/executar", {"top_k": top_k}, not dataset or not saude["llm_configurada"])
    if dataset:
        st.dataframe([{"Pergunta": i["pergunta"], "Persona": i["persona"] or "Sem persona",
                       "Documento": i["fonte"]["documento"], "Chunk de origem": i["fonte"]["chunk_id"],
                       "Estado": "Avaliada" if i["metricas"] else "Respondida" if i["resposta"] else "Gerada"}
                      for i in dataset], hide_index=True, use_container_width=True)

with resultados:
    st.header("Avaliação sem ground truth")
    acionar("Avaliar respostas", "/avaliacao/executar", desabilitado=not dataset or
            any(i["resposta"] is None for i in dataset) or not saude["llm_configurada"])
    nomes = {"faithfulness": "Fidelidade", "answer_relevancy": "Relevância da resposta", "context_utilization": "Utilização do contexto"}
    if avaliacao["medias"]:
        for coluna, (metrica, nome) in zip(st.columns(3), nomes.items()):
            coluna.metric(nome, f"{avaliacao['medias'][metrica]:.2f}")
        st.dataframe([{"Pergunta": i["pergunta"], **{nomes[m]: i["metricas"][m]["nota"] for m in nomes}}
                      for i in dataset if i["metricas"]], hide_index=True, use_container_width=True)
    for i, item in enumerate(dataset, 1):
        with st.expander(f"{i:02d} · {item['pergunta']}"):
            st.markdown("**Resposta gerada**")
            st.write(item["resposta"] or "Aguardando execução do RAG.")
            st.markdown("**Contextos recuperados**")
            for contexto in item["contextos"]:
                st.markdown(f"**{contexto['documento']} · {contexto['id']} · similaridade {contexto['similaridade']:.3f}**")
                st.text(contexto["texto"])
            if not item["contextos"] and item["resposta"]:
                st.info("Nenhum contexto apresentou similaridade positiva com a pergunta.")
            if item["metricas"]:
                for metrica, nome in nomes.items():
                    nota = item["metricas"][metrica]
                    st.markdown(f"**{nome}: {nota['nota']:.2f}**")
                    st.write(nota["justificativa"])
    if dataset:
        st.download_button("Baixar resultados em JSON", json.dumps(estado, ensure_ascii=False, indent=2),
                           "avaliacao-rag.json", "application/json")

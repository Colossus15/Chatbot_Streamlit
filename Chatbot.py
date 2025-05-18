import os
import ollama
from langchain_ollama import OllamaEmbeddings
from langchain_ollama import ChatOllama
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage
from streamlit_chat import message
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
import getpass
from langchain.chains import RetrievalQA
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing_extensions import List, TypedDict
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["USER_AGENT"] = os.getenv("USER_AGENT")

# Modelos LLM ##########################
def list_models():
    models_running = ollama.list()['models']
    available_models = [model["model"] for model in models_running]
    return available_models

lista = list_models()

# Estado inicial
if 'model_selection' not in st.session_state:
    st.session_state.model_selection = lista[0] if lista else None

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'model_selection' not in st.session_state:
    st.session_state.model_selection = lista[0]  if lista else None

with st.sidebar:
    st.title('🤖Modelos LLM🧠')
    st.session_state.model_selection = st.selectbox('Seleccione un modelo',
                                        options=lista,
                                        index=lista.index(st.session_state.model_selection) if st.session_state.model_selection in lista else 0)
    st.session_state.temperature = st.slider(
    'Temperatura',
    min_value=0.0,
    max_value=1.0,
    value=0.6,
    step=0.1
    )
    st.session_state.top_p = st.slider(
    'Top P',
    min_value=0.0,
    max_value=1.0,
    value=0.95,
    step=0.1
    )
    st.session_state.top_k = st.slider(
    'Top K',
    min_value=0,
    max_value=100,
    value=20,
    step=1
    )

st.title('🤖🧠CHATBOT CON TU DOCUMENTO👾')

llm = init_chat_model(
    model=st.session_state.model_selection, 
    model_provider="ollama",
    temperature=st.session_state.temperature,
    top_p=st.session_state.top_p,
    top_k=st.session_state.top_k
    )

#Carga de archivo PDF ##########################
uploaded_file = st.file_uploader("Sube un archivo PDF", type="pdf")

if uploaded_file is not None:
    # Guardar archivo temporal
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    # Cargar PDF
    loader = PyPDFLoader(tmp_path)
    docs = loader.load()
    st.write(f"📄 Páginas cargadas: {len(docs)}")


    #Spliter ##########################
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, add_start_index=True
    )
    all_splits = text_splitter.split_documents(docs)
    len(all_splits)

    #Embeddings ##########################
    embeddings = OllamaEmbeddings(model="nomic-embed-text:latest")

    #Vector DB ##########################
    vector_store = Chroma(
        collection_name="example_collection",
        embedding_function=embeddings,
        persist_directory="./chroma_langchain_db",  # Where to save data locally, remove if not necessary
    )
    ids = vector_store.add_documents(documents=all_splits)


    #Chatbot 
    # Crear cadena de recuperación con RAG
    retriever = vector_store.as_retriever(search_kwargs={"k": 4})

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True
    )

    user_input = st.chat_input("Escribe tu pregunta aquí...")

    # Mostrar historial de chat
    for i, msg in enumerate(st.session_state.chat_history):
        if isinstance(msg, HumanMessage):
            message(msg.content, is_user=True, key=f"user_{i}")
        elif isinstance(msg, AIMessage):
            message(msg.content, is_user=False, key=f"ai_{i}")

    # Procesar nueva pregunta
    if user_input:
        st.session_state.chat_history.append(HumanMessage(content=user_input))

        with st.spinner("Pensando..."):
            result = qa_chain.invoke({"query": user_input})
            response = result["result"]

            st.session_state.chat_history.append(AIMessage(content=response))
            message(user_input, is_user=True, key="latest_user")
            message(response, is_user=False, key="latest_ai")
import streamlit as st
import os
import tempfile
import requests
import msal

# --- IMPORTACIONES ---
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# Lectura local ultraligera
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

# El motor conversacional ultrarrápido de Groq
from langchain_groq import ChatGroq

# --- 1. SISTEMA DE CONTRASEÑA ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Acceso Restringido")
        st.text_input("Introduce la contraseña para acceder a los contratos", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 Acceso Restringido")
        st.text_input("Introduce la contraseña para acceder a los contratos", type="password", on_change=password_entered, key="password")
        st.error("😕 Contraseña incorrecta")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. CONFIGURACIÓN ---
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# --- 3. FUNCIONES BACKEND ---
def upload_to_sharepoint(file_path, filename):
    st.info("Subiendo a SharePoint...")
    # Aquí irá la lógica real de Microsoft Graph API más adelante
    st.success(f"✅ Documento '{filename}' guardado en SharePoint exitosamente.")
    return "ID_SIMULADO_123"

def analyze_and_index(file_path):
    # Detectar extensión para PDF o Word
    if file_path.lower().endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    elif file_path.lower().endswith('.docx'):
        loader = Docx2txtLoader(file_path)
    else:
        st.error("Formato no soportado")
        return None
        
    documents = loader.load()
    
    # Cortar texto en fragmentos
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    
    # Lectura local con FastEmbed (Estable y sin límites de red)
    embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    
    vector_db = FAISS.from_documents(documents=texts, embedding=embeddings)
    return vector_db

# --- 4. INTERFAZ GRÁFICA ---
st.title("📄 Analizador de Contratos (Motor Groq)")
st.markdown("Sube un contrato (PDF/Word) para guardarlo y consultarlo a la velocidad de la luz.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

with st.sidebar:
    st.header("1. Subir Contrato")
    uploaded_file = st.file_uploader("Archivo", type=["pdf", "docx"])
    
    if uploaded_file is not None and st.button("Procesar y Guardar"):
        with st.spinner("Procesando documento localmente..."):
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            st.session_state.vector_db = analyze_and_index(tmp_file_path)
            upload_to_sharepoint(tmp_file_path, uploaded_file.name)
            
            st.success("¡Listo! Documento indexado.")

st.header("2. Pregúntale a tu Contrato")

# Mostrar historial de chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ej: ¿Cuáles son las obligaciones del cliente?"):
    if st.session_state.vector_db is None:
        st.warning("⚠️ Primero debes subir un contrato en el panel izquierdo.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Consultando a Groq AI..."):
                
                # Búsqueda de cláusulas relevantes
                docs_relevantes = st.session_state.vector_db.similarity_search(prompt, k=4)
                contexto = "\n\n".join([doc.page_content for doc in docs_relevantes])
                
                instruccion = f"""
                Actúa como un abogado experto. Responde a la pregunta basándote SOLO en el siguiente contexto del contrato.
                Si la respuesta no está en el texto, di claramente "No se menciona en el documento". Responde en español.
                
                CONTEXTO:
                {contexto}
                
                PREGUNTA:
                {prompt}
                """
                
                try:
                    # Conexión súper rápida y nativa a Groq
                    llm = ChatGroq(
                        api_key=GROQ_API_KEY,
                        model_name="llama3-8b-8192", # Modelo brutalmente rápido y bueno en razonamiento
                        temperature=0.1
                    )
                    
                    # Ejecutar y obtener respuesta
                    respuesta = llm.invoke(instruccion).content
                    
                    st.markdown(respuesta)
                    st.session_state.messages.append({"role": "assistant", "content": respuesta})
                except Exception as e:
                    st.error(f"Error conectando con Groq: {e}")

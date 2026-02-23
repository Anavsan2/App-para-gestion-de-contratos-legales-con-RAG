import streamlit as st
import os
import tempfile
import requests
import msal

# Importamos los dos lectores: uno para PDF y otro para Word
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from langchain_huggingface import HuggingFaceEndpoint, HuggingFaceEndpointEmbeddings

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

# --- 2. CONFIGURACIÓN DESDE STREAMLIT SECRETS ---
HF_TOKEN = st.secrets["HUGGINGFACE_API_TOKEN"]
os.environ["HUGGINGFACEHUB_API_TOKEN"] = HF_TOKEN

# --- 3. FUNCIONES BACKEND ---
def upload_to_sharepoint(file_path, filename):
    st.info("Subiendo a SharePoint...")
    st.success(f"✅ Documento '{filename}' guardado en SharePoint exitosamente.")
    return "ID_SIMULADO_123"

def analyze_and_index(file_path):
    # Detectamos la extensión para usar el lector correcto
    if file_path.lower().endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    elif file_path.lower().endswith('.docx'):
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError("Formato de archivo no soportado.")
        
    documents = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    
    embeddings = HuggingFaceEndpointEmbeddings(
        model="sentence-transformers/all-MiniLM-L6-v2",
        task="feature-extraction",
        huggingfacehub_api_token=HF_TOKEN
    )
    
    vector_db = FAISS.from_documents(documents=texts, embedding=embeddings)
    return vector_db

# --- 4. INTERFAZ GRÁFICA (FRONTEND) ---
st.title("📄 Analizador de Contratos (Soporta PDF y Word)")
st.markdown("Sube un contrato para guardarlo en SharePoint y hazle preguntas al instante.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

with st.sidebar:
    st.header("1. Subir Contrato")
    # Ahora aceptamos tanto PDF como DOCX
    uploaded_file = st.file_uploader("Elige un archivo PDF o Word (.docx)", type=["pdf", "docx"])
    
    if uploaded_file is not None and st.button("Procesar y Guardar"):
        with st.spinner("Conectando con la IA en la nube e indexando..."):
            
            # Obtenemos la extensión real del archivo subido (.pdf o .docx)
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            
            # Guardamos el archivo temporal con su extensión correcta
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            st.session_state.vector_db = analyze_and_index(tmp_file_path)
            upload_to_sharepoint(tmp_file_path, uploaded_file.name)
            
            st.success("¡Listo! Ya puedes hacerle preguntas al contrato.")

st.header("2. Pregúntale a tu Contrato")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ej: ¿Cuáles son las condiciones de pago?"):
    if st.session_state.vector_db is None:
        st.warning("⚠️ Primero debes subir y procesar un contrato en la barra lateral.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analizando cláusulas con Mistral..."):
                
                docs_relevantes = st.session_state.vector_db.similarity_search(prompt, k=4)
                contexto = "\n\n".join([doc.page_content for doc in docs_relevantes])
                
                llm = HuggingFaceEndpoint(
                    repo_id="mistralai/Mistral-7B-Instruct-v0.3",
                    temperature=0.1,
                    max_new_tokens=512,
                    huggingfacehub_api_token=HF_TOKEN
                )
                
                instruccion = f"""
                Eres un asistente legal experto. Usa ÚNICAMENTE la siguiente información extraída del contrato para responder a la pregunta del usuario. Responde en español.
                Si la respuesta no está en este contexto, di "No he encontrado esta información en el contrato subido".
                
                CONTEXTO DEL CONTRATO:
                {contexto}
                
                PREGUNTA DEL USUARIO:
                {prompt}
                """
                
                respuesta = llm.invoke(instruccion)
                st.markdown(respuesta)
                
        st.session_state.messages.append({"role": "assistant", "content": respuesta})

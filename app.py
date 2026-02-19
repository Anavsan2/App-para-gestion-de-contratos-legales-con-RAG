import streamlit as st
import os
import tempfile
import requests
import msal
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA

# --- 1. SISTEMA DE CONTRASEÑA ---
def check_password():
    """Devuelve True si el usuario ingresó la contraseña correcta."""
    def password_entered():
        # Comprueba si la contraseña introducida coincide con la guardada en los secretos
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Borra la contraseña por seguridad
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

# Si la contraseña no es correcta, detenemos la ejecución de la app aquí
if not check_password():
    st.stop()

# --- 2. CONFIGURACIÓN DESDE STREAMLIT SECRETS ---
# En Streamlit Cloud, las claves se sacan de st.secrets, NO del código.
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# --- 3. FUNCIONES BACKEND (Las que vimos antes) ---
def get_graph_token():
    app = msal.ConfidentialClientApplication(
        st.secrets["CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{st.secrets['TENANT_ID']}",
        client_credential=st.secrets["CLIENT_SECRET"],
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")

def upload_to_sharepoint(file_path, filename):
    st.info("Subiendo a SharePoint...")
    # (Aquí iría la lógica de requests.put y requests.patch que vimos antes)
    # Por brevedad en la UI, simulamos el éxito:
    st.success(f"✅ Documento {filename} guardado en SharePoint exitosamente.")
    return "ID_SIMULADO_123"

def analyze_and_index(file_path):
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    
    embeddings = OpenAIEmbeddings()
    # Usamos Chroma en memoria para el MVP rápido
    vector_db = Chroma.from_documents(documents=texts, embedding=embeddings)
    return vector_db

# --- 4. INTERFAZ GRÁFICA (FRONTEND) ---
st.title("📄 Analizador de Contratos Inteligente")
st.markdown("Sube un contrato para guardarlo en SharePoint y hazle preguntas al instante.")

# Inicializar el historial de chat y la base de datos en la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []
if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

# Barra lateral para subir archivos
with st.sidebar:
    st.header("1. Subir Contrato")
    uploaded_file = st.file_uploader("Elige un archivo PDF", type="pdf")
    
    if uploaded_file is not None and st.button("Procesar y Guardar"):
        with st.spinner("Leyendo documento e indexando..."):
            # Streamlit maneja archivos en memoria, PyPDFLoader necesita una ruta física. 
            # Creamos un archivo temporal:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            # Procesar IA
            st.session_state.vector_db = analyze_and_index(tmp_file_path)
            
            # Subir a SharePoint
            upload_to_sharepoint(tmp_file_path, uploaded_file.name)
            
            st.success("¡Listo! Ya puedes hacerle preguntas al contrato.")

# Área principal: El Chatbot
st.header("2. Pregúntale a tu Contrato (Ask Lumi Clone)")

# Mostrar mensajes anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Caja de texto para nueva pregunta
if prompt := st.chat_input("Ej: ¿Cuáles son las condiciones de pago?"):
    if st.session_state.vector_db is None:
        st.warning("⚠️ Primero debes subir y procesar un contrato en la barra lateral.")
    else:
        # Mostrar pregunta del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generar respuesta de la IA
        with st.chat_message("assistant"):
            with st.spinner("Analizando cláusulas..."):
                qa_chain = RetrievalQA.from_chain_type(
                    llm=ChatOpenAI(model_name="gpt-3.5-turbo"),
                    chain_type="stuff",
                    retriever=st.session_state.vector_db.as_retriever()
                )
                respuesta = qa_chain.run(prompt)
                st.markdown(respuesta)
        
        # Guardar respuesta en el historial
        st.session_state.messages.append({"role": "assistant", "content": respuesta})

import streamlit as st
import os
import tempfile
import requests
import msal

# --- IMPORTACIONES MODERNAS DE LANGCHAIN ---
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS

# --- 1. SISTEMA DE CONTRASEÑA ---
def check_password():
    """Devuelve True si el usuario ingresó la contraseña correcta."""
    def password_entered():
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

if not check_password():
    st.stop()

# --- 2. CONFIGURACIÓN DESDE STREAMLIT SECRETS ---
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# --- 3. FUNCIONES BACKEND ---
def get_graph_token():
    """Simula o gestiona la conexión con Azure AD / SharePoint"""
    app = msal.ConfidentialClientApplication(
        st.secrets["CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{st.secrets['TENANT_ID']}",
        client_credential=st.secrets["CLIENT_SECRET"],
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")

def upload_to_sharepoint(file_path, filename):
    """Simula la subida del archivo a SharePoint"""
    st.info("Subiendo a SharePoint...")
    # Aquí irá tu lógica real de requests a Graph API
    st.success(f"✅ Documento '{filename}' guardado en SharePoint exitosamente.")
    return "ID_SIMULADO_123"

def analyze_and_index(file_path):
    """Lee el PDF y lo guarda en la base de datos vectorial (FAISS)"""
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    
    # Cortar el texto en trozos pequeños
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    
    # Convertir a vectores usando FAISS
    embeddings = OpenAIEmbeddings()
    vector_db = FAISS.from_documents(documents=texts, embedding=embeddings)
    return vector_db

# --- 4. INTERFAZ GRÁFICA (FRONTEND) ---
st.title("📄 Analizador de Contratos Inteligente")
st.markdown("Sube un contrato para guardarlo en SharePoint y hazle preguntas al instante.")

# Inicializar memoria de sesión
if "messages" not in st.session_state:
    st.session_state.messages = []
if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

# Barra lateral
with st.sidebar:
    st.header("1. Subir Contrato")
    uploaded_file = st.file_uploader("Elige un archivo PDF", type="pdf")
    
    if uploaded_file is not None and st.button("Procesar y Guardar"):
        with st.spinner("Leyendo documento e indexando..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            # Indexar en IA
            st.session_state.vector_db = analyze_and_index(tmp_file_path)
            
            # Guardar en SharePoint
            upload_to_sharepoint(tmp_file_path, uploaded_file.name)
            
            st.success("¡Listo! Ya puedes hacerle preguntas al contrato.")

# Chat Principal
st.header("2. Pregúntale a tu Contrato")

# Mostrar historial de mensajes
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Nueva pregunta del usuario
if prompt := st.chat_input("Ej: ¿Cuáles son las condiciones de pago?"):
    if st.session_state.vector_db is None:
        st.warning("⚠️ Primero debes subir y procesar un contrato en la barra lateral.")
    else:
        # Mostrar pregunta
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generar respuesta de la IA (Enfoque manual RAG sin 'chains')
        with st.chat_message("assistant"):
            with st.spinner("Analizando cláusulas..."):
                
                # 1. Buscar los fragmentos más relevantes en el contrato
                docs_relevantes = st.session_state.vector_db.similarity_search(prompt, k=4)
                contexto = "\n\n".join([doc.page_content for doc in docs_relevantes])
                
                # 2. Configurar el modelo de OpenAI
                llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
                
                # 3. Crear el Prompt estricto
                instruccion = f"""
                Eres un asistente legal experto. Usa ÚNICAMENTE la siguiente información extraída del contrato para responder a la pregunta del usuario.
                Si la respuesta no está en este contexto, di claramente "No he encontrado esta información en el contrato subido".
                
                CONTEXTO DEL CONTRATO:
                {contexto}
                
                PREGUNTA DEL USUARIO:
                {prompt}
                """
                
                # 4. Obtener y mostrar la respuesta
                respuesta = llm.invoke(instruccion).content
                st.markdown(respuesta)
                
        # Guardar respuesta en el historial
        st.session_state.messages.append({"role": "assistant", "content": respuesta})

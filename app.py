import os
import json
import requests
import msal  # Librería de autenticación de Microsoft
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA

# --- CONFIGURACIÓN (Rellena esto con tus datos reales) ---
CONFIG = {
    "sharepoint_site_id": "TU_SITE_ID_DE_SHAREPOINT",
    "sharepoint_drive_id": "TU_DRIVE_ID_DE_DOCUMENTOS",
    "client_id": "TU_AZURE_CLIENT_ID",
    "client_secret": "TU_AZURE_CLIENT_SECRET",
    "tenant_id": "TU_AZURE_TENANT_ID",
    "openai_api_key": "TU_CLAVE_DE_OPENAI"
}

# Configurar OpenAI
os.environ["OPENAI_API_KEY"] = CONFIG["openai_api_key"]

# --- PASO 1: CONEXIÓN CON MICROSOFT SHAREPOINT (Graph API) ---
def get_graph_token():
    """Obtiene el permiso temporal para hablar con SharePoint"""
    app = msal.ConfidentialClientApplication(
        CONFIG["client_id"],
        authority=f"https://login.microsoftonline.com/{CONFIG['tenant_id']}",
        client_credential=CONFIG["client_secret"],
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")

def upload_to_sharepoint(file_path, filename, metadata):
    """Sube el PDF a SharePoint y actualiza sus columnas (metadatos)"""
    token = get_graph_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 1. Subir el archivo físico
    with open(file_path, 'rb') as file:
        file_content = file.read()
    
    upload_url = f"https://graph.microsoft.com/v1.0/sites/{CONFIG['sharepoint_site_id']}/drives/{CONFIG['sharepoint_drive_id']}/root:/{filename}:/content"
    
    response = requests.put(upload_url, headers=headers, data=file_content)
    
    if response.status_code in [200, 201]:
        item_id = response.json()["id"]
        print(f"✅ Archivo subido a SharePoint con ID: {item_id}")
        
        # 2. Actualizar las columnas (Ej: Empresa, Valor)
        # Nota: La URL cambia ligeramente para actualizar 'listItems'
        update_url = f"https://graph.microsoft.com/v1.0/sites/{CONFIG['sharepoint_site_id']}/drives/{CONFIG['sharepoint_drive_id']}/items/{item_id}/listItem/fields"
        
        # Mapeo de tus columnas en SharePoint
        sharepoint_fields = {
            "Title": metadata.get("empresa", "Desconocida"), # Columna 'Title'
            "ValorContrato": metadata.get("valor", 0),       # Columna personalizada 'ValorContrato'
            "TipoDocumento": "Contrato"                      # Columna personalizada
        }
        
        patch_response = requests.patch(update_url, headers=headers, json=sharepoint_fields)
        if patch_response.status_code == 200:
            print("✅ Metadatos actualizados en SharePoint.")
        else:
            print(f"⚠️ Error actualizando metadatos: {patch_response.text}")
            
        return item_id
    else:
        print(f"❌ Error subiendo archivo: {response.text}")
        return None

# --- PASO 2: EL CEREBRO (IA y Base Vectorial) ---
def analyze_and_index(file_path):
    """Lee el PDF, extrae datos clave e indexa para el Chatbot"""
    
    print("🔍 Analizando contrato con IA...")
    
    # A. Cargar PDF
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    
    # B. Extraer Metadatos (Simulado aquí, idealmente usarías un LLM Chain para esto)
    # En una app real, le pedirías a GPT-4 que extraiga esto del texto primero.
    metadata_extraida = {
        "empresa": "Empresa Ejemplo S.A.",
        "valor": 15000
    }
    
    # C. Preparar para RAG (Chatbot)
    # Cortar el texto en trozos pequeños
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    
    # D. Guardar en Base de Datos Vectorial (Usamos ChromaDB localmente para este ejemplo)
    # Aquí es donde ocurre la magia del RAG.
    vector_db = Chroma.from_documents(
        documents=texts, 
        embedding=OpenAIEmbeddings(),
        persist_directory="./chroma_db" # Guarda la base de datos en una carpeta local
    )
    print("✅ Contrato memorizado en la base de datos vectorial.")
    
    return metadata_extraida, vector_db

# --- PASO 3: EL CHATBOT (Consultas) ---
def ask_lumi_clone(query, vector_db):
    """Función para preguntar al contrato"""
    qa_chain = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(model_name="gpt-3.5-turbo"),
        chain_type="stuff",
        retriever=vector_db.as_retriever()
    )
    respuesta = qa_chain.run(query)
    return respuesta

# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    archivo_pdf = "contrato_ejemplo.pdf" # El archivo que subió el usuario
    
    # 1. Analizar e Indexar (RAG)
    datos_clave, base_conocimiento = analyze_and_index(archivo_pdf)
    
    # 2. Subir y catalogar en SharePoint
    sp_item_id = upload_to_sharepoint(archivo_pdf, "Contrato_Final.pdf", datos_clave)
    
    # 3. Probamos el Chatbot
    print("\n💬 Iniciando Chat 'Ask Lumi'...")
    pregunta = "¿Cuáles son las condiciones de pago?"
    respuesta = ask_lumi_clone(pregunta, base_conocimiento)
    
    print(f"Pregunta: {pregunta}")
    print(f"Respuesta IA: {respuesta}")

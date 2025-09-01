# google_drive.py
import os
import io
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

load_dotenv()

# Carrega as credenciais do arquivo .env
CREDENTIALS_JSON_STR = os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON')
FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

def conectar_google_drive():
    """Conecta-se à API do Google Drive usando as credenciais de serviço."""
    try:
        creds_info = json.loads(CREDENTIALS_JSON_STR)
        creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"❌ Erro ao conectar com a API do Google Drive: {e}")
        return None

def upload_para_google_drive(bytes_imagem, nome_arquivo):
    """Faz o upload de uma imagem (em bytes) para a pasta configurada no Drive."""
    service = conectar_google_drive()
    if not service:
        return None

    try:
        print(f"☁️ Fazendo upload de '{nome_arquivo}' para o Google Drive...")
        media = MediaIoBaseUpload(io.BytesIO(bytes_imagem), mimetype='image/png')
        file_metadata = {'name': nome_arquivo, 'parents': [FOLDER_ID]}
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webContentLink'
        ).execute()

        file_id = file.get('id')
        
        # Torna o arquivo público para que a API da Meta possa acessá-lo
        service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        
        # Obtém o link direto para o conteúdo do arquivo
        link_direto = service.files().get(fileId=file_id, fields='webContentLink').execute().get('webContentLink')

        print(f"✅ Upload para o Drive concluído! Link: {link_direto}")
        return link_direto
    except Exception as e:
        print(f"❌ Erro durante o upload para o Google Drive: {e}")
        return None
# google_drive.py (Versão Final com Upload e Download)
import os
import io
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS_JSON_STR = os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON')
FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

def conectar_google_drive():
    try:
        creds_info = json.loads(CREDENTIALS_JSON_STR)
        creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"❌ Erro ao conectar com a API do Google Drive: {e}")
        return None

def upload_asset_para_drive(arquivo_stream, nome_arquivo, mimetype):
    """Faz o upload de um ATIVO (logo/fonte) para o Drive e retorna o ID do arquivo."""
    service = conectar_google_drive()
    if not service: return None
    try:
        print(f"☁️ Fazendo upload do ativo '{nome_arquivo}' para o Google Drive...")
        media = MediaIoBaseUpload(arquivo_stream, mimetype=mimetype)
        file_metadata = {'name': f"asset_{nome_arquivo}", 'parents': [FOLDER_ID]}
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')
        print(f"✅ Ativo salvo no Drive com ID: {file_id}")
        return file_id
    except Exception as e:
        print(f"❌ Erro no upload do ativo para o Drive: {e}")
        return None

def baixar_asset_do_drive(file_id):
    """Baixa um ATIVO (logo/fonte) do Drive usando seu ID e retorna os bytes em memória."""
    service = conectar_google_drive()
    if not service: return None
    try:
        request = service.files().get_media(fileId=file_id)
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        print(f"✅ Ativo ID {file_id} baixado do Drive.")
        file_stream.seek(0)
        return file_stream
    except Exception as e:
        print(f"❌ Erro ao baixar ativo do Drive (ID: {file_id}): {e}")
        return None

# A função de upload da imagem final permanece a mesma
def upload_para_google_drive(bytes_imagem, nome_arquivo):
    service = conectar_google_drive()
    if not service: return None
    try:
        print(f"☁️ Fazendo upload de '{nome_arquivo}' para o Google Drive...")
        media = MediaIoBaseUpload(io.BytesIO(bytes_imagem), mimetype='image/png')
        file_metadata = {'name': nome_arquivo, 'parents': [FOLDER_ID]}
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webContentLink').execute()
        file_id = file.get('id')
        service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        link_direto = service.files().get(fileId=file_id, fields='webContentLink').execute().get('webContentLink')
        print(f"✅ Upload para o Drive concluído! Link: {link_direto}")
        return link_direto
    except Exception as e:
        print(f"❌ Erro durante o upload para o Google Drive: {e}")
        return None

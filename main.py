# cloudinary_handler.py
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

# Configuração do Cloudinary com as variáveis de ambiente
cloudinary.config(
  cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'), 
  api_key = os.getenv('CLOUDINARY_API_KEY'), 
  api_secret = os.getenv('CLOUDINARY_API_SECRET'),
  secure = True
)

def upload_asset_to_cloudinary(file_stream, original_filename):
    """
    Faz o upload de um asset (logo ou fonte) para o Cloudinary.
    Retorna a URL segura do arquivo.
    """
    try:
        print(f"☁️ Fazendo upload do asset '{original_filename}' para o Cloudinary...")
        # A pasta 'automacao_assets' será criada automaticamente no Cloudinary
        result = cloudinary.uploader.upload(
            file_stream, 
            folder="automacao_assets",
            resource_type="auto" # Detecta se é imagem ou fonte
        )
        secure_url = result.get('secure_url')
        print(f"✅ Asset salvo no Cloudinary! URL: {secure_url}")
        return secure_url
    except Exception as e:
        print(f"❌ Erro no upload para o Cloudinary: {e}")
        return None

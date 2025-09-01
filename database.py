# database.py (Versão PostgreSQL)
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    """Cria uma conexão com o banco de dados PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def criar_banco_de_dados():
    """Cria as tabelas no banco de dados PostgreSQL, se não existirem."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Sintaxe SERIAL PRIMARY KEY é para PostgreSQL
    cur.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome_cliente TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            logo_path TEXT,
            fonte_titulo_path TEXT,
            fonte_categoria_path TEXT,
            layout_imagem TEXT DEFAULT 'padrão',
            cor_fundo_geral TEXT,
            cor_faixa_categoria TEXT,
            cor_caixa_titulo TEXT,
            cor_texto_titulo TEXT,
            cor_texto_categoria TEXT,
            meta_api_token TEXT,
            instagram_id TEXT,
            facebook_page_id TEXT,
            hashtags_fixas TEXT
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            CONSTRAINT fk_cliente
                FOREIGN KEY(cliente_id) 
                REFERENCES clientes(id)
                ON DELETE CASCADE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS posts_publicados (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL,
            link_noticia TEXT NOT NULL,
            data_publicacao TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_cliente
                FOREIGN KEY(cliente_id) 
                REFERENCES clientes(id)
                ON DELETE CASCADE
        )
    ''')

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Tabelas do PostgreSQL verificadas e prontas.")

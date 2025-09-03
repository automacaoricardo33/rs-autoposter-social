import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def criar_banco_de_dados():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Cria a tabela principal se ela não existir
    cur.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome_cliente TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            logo_path TEXT,
            fonte_titulo_path TEXT,
            fonte_categoria_path TEXT,
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

    # 2. Verifica e adiciona as novas colunas uma a uma, se necessário
    colunas_para_adicionar = {
        'handle_social': 'TEXT',
        'texto_categoria_fixo': 'TEXT',
        'cor_borda_caixa': 'TEXT',
        'raio_borda_caixa': 'INTEGER DEFAULT 0'
    }
    
    for coluna, tipo in colunas_para_adicionar.items():
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'clientes' AND column_name = %s
            );
        """, (coluna,))
        
        if not cur.fetchone()[0]:
            print(f"Adicionando coluna '{coluna}' à tabela 'clientes'...")
            cur.execute(f"ALTER TABLE clientes ADD COLUMN {coluna} {tipo};")
            conn.commit()

    # 3. Cria as outras tabelas
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id SERIAL PRIMARY KEY, cliente_id INTEGER NOT NULL, url TEXT NOT NULL,
            CONSTRAINT fk_cliente FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS posts_publicados (
            id SERIAL PRIMARY KEY, cliente_id INTEGER NOT NULL, link_noticia TEXT NOT NULL,
            data_publicacao TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_cliente FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Banco de dados PostgreSQL verificado e atualizado com sucesso.")

import os
import psycopg2

def get_db_connection():
    # Pega a URL da variável de ambiente que você acabou de cadastrar no Render
    url = os.getenv('DATABASE_URL')
    if not url:
        raise ValueError("DATABASE_URL não encontrada!")
    
    # Garante que o protocolo comece com postgresql:// (o Render às vezes envia postgres://)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
        
    return psycopg2.connect(url)

def init_db():
    sql = '''
        CREATE TABLE IF NOT EXISTS historico_climas_pesquisados (
            id SERIAL PRIMARY KEY,
            cidade VARCHAR(255) NOT NULL,
            data_consulta DATE NOT NULL,
            dados_clima JSONB NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            -- Removido o UNIQUE(cidade, data_consulta) daqui!
        );
    '''
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
            print("Banco de dados inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")
    finally:
        conn.close()
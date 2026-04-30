import os
import json
import requests
from datetime import datetime, timedelta, timezone
from database import get_db_connection


def fahrenheit_to_celsius(fahrenheit):
    if fahrenheit is not None:
        celsius = (fahrenheit - 32) /1.8
        return round(celsius, 2)
    
    return None
        
def miles_to_kilometers(miles):
    if miles is not None:
        kilometers = miles * 1.60934
        return round(kilometers, 2)
    
    return None

def validar_nome_cidade(nome_cidade):
    if not nome_cidade or not isinstance(nome_cidade, str):
        return "Nome da cidade inválido. Por favor, forneça um nome de cidade válido."
    if len(nome_cidade.strip()) < 2:
        return "O nome da cidade deve conter pelo menos 2 caracteres."
    return None

def transformar_dados_clima(dados_clima):
    clima_atual = dados_clima.get('currentConditions', {})
    dias = dados_clima.get('days', [])[:7]
    
    dados_transformados = {
        'data': datetime.now().strftime('%d-%m-%Y'),
        'hora': clima_atual.get('datetime', ''),
        'cidade': dados_clima.get('resolvedAddress', ''),
        'temperatura': fahrenheit_to_celsius(clima_atual.get('temp')),
        'umidade': clima_atual.get('humidity'),
        'vento': miles_to_kilometers(clima_atual.get('windspeed')),
        'precipitacao': clima_atual.get('precip'),
        'icon': clima_atual.get('icon'),
        'previsao': []  
    }

    for dia in dias:
        dia_processado = {
            'data': datetime.strptime(dia.get('datetime', ''), '%Y-%m-%d').strftime('%d-%m-%Y'),
            'temperatura_max': fahrenheit_to_celsius(dia.get('tempmax')),
            'temperatura_min': fahrenheit_to_celsius(dia.get('tempmin')),
            'umidade': dia.get('humidity'),
            'vento': miles_to_kilometers(dia.get('windspeed')),
            'precipitacao': dia.get('precip'),
            'icon': dia.get('icon')
        }
        dados_transformados['previsao'].append(dia_processado)

    return dados_transformados

def buscar_clima_por_cidade(nome_cidade):
    msg_erro = validar_nome_cidade(nome_cidade)
    if msg_erro:
        return {'error': True, 'message': msg_erro, 'status': 400}

    base_url = os.getenv('BASE_URL_VISUAL_CROSSING')
    api_key = os.getenv('VISUAL_CROSSING_API_KEY')
    
    nome_cidade_limpo = nome_cidade.strip().lower()

    # 1. AGORA SEMPRE BUSCAMOS DA API PRIMEIRO
    print(f"Buscando dados mais recentes de {nome_cidade} na API externa...")
    data_inicial = datetime.now().strftime('%Y-%m-%d')
    data_final = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    url = f"{base_url}{nome_cidade}/{data_inicial}/{data_final}?key={api_key}&unitGroup=us&include=days,current"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            return {'error': True, 'message': 'Cidade não encontrada.', 'status': 404}
        
        response.raise_for_status()
        dados_api = response.json()
        
        # Transforma os dados novos da API
        dados_formatados = transformar_dados_clima(dados_api)

        # 2. VERIFICA O ÚLTIMO REGISTRO NO BANCO PARA COMPARAR
        conn = get_db_connection()
        precisa_salvar = True # Assume que vai salvar, a menos que os dados sejam idênticos

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT dados_clima FROM historico_climas_pesquisados 
                    WHERE LOWER(cidade) = %s 
                    ORDER BY criado_em DESC LIMIT 1
                """, (nome_cidade_limpo,))
                ultimo_registro = cur.fetchone()
                
                if ultimo_registro:
                    dados_antigos = ultimo_registro[0]
                    if (dados_antigos.get('temperatura') == dados_formatados.get('temperatura') and
                        dados_antigos.get('umidade') == dados_formatados.get('umidade') and
                        dados_antigos.get('vento') == dados_formatados.get('vento') and
                        dados_antigos.get('precipitacao') == dados_formatados.get('precipitacao')):
                        
                        precisa_salvar = False
                        print(f"O clima em {nome_cidade} não mudou desde a última pesquisa. Ignorando salvamento.")
        except Exception as e:
            print(f"Erro ao verificar último registro: {e}")
        finally:
            conn.close()

        # 3. SE HOUVE MUDANÇA (Ou se for a primeira vez), GRAVA NO BANCO
        if precisa_salvar:
            fuso_brasil = timezone(timedelta(hours=-3))
            data_hoje_str = datetime.now(fuso_brasil).strftime('%Y-%m-%d')
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    # Removemos o "ON CONFLICT DO NOTHING" porque a tabela agora aceita duplicadas
                    cur.execute("""
                        INSERT INTO historico_climas_pesquisados (cidade, data_consulta, dados_clima) 
                        VALUES (%s, %s, %s)
                    """, (nome_cidade_limpo, data_hoje_str, json.dumps(dados_formatados)))
                    conn.commit()
                    print(f"Nova variação de clima para {nome_cidade} registrada no banco.")
            except Exception as e:
                print(f"Erro ao salvar no banco: {e}")
            finally:
                conn.close()

        return {'error': False, 'data': dados_formatados, 'status': 200}

    except Exception as e:
        return {'error': True, 'message': f"Erro: {str(e)}", 'status': 500}
    
def buscar_historico():
    """Busca os registros convertendo o fuso horário para Brasília."""
    conn = get_db_connection()
    historico = []
    try:
        with conn.cursor() as cur:
            # A mágica acontece aqui: AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo'
            cur.execute("""
                SELECT 
                    cidade, 
                    data_consulta, 
                    criado_em AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo' as hora_brasil, 
                    dados_clima 
                FROM historico_climas_pesquisados 
                ORDER BY criado_em DESC 
                LIMIT 20
            """)
            registros = cur.fetchall()
            
            for reg in registros:
                dados_json = reg[3]
                historico.append({
                    'cidade': reg[0].title(),
                    'data_consulta': reg[2].strftime('%d/%m/%Y'), # Usamos a data da coluna timestamptz ajustada
                    'hora_pesquisa': reg[2].strftime('%H:%M'),    # Agora sairá no horário de Brasília
                    'temperatura': dados_json.get('temperatura'),
                    'umidade': dados_json.get('umidade')
                })
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
    finally:
        conn.close()
        
    return historico
    
    
    
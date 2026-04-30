import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash # Adicionado o 'flash' aqui
from weather_service import buscar_clima_por_cidade, buscar_historico
from database import init_db

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY')

with app.app_context():
    init_db()

@app.route('/', methods=['GET'])
def consulta_clima():
    cidade = request.args.get('cidade', '').strip()
    weather = None

    if cidade:
        result = buscar_clima_por_cidade(cidade)
        
        if result['error']:
            # Envia mensagem de ERRO para o HTML
            flash(result['message'], 'error')
        else:
            weather = result['data']
            # Envia mensagem de SUCESSO para o HTML
            flash(f"Clima atual de {weather['cidade']} carregado com sucesso!", 'success')
            
    return render_template('index.html', weather=weather, cidade=cidade)

@app.route('/historico', methods=['GET'])
def pagina_historico():
    dados_historico = buscar_historico()
    return render_template('historico.html', historico=dados_historico)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
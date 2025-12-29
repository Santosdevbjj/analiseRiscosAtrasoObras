import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
import numpy as np
import os

# 1. Configuração da Página
st.set_page_config(page_title="MRV - Predictive Risk", layout="wide")

# =====================
# 1. Carregamento do Modelo
# =====================
@st.cache_resource
def load_model():
    # Caminhos possíveis para o modelo
    paths = ["models/modelo_random_forest.pkl", "../models/modelo_random_forest.pkl"]
    for p in paths:
        if os.path.exists(p):
            return joblib.load(p)
    raise FileNotFoundError("Modelo .pkl não encontrado!")

model = load_model()

# =====================
# 2. Interface Lateral (Inputs)
# =====================
st.sidebar.header("🏗️ Parâmetros da Obra")
with st.sidebar:
    obra = st.text_input("Nome do Empreendimento", "Residencial MRV Prime")
    # Nota: Mapeie estes sliders para as 4 primeiras variáveis que usaste no treino
    val1 = st.slider("Orçamento Estimado (Escalado)", 0, 1000, 500)
    val2 = st.slider("Rating de Confiabilidade (0-10)", 0, 10, 7)
    val3 = st.slider("Taxa de Insucesso Fornecedor (0-100)", 0, 100, 10)
    val4 = st.slider("Risco da Etapa (0-10)", 0, 10, 5)

# =====================
# 3. Painel Principal
# =====================
st.title("🛡️ Sistema de Antecipação de Riscos - MRV")
st.markdown(f"Análise preditiva para a obra: **{obra}**")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Previsão Atual")
    if st.button("🚀 Calcular Risco"):
        # SOLUÇÃO PARA O ERRO: Criar array de 20 colunas com zeros
        X_input = np.zeros((1, 20))
        
        # Preencher as 4 primeiras posições com os valores dos sliders
        X_input[0, 0] = val1
        X_input[0, 1] = val2
        X_input[0, 2] = val3
        X_input[0, 3] = val4
        
        # Realizar a previsão
        predicao = model.predict(X_input)[0]
        
        st.metric(label="Atraso Estimado", value=f"{predicao:.1f} Dias")
        
        if predicao > 10:
            st.error("Risco Crítico!")
        elif predicao > 5:
            st.warning("Risco Moderado")
        else:
            st.success("Operação Normal")

with col2:
    st.subheader("📈 Análise de Sensibilidade")
    
    # Gerar variação para o gráfico (Ex: variando o Orçamento ou Chuva na coluna 0)
    eixo_x = list(range(0, 1001, 50))
    matriz_cenarios = np.zeros((len(eixo_x), 20))
    
    for i, v in enumerate(eixo_x):
        matriz_cenarios[i, 0] = v  # Varia o primeiro parâmetro
        matriz_cenarios[i, 1] = val2
        matriz_cenarios[i, 2] = val3
        matriz_cenarios[i, 3] = val4
    
    # Prever para todos os cenários da matriz de 20 colunas
    previsoes = model.predict(matriz_cenarios)
    
    df_plot = pd.DataFrame({
        'Variável': eixo_x,
        'Atraso': previsoes
    })
    
    fig = px.line(df_plot, x='Variável', y='Atraso', title="Impacto no Cronograma")
    
    # Ponto atual (também com 20 colunas)
    X_atual = np.zeros((1, 20))
    X_atual[0, 0:4] = [val1, val2, val3, val4]
    pred_atual = model.predict(X_atual)[0]
    
    fig.add_scatter(x=[val1], y=[pred_atual], name="Atual", marker=dict(size=12, color='red'))
    
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("Desenvolvido por Sérgio Santos | Ciência de Dados Aplicada")


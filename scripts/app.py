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
    # Procura o modelo nos caminhos possíveis (Cloud e Local)
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
    c1 = st.slider("Dias de Chuva (Previsão)", 0, 30, 5)
    c2 = st.slider("Rating do Fornecedor (0-10)", 0, 10, 7)
    c3 = st.slider("Mão de Obra (Nº de Funcionários)", 5, 150, 50)
    c4 = st.slider("% Atraso na Entrega de Materiais", 0, 100, 10)

# Criamos uma lista com os valores (Ordem: Chuva, Fornecedor, Equipe, Materiais)
dados_puros = [[c1, c2, c3, c4]]

# =====================
# 3. Painel Principal
# =====================
st.title("🛡️ Sistema de Antecipação de Riscos - MRV")
st.markdown(f"Análise preditiva para a obra: **{obra}**")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Previsão Atual")
    if st.button("🚀 Calcular Risco"):
        # O segredo: Converter para numpy array ANTES de prever
        X = np.array(dados_puros)
        predicao = model.predict(X)[0]
        
        st.metric(label="Atraso Estimado", value=f"{predicao:.1f} Dias")
        
        if predicao > 10: st.error("Risco Crítico!")
        elif predicao > 5: st.warning("Risco Moderado")
        else: st.success("Operação Normal")

with col2:
    st.subheader("📈 Análise de Sensibilidade")
    
    # Criar cenários variando apenas a chuva
    dias_chuva = list(range(0, 31))
    matriz_cenarios = []
    for d in dias_chuva:
        matriz_cenarios.append([d, c2, c3, c4])
    
    # Prever usando a matriz para evitar o erro de colunas da linha 71
    X_cenarios = np.array(matriz_cenarios)
    previsoes = model.predict(X_cenarios)
    
    df_plot = pd.DataFrame({
        'Dias de Chuva': dias_chuva,
        'Atraso': previsoes
    })
    
    fig = px.line(df_plot, x='Dias de Chuva', y='Atraso', title="Impacto do Clima")
    
    # Ponto atual
    pred_atual = model.predict(np.array(dados_puros))[0]
    fig.add_scatter(x=[c1], y=[pred_atual], name="Atual", marker=dict(size=12, color='red'))
    
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("Desenvolvido por Sérgio Santos | Ciência de Dados Aplicada")

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
    # Caminho para o Streamlit Cloud encontrar o arquivo .pkl
    path = "models/modelo_random_forest.pkl"
    if not os.path.exists(path):
        path = "../models/modelo_random_forest.pkl"
    return joblib.load(path)

model = load_model()

# =====================
# 2. Interface Lateral (Inputs)
# =====================
st.sidebar.header("🏗️ Parâmetros da Obra")

with st.sidebar:
    obra = st.text_input("Nome do Empreendimento", "Residencial MRV Prime")
    v1 = st.slider("Dias de Chuva (Previsão)", 0, 30, 5)
    v2 = st.slider("Rating do Fornecedor (0-10)", 0, 10, 7)
    v3 = st.slider("Mão de Obra (Nº de Funcionários)", 5, 150, 50)
    v4 = st.slider("% Atraso na Entrega de Materiais", 0, 100, 10)

# Criamos uma lista simples com os valores (sem nomes de colunas)
# A ORDEM deve ser a mesma que você usou para treinar o modelo
dados_entrada = [[v1, v2, v3, v4]]

# =====================
# 3. Painel Principal
# =====================
st.title("🛡️ Sistema de Antecipação de Riscos - MRV")
st.markdown(f"Análise preditiva para a obra: **{obra}**")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Previsão Atual")
    if st.button("🚀 Calcular Risco"):
        # USAMOS np.array().reshape para garantir que o modelo receba os dados corretamente
        predicao = model.predict(np.array(dados_entrada))[0]
        
        st.metric(label="Atraso Estimado", value=f"{predicao:.1f} Dias")
        
        if predicao > 10:
            st.error("Risco Crítico Detectado!")
        elif predicao > 5:
            st.warning("Atenção: Risco Moderado")
        else:
            st.success("Operação dentro da normalidade")

with col2:
    st.subheader("📈 Análise de Sensibilidade")
    
    # Gerar cenários variando apenas a chuva (v1)
    eixo_x = list(range(0, 31))
    lista_cenarios = []
    for x in eixo_x:
        lista_cenarios.append([x, v2, v3, v4])
    
    # Prever todos de uma vez usando a matriz numérica
    previsoes_cenarios = model.predict(np.array(lista_cenarios))
    
    df_grafico = pd.DataFrame({
        'Dias de Chuva': eixo_x,
        'Atraso': previsoes_cenarios
    })
    
    fig = px.line(df_grafico, x='Dias de Chuva', y='Atraso',
                  title="Impacto do Clima no Cronograma",
                  labels={'Atraso': 'Dias de Atraso Previstos'})
    
    # Ponto atual
    pred_atual = model.predict(np.array(dados_entrada))[0]
    fig.add_scatter(x=[v1], y=[pred_atual], 
                    name="Cenário Atual", marker=dict(size=15, color='red'))
    
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("Desenvolvido por Sérgio Santos | Ciência de Dados Aplicada")

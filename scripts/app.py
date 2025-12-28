import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
import numpy as np

# Configuração da Página
st.set_page_config(page_title="MRV - Predictive Risk", layout="wide")

# =====================
# 1. Carregamento do Modelo
# =====================
@st.cache_resource
def load_model():
    # Caminho ajustado para o Streamlit Cloud (lê da raiz)
    return joblib.load("models/modelo_random_forest.pkl")

model = load_model()

# =====================
# 2. Interface Lateral (Inputs)
# =====================
st.sidebar.header("🏗️ Parâmetros da Obra")

with st.sidebar:
    obra = st.text_input("Nome do Empreendimento", "Residencial MRV Prime")
    chuva = st.slider("Dias de Chuva (Previsão)", 0, 30, 5)
    fornecedor = st.slider("Rating do Fornecedor (0-10)", 0, 10, 7)
    equipe = st.slider("Mão de Obra (Nº de Funcionários)", 5, 150, 50)
    atraso_mat = st.slider("% Atraso na Entrega de Materiais", 0, 100, 10)

# Criar DataFrame para o modelo
# IMPORTANTE: A ordem abaixo deve ser EXATAMENTE a mesma do X_train no notebook
input_df = pd.DataFrame({
    'chuva_dias': [chuva],
    'fornecedor_score': [fornecedor],
    'mão_obra_qtd': [equipe],
    'material_atraso': [atraso_mat]
})

# =====================
# 3. Painel Principal
# =====================
st.title("🛡️ Sistema de Antecipação de Riscos - MRV")
st.markdown(f"Análise preditiva para a obra: **{obra}**")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Previsão Atual")
    if st.button("🚀 Calcular Risco"):
        # USAMOS .values para evitar o erro de nomes de colunas (Feature Names)
        predicao = model.predict(input_df.values)[0]
        st.metric(label="Atraso Estimado", value=f"{predicao:.1f} Dias")
        
        if predicao > 10:
            st.error("Risco Crítico Detectado!")
        elif predicao > 5:
            st.warning("Atenção: Risco Moderado")
        else:
            st.success("Operação dentro da normalidade")

with col2:
    st.subheader("📈 Análise de Sensibilidade (O que aconteceria se...?)")
    
    # Gerar cenário hipotético
    cenarios = pd.DataFrame({
        'chuva_dias': list(range(0, 31)),
        'fornecedor_score': fornecedor,
        'mão_obra_qtd': equipe,
        'material_atraso': atraso_mat
    })
    
    # Reordenar colunas e usar .values para garantir compatibilidade
    cenarios_input = cenarios[['chuva_dias', 'fornecedor_score', 'mão_obra_qtd', 'material_atraso']]
    cenarios['Atraso Previsto (Dias)'] = model.predict(cenarios_input.values)
    
    fig = px.line(cenarios, x='chuva_dias', y='Atraso Previsto (Dias)',
                  title="Impacto do Clima no Cronograma",
                  labels={'chuva_dias': 'Dias de Chuva no Mês'})
    
    # Destacar o ponto atual
    atual_pred = model.predict(input_df.values)[0]
    fig.add_scatter(x=[chuva], y=[atual_pred], 
                    name="Cenário Atual", marker=dict(size=15, color='red'))
    
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("Desenvolvido por Sérgio Santos | Ciência de Dados Aplicada")

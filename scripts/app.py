import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
import numpy as np
import os

# 1. Configuração da Página
st.set_page_config(
    page_title="Cons.Civil Risk Intelligence",
    page_icon="🏗️",
    layout="wide"
)

# Customização visual básica
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# =====================
# 1. Carregamento do Pipeline (IA)
# =====================
@st.cache_resource
def load_pipeline():
    # Prioriza o pipeline que contém o encoder + modelo
    path = "models/pipeline_random_forest.pkl"
    if os.path.exists(path):
        return joblib.load(path)
    raise FileNotFoundError("Pipeline de IA não encontrado em /models. Certifique-se de retreinar o modelo.")

pipeline = load_pipeline()

# =====================
# 2. Interface Lateral (Parâmetros)
# =====================
st.sidebar.header("🏗️ Painel de Controle de Riscos")

with st.sidebar:
    st.subheader("📍 Identificação")
    id_obra = st.text_input("ID da Obra", "MRV-100")
    cidade = st.selectbox("Cidade", ['Belo Horizonte', 'São Paulo', 'Rio de Janeiro', 'Curitiba', 'Salvador'])
    etapa = st.selectbox("Etapa da Obra", ['Fundação', 'Estrutura', 'Acabamento'])
    
    st.divider()
    st.subheader("🌦️ Condições de Campo")
    val_chuva = st.slider("Previsão de Chuva Mensal (mm)", 0, 500, 150, help="Impacto direto na drenagem e concretagem.")
    tipo_solo = st.selectbox("Geologia do Terreno (Solo)", ['Arenoso', 'Argiloso', 'Rochoso', 'Siltoso'])
    
    st.divider()
    st.subheader("💰 Gestão e Logística")
    val_orcamento = st.number_input("Orçamento Estimado (R$)", min_value=1000000, value=12000000)
    val_rating = st.slider("Rating de Confiabilidade Fornecedor", 0.0, 5.0, 3.5)
    material = st.selectbox("Material Principal em Uso", ['Cimento', 'Aço', 'Brita', 'Madeira', 'Piso', 'Tintas', 'Revestimento'])

# =====================
# 3. Preparação dos Dados para a IA
# =====================
# Criamos o DataFrame com as colunas EXATAMENTE como o modelo foi treinado no notebook
input_df = pd.DataFrame([{
    'orcamento_estimado': val_orcamento,
    'rating_confiabilidade': val_rating,
    'taxa_insucesso_fornecedor': 0.15, # Valor médio padrão
    'complexidade_obra': np.log1p(val_orcamento),
    'risco_etapa': 8.5, # Valor base histórico
    'nivel_chuva': val_chuva,
    'tipo_solo': tipo_solo,
    'material': material,
    'cidade': cidade,
    'etapa': etapa
}])

# =====================
# 4. Dashboard Principal
# =====================
st.title("🛡️ Sistema de Antecipação de Riscos - MRV")
st.caption(f"Análise preditiva em tempo real para: **{id_obra}**")

col1, col2, col3 = st.columns(3)

try:
    # Predição Única
    predicao_final = pipeline.predict(input_df)[0]
    
    with col1:
        st.metric("Atraso Estimado (IA)", f"{predicao_final:.1f} dias")
    with col2:
        confianca = "Alta" if val_rating > 4 else "Média"
        st.metric("Grau de Confiança", confianca)
    with col3:
        status = "Crítico" if predicao_final > 15 else "Alerta" if predicao_final > 7 else "Normal"
        st.metric("Status Operacional", status)

    st.divider()

    # Gráficos de Análise
    c_graf1, c_graf2 = st.columns(2)

    with c_graf1:
        st.subheader("📉 Sensibilidade: Chuva vs Atraso")
        # Simulação de variação de chuva para o gráfico
        range_chuva = np.linspace(0, 500, 20)
        cenarios = []
        for c in range_chuva:
            copy_df = input_df.copy()
            copy_df['nivel_chuva'] = c
            cenarios.append(copy_df)
        
        df_cenarios = pd.concat(cenarios)
        preds_chuva = pipeline.predict(df_cenarios)
        
        fig_chuva = px.line(
            x=range_chuva, 
            y=preds_chuva,
            labels={'x': 'Chuva (mm)', 'y': 'Dias de Atraso'},
            title=f"Relação Clima-Cronograma ({tipo_solo})",
            line_shape='spline'
        )
        fig_chuva.update_traces(line_color='#2E86C1')
        st.plotly_chart(fig_chuva, use_container_width=True)

    with c_graf2:
        st.subheader("🏗️ Riscos por Tipo de Solo")
        # Simulação de comparação de solos
        solos = ['Arenoso', 'Argiloso', 'Rochoso', 'Siltoso']
        cenarios_solo = []
        for s in solos:
            copy_df = input_df.copy()
            copy_df['tipo_solo'] = s
            cenarios_solo.append(copy_df)
        
        df_solos = pd.concat(cenarios_solo)
        preds_solo = pipeline.predict(df_solos)
        
        fig_solo = px.bar(
            x=solos, 
            y=preds_solo,
            labels={'x': 'Tipo de Solo', 'y': 'Atraso Estimado'},
            title="Impacto Geológico na Etapa Atual",
            color=preds_solo,
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig_solo, use_container_width=True)

    st.info(f"💡 **Recomendação:** Para a etapa de {etapa} em solo {tipo_solo}, cada 50mm de chuva extra pode impactar o cronograma em aproximadamente {(preds_chuva[-1] - preds_chuva[0])/10:.1f} dias.")

except Exception as e:
    st.error(f"Ocorreu um erro na predição: {e}")
    st.warning("Certifique-se de que o arquivo 'pipeline_random_forest.pkl' foi treinado com as colunas: nivel_chuva e tipo_solo.")


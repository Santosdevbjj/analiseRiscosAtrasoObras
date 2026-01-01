import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
import numpy as np
import os

# 1. Configuração da Página
st.set_page_config(
    page_title="CCbjj - Risk Intelligence",
    page_icon="🏗️",
    layout="wide"
)

# Estilização visual CCbjj
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #004A2F;
    }
    div[data-testid="stMetricValue"] { color: #004A2F; }
    </style>
    """, unsafe_allow_html=True)

# =====================
# 1. Carregamento de Recursos (Caminhos Atualizados)
# =====================
@st.cache_resource
def load_assets():
    # Carrega Modelo, Metadados e Base
    m_path = "models/pipeline_random_forest.pkl"
    f_path = "models/features_metadata.joblib"
    d_path = "data/processed/df_mestre_consolidado.csv"
    
    pipeline = joblib.load(m_path) if os.path.exists(m_path) else None
    features = joblib.load(f_path) if os.path.exists(f_path) else None
    df_base = pd.read_csv(d_path) if os.path.exists(d_path) else pd.DataFrame()
    
    return pipeline, features, df_base

pipeline, features_order, df_base = load_assets()

# =====================
# 2. Interface Lateral (Padronização Lowercase)
# =====================
st.sidebar.image("https://img.icons8.com/fluency/96/construction.png", width=80)
st.sidebar.header("🕹️ Painel de Controle CCbjj")

with st.sidebar:
    st.markdown("---")
    st.subheader("📍 Localização e Etapa")
    
    # Busca cidades da base, tratando nulos e padronizando para exibição
    if not df_base.empty:
        cidades_list = sorted([c.title() for c in df_base['cidade'].dropna().unique()])
        etapas_list = sorted([e.title() for e in df_base['etapa'].dropna().unique()])
    else:
        cidades_list, etapas_list = ['Belo Horizonte', 'São Paulo'], ['Fundação', 'Estrutura']

    cidade_ui = st.selectbox("Cidade do Empreendimento", cidades_list)
    etapa_ui = st.selectbox("Etapa Atual", etapas_list)
    
    st.divider()
    st.subheader("🌦️ Fatores Ambientais")
    val_chuva = st.slider("Previsão de Chuva (mm)", 0, 800, 150)
    tipo_solo_ui = st.selectbox("Geologia do Terreno", ['Arenoso', 'Argiloso', 'Rochoso', 'Siltoso'])
    
    st.divider()
    st.subheader("📦 Logística de Suprimentos")
    material_ui = st.selectbox("Insumo Crítico", ['Cimento', 'Aço', 'Brita', 'Madeira', 'Piso'])
    val_rating = st.slider("Rating do Fornecedor", 1.0, 5.0, 3.5)

# =====================
# 3. Lógica de Predição (Sincronização com o Modelo)
# =====================
st.title("🛡️ CCbjj - Sistema de Antecipação de Riscos")

if pipeline is None or features_order is None:
    st.error("❌ Erro: Ativos de IA não localizados na pasta /models. Rode o notebook primeiro.")
else:
    # 1. Preparar o DataFrame EXATAMENTE como o modelo foi treinado (Lowercase)
    input_dict = {
        'orcamento_estimado': 15000000.0,
        'rating_confiabilidade': float(val_rating),
        'taxa_insucesso_fornecedor': 0.15,
        'complexidade_obra': np.log1p(15000000.0),
        'risco_etapa': 8.5,
        'nivel_chuva': float(val_chuva),
        'tipo_solo': tipo_solo_ui.lower(),
        'material': material_ui.lower(),
        'cidade': cidade_ui.lower(),
        'etapa': etapa_ui.lower()
    }
    
    input_df = pd.DataFrame([input_dict])
    input_df = input_df[features_order] # Garante a ordem correta das colunas

    try:
        pred_dias = max(0, pipeline.predict(input_df)[0])
        
        # Dashboard de Métricas
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Atraso Estimado", f"{pred_dias:.1f} dias")
        with m2:
            status_cor = "🔴" if pred_dias > 12 else "🟡" if pred_dias > 7 else "🟢"
            label_status = "Crítico" if pred_dias > 12 else "Alerta" if pred_dias > 7 else "Normal"
            st.metric("Status do Cronograma", f"{status_cor} {label_status}")
        with m3:
            st.metric("Impacto Financeiro Est.", f"R$ {pred_dias * 5000:,.2f}")

        st.markdown("---")

        # 4. Gráficos de Simulação
        
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("📉 Sensibilidade Climática")
            chuvas = np.linspace(0, 800, 20)
            # Simulação eficiente
            sim_chuva = pd.concat([input_df.assign(nivel_chuva=c) for c in chuvas])
            preds_chuva = [max(0, p) for p in pipeline.predict(sim_chuva)]
            
            fig_chuva = px.area(x=chuvas, y=preds_chuva, 
                                labels={'x': 'Chuva (mm)', 'y': 'Atraso (Dias)'},
                                title="Impacto do Volume de Chuva",
                                color_discrete_sequence=['#004A2F'])
            st.plotly_chart(fig_chuva, use_container_width=True)

        with c2:
            st.subheader("⛰️ Comparativo Geológico")
            solos = ['arenoso', 'argiloso', 'rochoso', 'siltoso']
            sim_solo = pd.concat([input_df.assign(tipo_solo=s) for s in solos])
            preds_solo = [max(0, p) for p in pipeline.predict(sim_solo)]
            
            fig_solo = px.bar(x=[s.title() for s in solos], y=preds_solo,
                             labels={'x': 'Tipo de Solo', 'y': 'Atraso Previsto'},
                             title="Risco por Geologia",
                             color=preds_solo, color_continuous_scale='Greens')
            st.plotly_chart(fig_solo, use_container_width=True)

        st.success(f"💡 **Insight CCbjj:** Em solo **{tipo_solo_ui}**, o impacto da chuva é potencializado. Recomendamos revisar drenagem em **{cidade_ui}**.")

    except Exception as e:
        st.error(f"Erro na predição: {e}")

st.markdown("<br><hr><center>Desenvolvido para Portfólio Técnico - CCbjj Engenharia</center>", unsafe_allow_html=True)

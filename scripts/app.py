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

# Estilização institucional
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

@st.cache_resource
def load_assets():
    m_path = "models/pipeline_random_forest.pkl"
    f_path = "models/features_metadata.joblib"
    d_path = "data/processed/df_mestre_consolidado.csv"
    
    pipeline = joblib.load(m_path) if os.path.exists(m_path) else None
    features = joblib.load(f_path) if os.path.exists(f_path) else None
    df_base = pd.read_csv(d_path) if os.path.exists(d_path) else pd.DataFrame()
    
    return pipeline, features, df_base

pipeline, features_order, df_base = load_assets()

# =====================
# 2. Interface Lateral
# =====================
st.sidebar.image("https://img.icons8.com/fluency/96/construction.png", width=80)
st.sidebar.header("🕹️ Painel de Controle CCbjj")

with st.sidebar:
    st.markdown("---")
    if not df_base.empty:
        cidades_list = sorted([c.title() for c in df_base['cidade'].dropna().unique()])
        etapas_list = sorted([e.title() for e in df_base['etapa'].dropna().unique()])
        solos_list = sorted([s.title() for s in df_base['tipo_solo'].dropna().unique()])
        materiais_list = sorted([m.title() for m in df_base['material'].dropna().unique()])
    else:
        cidades_list, etapas_list = ['Recife', 'São Paulo'], ['Fundação', 'Estrutura']
        solos_list, materiais_list = ['Argiloso', 'Rochoso'], ['Cimento', 'Aço']

    cidade_ui = st.selectbox("Cidade", cidades_list)
    etapa_ui = st.selectbox("Etapa Atual", etapas_list)
    tipo_solo_ui = st.selectbox("Geologia", solos_list)
    material_ui = st.selectbox("Insumo Crítico", materiais_list)
    
    st.divider()
    val_chuva = st.slider("Previsão de Chuva (mm)", 0, 800, 150)
    val_rating = st.slider("Rating do Fornecedor", 1.0, 5.0, 3.5)

# =====================
# 3. Lógica de Predição
# =====================
st.title("🛡️ CCbjj - Sistema de Antecipação de Riscos")

if pipeline is None or features_order is None:
    st.warning("⚠️ Aguardando modelos de IA. Certifique-se de rodar o pipeline de treinamento.")
else:
    # Construção do input respeitando o contrato do modelo
    input_dict = {
        'orcamento_estimado': 15000000.0,
        'rating_confiabilidade': float(val_rating),
        'taxa_insucesso_fornecedor': 0.15, 
        'complexidade_obra': np.log1p(15000000.0),
        'nivel_chuva': float(val_chuva),
        'tipo_solo': tipo_solo_ui.lower(),
        'material': material_ui.lower(),
        'cidade': cidade_ui.lower(),
        'etapa': etapa_ui.lower()
    }
    
    # Criar DataFrame e garantir colunas do modelo (inclusive as faltantes)
    input_df = pd.DataFrame([input_dict])
    for col in features_order:
        if col not in input_df.columns:
            input_df[col] = 0 # Valor default para colunas extras do treino
    
    input_df = input_df[features_order]

    with st.spinner('Analisando cenários de risco...'):
        pred_dias = max(0, pipeline.predict(input_df)[0])
        
        # Dashboard Superior
        m1, m2, m3 = st.columns(3)
        m1.metric("Atraso Estimado", f"{pred_dias:.1f} dias")
        
        status_map = {
            "Crítico": ("🔴", pred_dias > 12),
            "Alerta": ("🟡", 7 < pred_dias <= 12),
            "Normal": ("🟢", pred_dias <= 7)
        }
        label = [k for k, v in status_map.items() if v[1]][0]
        m2.metric("Status do Cronograma", f"{status_map[label][0]} {label}")
        m3.metric("Impacto Financeiro Est.", f"R$ {pred_dias * 3500:,.2f}")

    st.markdown("---")

    # 4. Gráficos de Simulação
    
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📉 Sensibilidade Climática")
        faixa_chuva = np.linspace(0, 800, 20)
        sim_chuva = pd.concat([input_df.assign(nivel_chuva=c) for c in faixa_chuva])
        preds_chuva = [max(0, p) for p in pipeline.predict(sim_chuva)]
        fig_chuva = px.area(x=faixa_chuva, y=preds_chuva, 
                            labels={'x': 'Chuva (mm)', 'y': 'Atraso (Dias)'},
                            color_discrete_sequence=['#004A2F'])
        st.plotly_chart(fig_chuva, use_container_width=True)

    with c2:
        st.subheader("⛰️ Risco por Geologia")
        solos_ref = ['arenoso', 'argiloso', 'rochoso', 'siltoso']
        sim_solo = pd.concat([input_df.assign(tipo_solo=s) for s in solos_ref])
        preds_solo = [max(0, p) for p in pipeline.predict(sim_solo)]
        fig_solo = px.bar(x=[s.title() for s in solos_ref], y=preds_solo,
                         color=preds_solo, color_continuous_scale='Greens')
        st.plotly_chart(fig_solo, use_container_width=True)

    st.info(f"💡 **Insight:** Obra em solo **{tipo_solo_ui}** sob chuva de **{val_chuva}mm** requer reforço logístico em **{material_ui}**.")

st.markdown("<br><hr><center>Desenvolvido para Portfólio Técnico - CCbjj Engenharia</center>", unsafe_allow_html=True)

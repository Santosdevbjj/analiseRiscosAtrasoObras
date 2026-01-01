import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
import numpy as np
import os

# Configuração igual ao seu PDF
st.set_page_config(page_title="CCbjj - Risk Intelligence", page_icon="🏗️", layout="wide")

@st.cache_resource
def load_assets():
    # Caminhos relativos padrão
    m_path, f_path, d_path = "models/pipeline_random_forest.pkl", "models/features_metadata.joblib", "data/processed/df_mestre_consolidado.csv"
    pipeline = joblib.load(m_path) if os.path.exists(m_path) else None
    features = joblib.load(f_path) if os.path.exists(f_path) else None
    df = pd.read_csv(d_path) if os.path.exists(d_path) else pd.DataFrame()
    return pipeline, features, df

pipeline, features_order, df_base = load_assets()

# --- Interface Lateral ---
with st.sidebar:
    st.header("🕹️ Painel de Controle CCbjj")
    # Proteção contra listas vazias (o que causou seu erro anterior)
    def get_options(col, default):
        if not df_base.empty and col in df_base.columns:
            opts = [str(x).title() for x in df_base[col].dropna().unique() if str(x).lower() != 'nan']
            if opts: return sorted(opts)
        return default

    cidade_ui = st.selectbox("Cidade", get_options('cidade', ['Recife', 'São Paulo']))
    etapa_ui = st.selectbox("Etapa Atual", get_options('etapa', ['Fundação', 'Estrutura']))
    solo_ui = st.selectbox("Geologia", get_options('tipo_solo', ['Argiloso', 'Rochoso']))
    material_ui = st.selectbox("Insumo Crítico", get_options('material', ['Cimento', 'Aço']))
    
    val_chuva = st.slider("Previsão de Chuva (mm)", 0, 800, 150)
    val_rating = st.slider("Rating de Confiança", 1.0, 5.0, 3.5)

# --- Título e Predição ---
st.title("🛡️ CCbjj - Sistema de Antecipação de Riscos")

if pipeline is None or features_order is None:
    st.error("Modelos não encontrados. Verifique a pasta /models no GitHub.")
else:
    # Preparação do Input (Respeitando o contrato do modelo)
    input_dict = {
        'orcamento_estimado': 15000000.0,
        'rating_confiabilidade': float(val_rating),
        'taxa_insucesso_fornecedor': 0.15,
        'complexidade_obra': np.log1p(15000000.0),
        'risco_etapa': 5.0,
        'nivel_chuva': float(val_chuva),
        'tipo_solo': solo_ui.lower(),
        'material': material_ui.lower(),
        'cidade': cidade_ui.lower(),
        'etapa': etapa_ui.lower(),
        'id_obra': 'PRED-01'
    }
    
    input_df = pd.DataFrame([input_dict])
    for col in features_order:
        if col not in input_df.columns: input_df[col] = 0
    input_df = input_df[features_order]

    # Resultado (Dashboard do PDF)
    pred_dias = pipeline.predict(input_df)[0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Atraso Estimado", f"{pred_dias:.1f} dias")
    m2.metric("Status do Cronograma", "Normal" if pred_dias < 7 else "Alerta")
    m3.metric("Impacto Financeiro Est.", f"R$ {pred_dias * 3500:,.2f}")

    # Gráficos (Simulação do PDF)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Sensibilidade Climática")
        chuvas = np.linspace(0, 800, 20)
        sim = pd.concat([input_df.assign(nivel_chuva=c) for c in chuvas])
        fig = px.area(x=chuvas, y=pipeline.predict(sim), labels={'x':'Chuva', 'y':'Dias'})
        st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        st.subheader("Risco por Geologia")
        solos = ['arenoso', 'argiloso', 'rochoso', 'siltoso']
        sim_s = pd.concat([input_df.assign(tipo_solo=s) for s in solos])
        fig_s = px.bar(x=[s.title() for s in solos], y=pipeline.predict(sim_s))
        st.plotly_chart(fig_s, use_container_width=True)

    st.info(f"Insight CCbjj: Para {cidade_ui}, solo {solo_ui} e chuva de {val_chuva}mm, o risco estimado é de {pred_dias:.1f} dias.")

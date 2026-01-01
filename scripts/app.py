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

# Estilização institucional CCbjj
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
# 1. Carregamento de Recursos
# =====================
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
# 2. Interface Lateral (Versão à Prova de Falhas)
# =====================
with st.sidebar:
    st.sidebar.image("https://img.icons8.com/fluency/96/construction.png", width=80)
    st.sidebar.header("🕹️ Painel de Controle CCbjj")
    st.markdown("---")
    
    def get_safe_options(df, column, default_values):
        if not df.empty and column in df.columns:
            options = df[column].dropna().unique().tolist()
            options = [str(x).title() for x in options if str(x).lower() != 'nan']
            if options:
                return sorted(options)
        return default_values

    # Listas de opções com Fallbacks caso o CSV venha com 'nan'
    cidades_list = get_safe_options(df_base, 'cidade', ['Recife', 'São Paulo', 'Manaus', 'Curitiba'])
    etapas_list = get_safe_options(df_base, 'etapa', ['Fundação', 'Estrutura', 'Acabamento'])
    solos_list = get_safe_options(df_base, 'tipo_solo', ['Argiloso', 'Arenoso', 'Rochoso', 'Siltoso'])
    materiais_list = get_safe_options(df_base, 'material', ['Cimento', 'Aço', 'Areia', 'Brita'])

    cidade_ui = st.selectbox("Cidade do Empreendimento", cidades_list)
    etapa_ui = st.selectbox("Etapa Atual", etapas_list)
    tipo_solo_ui = st.selectbox("Geologia do Terreno", solos_list)
    material_ui = st.selectbox("Insumo Crítico", materiais_list)
    
    st.divider()
    val_chuva = st.slider("Previsão de Chuva (mm)", 0, 800, 150)
    val_rating = st.slider("Rating de Confiança do Fornecedor", 1.0, 5.0, 3.5)

# =====================
# 3. Lógica de Predição
# =====================
st.title("🛡️ CCbjj - Sistema de Antecipação de Riscos")
st.markdown("*Inteligência Artificial aplicada ao controle de cronogramas e mitigação de atrasos.*")

if pipeline is None or features_order is None:
    st.error("❌ Ativos de IA (models/) não localizados. Certifique-se de que o treinamento foi concluído.")
else:
    # Sanitização dos inputs (Garante que nunca seja None para o .lower())
    cidade_val = str(cidade_ui).lower() if cidade_ui else "recife"
    etapa_val = str(etapa_ui).lower() if etapa_ui else "fundação"
    solo_val = str(tipo_solo_ui).lower() if tipo_solo_ui else "argiloso"
    material_val = str(material_ui).lower() if material_ui else "cimento"

    input_dict = {
        'orcamento_estimado': 15000000.0,
        'rating_confiabilidade': float(val_rating),
        'taxa_insucesso_fornecedor': 0.15,
        'complexidade_obra': np.log1p(15000000.0),
        'risco_etapa': 5.0,
        'nivel_chuva': float(val_chuva),
        'tipo_solo': solo_val,
        'material': material_val,
        'cidade': cidade_val,
        'etapa': etapa_val,
        'id_obra': 'PREDICT_MODE'
    }
    
    # Criar DataFrame e Sincronizar Colunas
    input_df = pd.DataFrame([input_dict])
    for col in features_order:
        if col not in input_df.columns:
            input_df[col] = 0
    
    input_df = input_df[features_order]

    try:
        with st.spinner('Analisando cenários...'):
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
                st.metric("Impacto Financeiro Est.", f"R$ {pred_dias * 3500:,.2f}")

        st.markdown("---")

        # 4. Gráficos de Simulação
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("📉 Sensibilidade Climática")
            faixa_chuva = np.linspace(0, 800, 20)
            sim_chuva = pd.concat([input_df.assign(nivel_chuva=c) for c in faixa_chuva])
            preds_chuva = [max(0, p) for p in pipeline.predict(sim_chuva)]
            fig_chuva = px.area(x=faixa_chuva, y=preds_chuva, 
                                labels={'x': 'Precipitação (mm)', 'y': 'Atraso (Dias)'},
                                color_discrete_sequence=['#004A2F'])
            st.plotly_chart(fig_chuva, use_container_width=True)

        with c2:
            st.subheader("⛰️ Risco por Geologia")
            solos_ref = ['arenoso', 'argiloso', 'rochoso', 'siltoso']
            sim_solo = pd.concat([input_df.assign(tipo_solo=s) for s in solos_ref])
            preds_solo = [max(0, p) for p in pipeline.predict(sim_solo)]
            fig_solo = px.bar(x=[s.title() for s in solos_ref], y=preds_solo,
                             labels={'x': 'Tipo de Solo', 'y': 'Dias de Atraso'},
                             color=preds_solo, color_continuous_scale='Greens')
            st.plotly_chart(fig_solo, use_container_width=True)

        st.success(f"💡 **Insight CCbjj:** Para {cidade_ui}, solo {tipo_solo_ui} e chuva de {val_chuva}mm, o risco estimado é de {pred_dias:.1f} dias.")

    except Exception as e:
        st.error(f"Erro de compatibilidade: {e}")

st.markdown("<br><hr><center>Desenvolvido para Portfólio Técnico - CCbjj Engenharia</center>", unsafe_allow_html=True)

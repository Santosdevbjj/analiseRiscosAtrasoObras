import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
import numpy as np
import os

# 1. CONFIGURAÇÃO DA PÁGINA (Padrão Executivo)
st.set_page_config(
    page_title="CCbjj - Risk Intelligence Dashboard", 
    page_icon="🏗️", 
    layout="wide"
)

# Estilização CSS para um visual profissional
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stMetric label { font-weight: bold; color: #1B5E20; }
    </style>
    """, unsafe_allow_html=True)

# 2. CARREGAMENTO DE ASSETS (Otimizado com caminhos absolutos)
@st.cache_resource
def load_assets():
    # Define a base do projeto para evitar erros de caminho no Streamlit Cloud
    base_path = os.getcwd()
    m_path = os.path.join(base_path, "models", "pipeline_random_forest.pkl")
    f_path = os.path.join(base_path, "models", "features_metadata.joblib")
    d_path = os.path.join(base_path, "data", "processed", "df_mestre_consolidado.csv.gz")
    
    pipeline = joblib.load(m_path) if os.path.exists(m_path) else None
    features = joblib.load(f_path) if os.path.exists(f_path) else None
    
    if os.path.exists(d_path):
        df = pd.read_csv(d_path, compression='gzip')
    else:
        # Fallback para CSV comum se o GZ não existir
        alt_path = d_path.replace(".gz", "")
        df = pd.read_csv(alt_path) if os.path.exists(alt_path) else pd.DataFrame()
        
    return pipeline, features, df

pipeline, features_order, df_base = load_assets()

# --- INTERFACE LATERAL (PAINEL DE CONTROLE) ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/construction.png", width=80)
    st.title("🕹️ Parâmetros da Obra")
    st.markdown("Ajuste as variáveis para simulação em tempo real.")
    
    def get_options(col, default_list):
        if not df_base.empty and col in df_base.columns:
            opts = [str(x).title() for x in df_base[col].unique() if pd.notna(x)]
            return sorted(opts)
        return default_list

    cidade_ui = st.selectbox("Localização", get_options('cidade', ['Recife', 'São Paulo']))
    etapa_ui = st.selectbox("Etapa Construtiva", get_options('etapa', ['Fundação', 'Estrutura', 'Acabamento']))
    solo_ui = st.selectbox("Geologia do Terreno", get_options('tipo_solo', ['Argiloso', 'Arenoso', 'Rochoso']))
    material_ui = st.selectbox("Insumo Crítico", get_options('material', ['Cimento', 'Aço', 'Brita']))
    
    st.markdown("---")
    val_chuva = st.slider("Previsão Pluviométrica (mm)", 0, 800, 150)
    val_rating = st.select_slider("Rating de Confiança do Fornecedor", options=[1, 2, 3, 4, 5], value=3)

# --- CORPO DO DASHBOARD ---
st.title("🛡️ CCBJJ Risk Intelligence 2.0")
st.caption("Sistema Preditivo de Atrasos para Decisão de Diretoria e Logística")
st.markdown("---")

if pipeline is None or features_order is None:
    st.error("🚨 **Atenção:** Ativos da IA não encontrados na pasta `/models`. Verifique o deploy no GitHub.")
else:
    try:
        # Extração de Médias de Contexto do Banco de Dados
        if not df_base.empty:
            contexto = df_base[(df_base['cidade'] == cidade_ui.lower()) & (df_base['etapa'] == etapa_ui.lower())]
            if not contexto.empty:
                orcamento = contexto['orcamento_estimado'].mean()
                complexidade = contexto['complexidade_obra'].mean()
                risco_etapa = contexto['risco_etapa'].mean()
                taxa_forn = contexto['taxa_insucesso_fornecedor'].mean()
            else:
                orcamento, complexidade, risco_etapa, taxa_forn = 12000000.0, 15.0, 5.0, 0.12
        else:
            orcamento, complexidade, risco_etapa, taxa_forn = 10000000.0, 10.0, 4.0, 0.10

        # Montagem do DataFrame de Predição (Contrato com o Modelo)
        input_dict = {
            'orcamento_estimado': float(orcamento),
            'rating_confiabilidade': float(val_rating),
            'taxa_insucesso_fornecedor': float(taxa_forn),
            'complexidade_obra': float(complexidade),
            'risco_etapa': float(risco_etapa),
            'nivel_chuva': float(val_chuva),
            'tipo_solo': solo_ui.lower(),
            'material': material_ui.lower(),
            'cidade': cidade_ui.lower(),
            'etapa': etapa_ui.lower()
        }
        
        input_df = pd.DataFrame([input_dict])
        # Alinha colunas e preenche faltantes (dummy variables do modelo)
        for col in features_order:
            if col not in input_df.columns:
                input_df[col] = 0
        input_df = input_df[features_order]

        # Execução da Predição
        pred_dias = float(pipeline.predict(input_df)[0])
        pred_dias = max(0, pred_dias)

        # MÉTRICAS PRINCIPAIS
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Atraso Estimado", f"{pred_dias:.1f} Dias")
        with m2:
            status = "🔴 Crítico" if pred_dias > 10 else "🟡 Alerta" if pred_dias > 6 else "🟢 Estável"
            st.metric("Status do Risco", status)
        with m3:
            # Estimativa de custo de atraso: R$ 5.000,00 por dia (exemplo)
            st.metric("Custo de Oportunidade", f"R$ {pred_dias * 5000:,.2f}")

        st.markdown("### 📈 Análises de Sensibilidade")
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Simulação de Chuva vs. Atraso")
            faixa_chuva = np.linspace(0, 800, 20)
            # Simulação rápida criando cópias do dataframe
            sim_chuva = pd.concat([input_df.assign(nivel_chuva=c) for c in faixa_chuva])
            preds_chuva = pipeline.predict(sim_chuva)
            
            fig_chuva = px.line(x=faixa_chuva, y=preds_chuva, 
                               labels={'x': 'Nível de Chuva (mm)', 'y': 'Dias de Atraso'},
                               markers=True, template="plotly_white")
            fig_chuva.update_traces(line_color='#2E7D32')
            st.plotly_chart(fig_chuva, use_container_width=True)

        with col_b:
            st.subheader("Impacto por Geologia")
            tipos_solo = ['arenoso', 'argiloso', 'rochoso', 'siltoso']
            # Simulação por categoria de solo
            sim_solo = pd.concat([input_df.assign(tipo_solo=s) for s in tipos_solo])
            preds_solo = pipeline.predict(sim_solo)
            
            fig_solo = px.bar(x=[s.title() for s in tipos_solo], y=preds_solo,
                             labels={'x': 'Geologia', 'y': 'Atraso Estimado'},
                             color=preds_solo, color_continuous_scale='Greens')
            st.plotly_chart(fig_solo, use_container_width=True)

        st.success(f"📌 **Insight Técnico:** A combinação de solo **{solo_ui}** com previsão de **{val_chuva}mm** de chuva indica atenção especial na etapa de **{etapa_ui}**.")

    except Exception as e:
        st.error(f"Erro no processamento da IA: {e}")

st.markdown("<br><hr><center><b>CCBJJ Engenharia & Inteligência de Risco v2.0</b> | Inteligência Artificial Aplicada à Construção Civil | Desenvolvido por Sérgio Santos</center>", unsafe_allow_html=True)

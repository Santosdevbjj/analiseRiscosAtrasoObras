import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
import numpy as np
import os

# 1. Configuração da Página
st.set_page_config(page_title="CCbjj - Risk Intelligence", page_icon="🏗️", layout="wide")

@st.cache_resource
def load_assets():
    m_path = "models/pipeline_random_forest.pkl"
    f_path = "models/features_metadata.joblib"
    # IMPORTANTE: Caminho para o arquivo compactado gerado na célula 18
    d_path = "data/processed/df_mestre_consolidado.csv.gz" 
    
    pipeline = joblib.load(m_path) if os.path.exists(m_path) else None
    features = joblib.load(f_path) if os.path.exists(f_path) else None
    
    # Leitura com descompactação automática
    if os.path.exists(d_path):
        df = pd.read_csv(d_path, compression='gzip')
    else:
        # Tenta ler o CSV normal caso o .gz ainda não exista
        alt_path = d_path.replace(".gz", "")
        df = pd.read_csv(alt_path) if os.path.exists(alt_path) else pd.DataFrame()
        
    return pipeline, features, df

pipeline, features_order, df_base = load_assets()

# --- Interface Lateral ---
with st.sidebar:
    st.sidebar.image("https://img.icons8.com/fluency/96/construction.png", width=60)
    st.header("🕹️ Painel de Controle CCbjj")
    
    def get_options(col, default):
        if not df_base.empty and col in df_base.columns:
            opts = [str(x).title() for x in df_base[col].unique() if str(x).lower() != 'nan' and pd.notna(x)]
            if opts: return sorted(opts)
        return default

    cidade_ui = st.selectbox("Cidade", get_options('cidade', ['Recife', 'São Paulo']))
    etapa_ui = st.selectbox("Etapa Atual", get_options('etapa', ['Fundação', 'Estrutura', 'Acabamento']))
    solo_ui = st.selectbox("Geologia", get_options('tipo_solo', ['Argiloso', 'Arenoso', 'Rochoso', 'Siltoso']))
    material_ui = st.selectbox("Insumo Crítico", get_options('material', ['Cimento', 'Aço', 'Areia', 'Brita', 'Madeira']))
    
    val_chuva = st.slider("Previsão de Chuva (mm)", 0, 800, 150)
    val_rating = st.slider("Rating de Confiança", 1.0, 5.0, 3.5)

# --- Título e Predição ---
st.title("🛡️ CCbjj - Sistema de Antecipação de Riscos")
st.markdown("---")

if pipeline is None or features_order is None:
    st.error("❌ Modelos não encontrados na pasta /models. Verifique seu repositório GitHub.")
else:
    try:
        # --- BUSCA DINÂMICA DE DADOS ---
        if not df_base.empty:
            filtro = (df_base['cidade'] == cidade_ui.lower()) & (df_base['etapa'] == etapa_ui.lower())
            dados_contexto = df_base[filtro]
            
            if not dados_contexto.empty:
                orcamento = dados_contexto['orcamento_estimado'].mean()
                complexidade = dados_contexto['complexidade_obra'].mean()
                risco_etapa = dados_contexto['risco_etapa'].mean()
                taxa_forn = dados_contexto['taxa_insucesso_fornecedor'].mean()
            else:
                orcamento = df_base['orcamento_estimado'].median()
                complexidade = df_base['complexidade_obra'].median()
                risco_etapa = df_base['risco_etapa'].median()
                taxa_forn = 0.15
        else:
            orcamento, complexidade, risco_etapa, taxa_forn = 15000000.0, 16.5, 6.6, 0.15

        # Preparação do Input
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
            'etapa': etapa_ui.lower(),
            'id_obra': 'PRED-CCBJJ'
        }
        
        input_df = pd.DataFrame([input_dict])
        
        # Alinhamento de colunas com o modelo
        for col in features_order:
            if col not in input_df.columns:
                input_df[col] = 0
        input_df = input_df[features_order]

        # Predição Real
        pred_array = pipeline.predict(input_df)
        pred_dias = max(0, float(pred_array[0]))
        
        # Dashboard de Métricas
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Atraso Estimado", f"{pred_dias:.1f} dias")
        with m2:
            status = "🔴 Crítico" if pred_dias > 12 else "🟡 Alerta" if pred_dias > 7 else "🟢 Normal"
            st.metric("Status do Cronograma", status)
        with m3:
            st.metric("Impacto Financeiro Est.", f"R$ {pred_dias * 3500:,.2f}")

        # Gráficos de Simulação
        st.markdown("### 📊 Análise de Sensibilidade")
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Sensibilidade Climática")
            faixa_chuva = np.linspace(0, 800, 20)
            df_sim_chuva = pd.concat([input_df.assign(nivel_chuva=c) for c in faixa_chuva]) 
            preds_chuva = pipeline.predict(df_sim_chuva)
            fig_chuva = px.area(x=faixa_chuva, y=preds_chuva, 
                               labels={'x':'Chuva (mm)', 'y':'Atraso (Dias)'},
                               color_discrete_sequence=['#004A2F'])
            st.plotly_chart(fig_chuva, use_container_width=True)
        
        with c2:
            st.subheader("Risco por Geologia")
            solos_teste = ['arenoso', 'argiloso', 'rochoso', 'siltoso']
            df_sim_solo = pd.concat([input_df.assign(tipo_solo=s) for s in solos_teste])
            preds_solo = pipeline.predict(df_sim_solo)
            fig_solo = px.bar(x=[s.title() for s in solos_teste], y=preds_solo,
                             labels={'x':'Tipo de Solo', 'y':'Dias de Atraso'},
                             color=preds_solo, color_continuous_scale='Greens')
            st.plotly_chart(fig_solo, use_container_width=True)

        st.info(f"**Insight CCbjj:** Para {cidade_ui}, solo {solo_ui} e chuva de {val_chuva}mm, o risco estimado é de {pred_dias:.1f} dias.")

    except Exception as e:
        st.error(f"Erro no processamento da IA: {e}")

st.markdown("<br><hr><center>Desenvolvido por Sergio Santos,para Portfólio Técnico - CCbjj Engenharia</center>", unsafe_allow_html=True)

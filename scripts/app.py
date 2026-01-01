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

# Customização visual para as cores da CCbjj (Verde e Azul Profissional)
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #004A2F;
    }
    div[data-testid="stMetricValue"] {
        color: #004A2F;
    }
    </style>
    """, unsafe_allow_html=True)

# =====================
# 1. Carregamento de Recursos
# =====================
@st.cache_resource
def load_pipeline():
    path = "models/pipeline_random_forest.pkl"
    if os.path.exists(path):
        return joblib.load(path)
    return None

@st.cache_data
def load_base_data():
    path = "data/raw/base_consulta_botccbjj.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

pipeline = load_pipeline()
df_base = load_base_data()

# =====================
# 2. Interface Lateral (Parâmetros)
# =====================
st.sidebar.image("https://img.icons8.com/fluency/96/construction.png", width=80)
st.sidebar.header("🕹️ Painel de Controle CCbjj")

with st.sidebar:
    st.markdown("---")
    st.subheader("📍 Localização e Etapa")
    
    # Busca dinamicamente as cidades e etapas da sua nova base CCbjj
    cidades_disponiveis = df_base['cidade'].unique() if not df_base.empty else ['Recife', 'São Paulo', 'Manaus']
    cidade = st.selectbox("Cidade do Empreendimento", sorted(cidades_disponiveis))
    
    etapa = st.selectbox("Etapa Atual", ['Fundação', 'Estrutura', 'Acabamento'])
    
    st.divider()
    st.subheader("🌦️ Fatores Ambientais")
    val_chuva = st.slider("Previsão de Chuva (mm)", 0, 600, 150)
    tipo_solo = st.selectbox("Geologia do Terreno", ['Arenoso', 'Argiloso', 'Rochoso', 'Siltoso'])
    
    st.divider()
    st.subheader("📦 Logística de Suprimentos")
    material = st.selectbox("Insumo Crítico", ['Cimento', 'Aço', 'Brita', 'Madeira', 'Piso', 'Tintas', 'Revestimento', 'Areia'])
    val_rating = st.slider("Rating do Fornecedor", 0.0, 5.0, 3.5, help="Nível de confiança histórica do fornecedor escolhido.")

# =====================
# 3. Cabeçalho e Disclaimer (Ética de Dados)
# =====================
st.title("🛡️ CCbjj - Sistema de Antecipação de Riscos")
st.markdown("""
    *Análise Preditiva de Cronograma para Engenharia e Construção Civil.*
    
    ---
    ⚠️ **Nota Legal:** Este sistema é um simulador de portfólio para estudos de Ciência de Dados. 
    Os dados e previsões são baseados em modelos estatísticos fictícios para demonstração técnica.
""")

# =====================
# 4. Lógica de Predição
# =====================
if pipeline is None:
    st.error("❌ Erro: Pipeline de IA não encontrado na pasta /models.")
else:
    # Preparação do dado conforme os novos CSVs analisados
    input_df = pd.DataFrame([{
        'orcamento_estimado': 15000000.0, # Valor médio baseado na sua base CCbjj
        'rating_confiabilidade': val_rating,
        'taxa_insucesso_fornecedor': 0.20,
        'complexidade_obra': 16.5, 
        'risco_etapa': 9.0,
        'nivel_chuva': val_chuva,
        'tipo_solo': tipo_solo,
        'material': material,
        'cidade': cidade,
        'etapa': etapa
    }])

    try:
        # Predição em Tempo Real
        pred_dias = pipeline.predict(input_df)[0]
        
        # Dashboard de Métricas
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Atraso Estimado", f"{pred_dias:.1f} dias")
        with m2:
            status_cor = "🔴" if pred_dias > 12 else "🟡" if pred_dias > 6 else "🟢"
            st.metric("Status do Cronograma", f"{status_cor} {'Crítico' if pred_dias > 12 else 'Alerta' if pred_dias > 6 else 'Normal'}")
        with m3:
            # Impacto Financeiro Estimado (Diferencial para Gestores)
            impacto_financeiro = pred_dias * 1250.0 # Exemplo: R$ 1250/dia de custo fixo extra
            st.metric("Impacto Financeiro Est.", f"R$ {impacto_financeiro:,.2f}")

        st.markdown("---")

        # Gráficos de Simulação de Cenários
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("📉 Sensibilidade Climática")
            # Simula impacto da chuva
            chuvas = np.linspace(0, 600, 15)
            cenarios = pd.concat([input_df.assign(nivel_chuva=c) for c in chuvas])
            preds = pipeline.predict(cenarios)
            
            fig_chuva = px.area(x=chuvas, y=preds, 
                               labels={'x': 'Precipitação (mm)', 'y': 'Dias de Atraso'},
                               title="Curva de Atraso por Volume de Chuva",
                               color_discrete_sequence=['#004A2F'])
            st.plotly_chart(fig_chuva, use_container_width=True)

        with c2:
            st.subheader("⛰️ Comparativo Geológico")
            solos = ['Arenoso', 'Argiloso', 'Rochoso', 'Siltoso']
            cenarios_s = pd.concat([input_df.assign(tipo_solo=s) for s in solos])
            preds_s = pipeline.predict(cenarios_s)
            
            fig_solo = px.bar(x=solos, y=preds_s, color=preds_s,
                             labels={'x': 'Solo', 'y': 'Atraso'},
                             title="Risco Estimado por Tipo de Solo",
                             color_continuous_scale='Greens')
            st.plotly_chart(fig_solo, use_container_width=True)

        # Insight de Negócio Final
        st.success(f"💡 **Decisão Recomendada:** Para a unidade em **{cidade}**, sob chuva de {val_chuva}mm, o modelo sugere reforçar o estoque de **{material}** e revisar o cronograma de drenagem da etapa de **{etapa}**.")

    except Exception as e:
        st.warning(f"Ajuste necessário: O modelo espera colunas que podem estar ausentes. Erro: {e}")

# Rodapé
st.markdown("<br><hr><center>Desenvolvido como Portfólio Técnico - CCbjj Engenharia</center>", unsafe_allow_html=True)

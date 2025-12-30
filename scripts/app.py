import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
import numpy as np
import os

# 1. Configuração da Página
st.set_page_config(page_title="MRV - Predictive Risk", layout="wide")

# =====================
# 1. Carregamento do Recurso (PIPELINE é a chave aqui)
# =====================
@st.cache_resource
def load_resource():
    # Priorizamos o PIPELINE pois ele trata as 20 colunas internamente
    path = "models/pipeline_random_forest.pkl"
    if os.path.exists(path):
        return joblib.load(path)
    # Fallback para o modelo simples se o pipeline não existir
    path_model = "models/modelo_random_forest.pkl"
    if os.path.exists(path_model):
        return joblib.load(path_model)
    raise FileNotFoundError("Nenhum modelo ou pipeline encontrado em /models!")

model = load_resource()

# =====================
# 2. Interface Lateral
# =====================
st.sidebar.header("🏗️ Parâmetros da Obra")
with st.sidebar:
    obra_nome = st.text_input("Nome do Empreendimento", "Residencial MRV Prime")
    val_orcamento = st.slider("Orçamento Estimado (R$)", 5_000_000, 20_000_000, 10_000_000)
    val_rating = st.slider("Rating de Confiabilidade (0-5)", 0.0, 5.0, 3.5)
    val_insucesso = st.slider("Taxa de Insucesso Fornecedor (0-1)", 0.0, 1.0, 0.2)
    val_risco_etapa = st.slider("Risco Base da Etapa", 0.0, 15.0, 8.0)
    
    # Inputs Categóricos para completar as 20 colunas
    cidade = st.selectbox("Cidade", ['Belo Horizonte', 'São Paulo', 'Rio de Janeiro', 'Curitiba', 'Salvador'])
    etapa = st.selectbox("Etapa", ['Fundação', 'Estrutura', 'Acabamento'])
    material = st.selectbox("Material Crítico", ['Cimento', 'Aço', 'Brita', 'Madeira', 'Piso', 'Tintas', 'Revestimento'])

# =====================
# 3. Processamento e Predição
# =====================
# Criamos o DataFrame exatamente como o Pipeline espera
dados_input = pd.DataFrame([{
    'orcamento_estimado': val_orcamento,
    'rating_confiabilidade': val_rating,
    'taxa_insucesso_fornecedor': val_insucesso,
    'complexidade_obra': np.log1p(val_orcamento),
    'risco_etapa': val_risco_etapa,
    'material': material,
    'cidade': cidade,
    'etapa': etapa
}])

col1, col2 = st.columns(2)

with col1:
    st.subheader("🛡️ Previsão Real")
    # O Pipeline cuidará de transformar 'cidade', 'etapa' etc nas 20 colunas
    try:
        predicao = model.predict(dados_input)[0]
        st.metric(label="Atraso Estimado", value=f"{predicao:.1f} Dias")
        
        if predicao > 15: st.error("Risco Crítico!")
        elif predicao > 7: st.warning("Risco Moderado")
        else: st.success("Operação Normal")
    except Exception as e:
        st.error(f"Erro na predição: {e}")

with col2:
    st.subheader("📈 Análise de Sensibilidade")
    
    # Variação do orçamento para o gráfico
    eixo_x = np.linspace(5_000_000, 25_000_000, 20)
    cenarios = []
    
    for v in eixo_x:
        cenario = dados_input.copy()
        cenario['orcamento_estimado'] = v
        cenario['complexidade_obra'] = np.log1p(v)
        cenarios.append(cenario)
    
    df_cenarios = pd.concat(cenarios)
    
    try:
        previsoes = model.predict(df_cenarios)
        df_plot = pd.DataFrame({'Orçamento': eixo_x, 'Atraso Previsto': previsoes})
        fig = px.line(df_plot, x='Orçamento', y='Atraso Previsto', title="Impacto do Orçamento no Atraso")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.info("Ajuste o Pipeline para suportar múltiplos cenários.")

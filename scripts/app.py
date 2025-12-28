import streamlit as st
import pandas as pd
import joblib
import plotly.express as px

# ======================
# Carregar modelo
# ======================
@st.cache_resource
def load_model():
    return joblib.load("models/modelo_random_forest.pkl")

model = load_model()

# ======================
# Layout
# ======================
st.set_page_config(page_title="Previsão de Atraso de Obras — MRV", layout="wide")
st.title("🏗️ Previsão de Atraso de Obras — Demo Streamlit")
st.markdown("Esse app usa Machine Learning (Random Forest) para prever atraso de obras da MRV Engenharia.")

# ======================
# Sidebar — Entrada de Dados
# ======================
st.sidebar.header("Parâmetros da Obra")

obra = st.sidebar.text_input("Nome da Obra:", "Residencial Parque Bela Vista")
chuva_dias = st.sidebar.slider("Dias de Chuva no Mês", 0, 30, 12)
fornecedor_score = st.sidebar.slider("Qualidade do Fornecedor (0-10)", 0, 10, 6)
mão_obra_qtd = st.sidebar.slider("Número de Funcionários", 2, 200, 45)
material_atraso = st.sidebar.slider("% de atraso no material", 0, 100, 15)

# Criar DataFrame com os inputs
data = pd.DataFrame(
    {
        "chuva_dias": [chuva_dias],
        "fornecedor_score": [fornecedor_score],
        "mão_obra_qtd": [mão_obra_qtd],
        "material_atraso": [material_atraso],
    }
)

# ======================
# Previsão
# ======================
if st.button("⚡ Prever Risco de Atraso"):
    dias = model.predict(data)[0]
    st.metric(label="⏳ Dias de Atraso Previstos", value=f"{dias:.2f} dias")
    st.success("Recomendação: ajuste fornecedores e cronograma preventivamente 🚧")

# ======================
# Gráfico Exemplo
# ======================
st.subheader("📊 Exemplo — Ranking de Risco por Obra Integrado ao Modelo")

df_demo = pd.DataFrame({
    "obra": ["A", "B", "C", "D"],
    "atraso_previsto_dias": [8.5, 2.1, 12.0, 4.4]
})

fig = px.bar(df_demo, x="obra", y="atraso_previsto_dias", title="Previsão de atraso (dias)")
st.plotly_chart(fig, use_container_width=True)

st.caption("Modelo: RandomForestRegressor — métricas: MAE 4.97 dias | R² 0.41")

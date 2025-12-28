# ============================================================
# 12. Simulador de Risco – Exemplo de uso do modelo
# ============================================================

# Exemplo de como usar o modelo para uma nova obra
nova_obra = {
    'orcamento_estimado': 12000000,
    'rating_confiabilidade': 2.5,
    'taxa_insucesso_fornecedor': 0.8,  # fornecedor perigoso
    'complexidade_obra': np.log1p(12000000),
    'risco_etapa': 10.0,
    'material': 'concreto',
    'cidade': 'Belo Horizonte',
    'etapa': 'Fundação'
}

# Transformar em DataFrame para prever
df_nova = pd.DataFrame([nova_obra])

# Aplicar one-hot encoding igual ao treinamento
df_nova_encoded = pd.get_dummies(df_nova, columns=["material","cidade","etapa"])

# Garantir que tenha as mesmas colunas de X (adiciona colunas faltantes com 0)
for col in X.columns:
    if col not in df_nova_encoded.columns:
        df_nova_encoded[col] = 0

# Reordenar colunas
df_nova_encoded = df_nova_encoded[X.columns]

# Fazer previsão
pred_atraso = model.predict(df_nova_encoded)[0]

print("=== Simulador de Risco ===")
print(f"Previsão de atraso para a nova obra: {pred_atraso:.2f} dias")


# ============================================================
# 23. Simulador de Risco CCbjj – Consumo de Pipeline IA
# ============================================================
import pandas as pd
import numpy as np
import joblib
import os

# 1. Carregamento do Cérebro do Projeto (Pipeline + Metadados)
MODEL_PATH = "models/pipeline_random_forest.pkl"
META_PATH = "models/features_metadata.joblib"

if not os.path.exists(MODEL_PATH):
    print("❌ Erro: Modelo não encontrado. Rode o scripts/train_model.py primeiro.")
else:
    # Carregamos o pipeline completo (já inclui o tratamento de dados)
    pipeline = joblib.load(MODEL_PATH)
    features_originais = joblib.load(META_PATH)

    # 2. Definição do Cenário de Simulação (Exemplo de Obra de Alto Risco)
    # IMPORTANTE: Usamos minúsculo para bater com o padrão do gerador_dados.py
    nova_obra = {
        'orcamento_estimado': 12000000.0,
        'rating_confiabilidade': 2.5,        # Fornecedor com nota baixa
        'taxa_insucesso_fornecedor': 0.35,   # Histórico de falhas alto
        'complexidade_obra': np.log1p(12000000.0),
        'risco_etapa': 8.0,                  # Valor base de risco da etapa
        'nivel_chuva': 450.0,                # Cenário de muita chuva
        'tipo_solo': 'argiloso',             # Solo instável
        'material': 'cimento',
        'cidade': 'belo horizonte',
        'etapa': 'fundação'
    }

    # 3. Transformação em DataFrame
    df_nova = pd.DataFrame([nova_obra])

    # 4. Garantia de Contrato (Reordenar colunas conforme o treinamento)
    # Isso evita erros de predição se a ordem das chaves no dicionário mudar
    df_nova = df_nova[features_originais]

    # 5. Predição Direta via Pipeline
    # O pipeline aplica o StandardScaler e o OneHotEncoder automaticamente!
    
    pred_atraso = pipeline.predict(df_nova)[0]

    # 6. Relatório de Diagnóstico
    print("=== 🏗️ SIMULADOR DE RISCO CCBJJ ===")
    print(f"📍 Obra em: {nova_obra['cidade'].title()} | Etapa: {nova_obra['etapa'].title()}")
    print(f"🌧️ Clima: {nova_obra['nivel_chuva']}mm | Solo: {nova_obra['tipo_solo'].title()}")
    print("-" * 40)
    
    status = "🔴 CRÍTICO" if pred_atraso > 12 else "🟡 ALERTA" if pred_atraso > 7 else "🟢 SEGURO"
    print(f"🔮 PREVISÃO DE ATRASO: {pred_atraso:.1f} dias")
    print(f"📊 STATUS DO CRONOGRAMA: {status}")
    print("-" * 40)
    print("💡 Sugestão: Verifique planos de drenagem ou troque o fornecedor.")

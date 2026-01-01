import pandas as pd
import numpy as np
import joblib
import os

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score

# 1. Configurações de Caminhos
DATA_PATH = "data/raw/base_consulta_botccbjj.csv"
MODEL_PATH = "models/pipeline_random_forest.pkl"
META_PATH = "models/features_metadata.joblib"
os.makedirs("models", exist_ok=True)

def train():
    print("🚀 Iniciando treinamento do modelo CCbjj IA...")

    # 2. Carregamento dos dados
    if not os.path.exists(DATA_PATH):
        print(f"❌ Erro: Arquivo {DATA_PATH} não encontrado. Rode o gerar_dados.py primeiro.")
        return

    df = pd.read_csv(DATA_PATH)

    # 3. Pré-processamento Preventivo (Sincronia com Célula 18)
    # Garantimos que os dados de treino estejam em minúsculo para evitar conflitos
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.lower().str.strip()

    # 4. Separação de Features e Target
    target = 'risco_etapa'
    # Removemos IDs e a variável alvo
    X = df.drop(columns=['id_obra', target], errors='ignore')
    y = df[target]

    # [CONTRATO] Salvar a ordem exata das colunas para o App/Bot
    feature_names = X.columns.tolist()
    joblib.dump(feature_names, META_PATH)
    print(f"📝 Contrato de variáveis salvo em: {META_PATH}")

    # 5. Definição Automática de Colunas por Tipo
    cat_features = ['cidade', 'tipo_solo', 'material', 'etapa']
    num_features = [col for col in X.columns if col not in cat_features]

    

    # 6. Criação do Processador de Dados
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_features),
            ('num', StandardScaler(), num_features)
        ])

    # 7. Pipeline de Produção
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=2,  # Evita que o modelo decore ruídos dos dados
            random_state=42,
            n_jobs=-1
        ))
    ])

    # 8. Divisão Treino/Teste
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 9. Execução do Treinamento
    print(f"🧠 Processando {len(X_train)} registros e otimizando floresta...")
    model_pipeline.fit(X_train, y_train)

    # 10. Avaliação de Performance
    preds = model_pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    print("-" * 30)
    print(f"✅ TREINAMENTO CCBJJ CONCLUÍDO!")
    print(f"📊 Margem de Erro (MAE): {mae:.2f} dias")
    print(f"📈 Poder de Explicação (R²): {r2*100:.1f}%")
    print("-" * 30)

    # 11. Salvamento do Ativo Final
    joblib.dump(model_pipeline, MODEL_PATH)
    print(f"💾 Pipeline IA exportado: {MODEL_PATH}")

if __name__ == "__main__":
    train()

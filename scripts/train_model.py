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
os.makedirs("models", exist_ok=True)

def train():
    print("🚀 Iniciando treinamento do modelo CCbjj...")

    # 2. Carregamento dos dados
    if not os.path.exists(DATA_PATH):
        print(f"❌ Erro: Arquivo {DATA_PATH} não encontrado. Rode o gerar_dados.py primeiro.")
        return

    df = pd.read_csv(DATA_PATH)

    # 3. Separação de Features e Target
    # O objetivo é prever o 'risco_etapa' (que representa os dias de atraso simulados)
    X = df.drop(columns=['id_obra', 'risco_etapa'])
    y = df['risco_etapa']

    # 4. Definição das colunas por tipo
    # O pipeline precisa saber quem é texto e quem é número
    cat_features = ['cidade', 'tipo_solo', 'material', 'etapa']
    num_features = ['orcamento_estimado', 'rating_confiabilidade', 
                    'complexidade_obra', 'nivel_chuva', 'taxa_insucesso_fornecedor']

    # 5. Criação do Processador de Dados (Feature Engineering)
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore'), cat_features),
            ('num', StandardScaler(), num_features)
        ])

    # 6. Montagem do Pipeline Completo
    # O Pipeline une o tratamento de dados + o Algoritmo em um único objeto .pkl
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42))
    ])

    # 7. Divisão Treino/Teste
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 8. Treinamento
    print("🧠 Otimizando floresta aleatória (Random Forest)...")
    model_pipeline.fit(X_train, y_train)

    # 9. Avaliação
    preds = model_pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    print(f"\n✅ Treinamento concluído!")
    print(f"📊 Erro Médio (MAE): {mae:.2f} dias")
    print(f"📈 Score R²: {r2:.2f}")

    # 10. Salvamento Serializado
    joblib.dump(model_pipeline, MODEL_PATH)
    print(f"💾 Modelo salvo com sucesso em: {MODEL_PATH}")

if __name__ == "__main__":
    train()

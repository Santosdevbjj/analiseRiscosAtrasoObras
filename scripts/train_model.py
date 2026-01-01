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

    # 3. Separação de Features e Target
    # O alvo é prever o risco (atraso em dias)
    target = 'risco_etapa'
    X = df.drop(columns=['id_obra', target])
    y = df[target]

    # [IMPORTANTE] Salvar a ordem das colunas para o deploy (App/Bot)
    feature_names = X.columns.tolist()
    joblib.dump(feature_names, META_PATH)
    print(f"📝 Metadados de colunas salvos em: {META_PATH}")

    # 4. Definição das colunas por tipo
    cat_features = ['cidade', 'tipo_solo', 'material', 'etapa']
    num_features = ['orcamento_estimado', 'rating_confiabilidade', 
                    'complexidade_obra', 'nivel_chuva', 'taxa_insucesso_fornecedor']

    # 5. Criação do Processador de Dados
    # Usamos sparse_output=False para facilitar manipulações posteriores se necessário
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_features),
            ('num', StandardScaler(), num_features)
        ])

    # 6. Montagem do Pipeline Completo
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(
            n_estimators=300, # Aumentado para maior estabilidade
            max_depth=12,      # Aumentado para capturar correlações solo/chuva
            random_state=42,
            n_jobs=-1          # Usa todos os núcleos do processador
        ))
    ])

    # 7. Divisão Treino/Teste
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 8. Treinamento
    print(f"🧠 Treinando com {len(X_train)} amostras...")
    model_pipeline.fit(X_train, y_train)

    # 9. Avaliação
    preds = model_pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    print(f"\n✅ Treinamento concluído!")
    print(f"📊 Erro Médio (MAE): {mae:.2f} dias")
    print(f"📈 Precisão R²: {r2*100:.1f}%")

    # 10. Salvamento Serializado
    joblib.dump(model_pipeline, MODEL_PATH)
    print(f"💾 Pipeline de IA salvo em: {MODEL_PATH}")

if __name__ == "__main__":
    train()

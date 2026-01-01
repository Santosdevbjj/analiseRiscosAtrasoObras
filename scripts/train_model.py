import pandas as pd
import numpy as np
import joblib
import os

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer # Importante para segurança
from sklearn.metrics import mean_absolute_error, r2_score

# 1. Configurações de Caminhos Sincronizados
# Agora usamos o dado PROCESSADO pela célula 18
DATA_PATH = "data/processed/df_mestre_consolidado.csv"
MODEL_PATH = "models/pipeline_random_forest.pkl"
META_PATH = "models/features_metadata.joblib"
os.makedirs("models", exist_ok=True)

def train():
    print("🚀 Iniciando treinamento do modelo CCbjj IA...")

    # 2. Carregamento dos dados
    if not os.path.exists(DATA_PATH):
        print(f"❌ Erro: Arquivo processado {DATA_PATH} não encontrado. Rode consolidar_base.py primeiro.")
        return

    df = pd.read_csv(DATA_PATH)

    # 3. Pré-processamento Preventivo
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.lower().str.strip()

    # 4. Definição de Features e Target
    # O alvo ideal é o risco calculado ou atraso real (aqui usamos risco_etapa conforme seu design)
    target = 'risco_etapa'
    
    # Removemos colunas que não são preditivas (IDs)
    X = df.drop(columns=['id_obra', target], errors='ignore')
    y = df[target]

    # Salvar contrato de variáveis
    feature_names = X.columns.tolist()
    joblib.dump(feature_names, META_PATH)

    # 5. Definição de Colunas por Tipo
    cat_features = ['cidade', 'tipo_solo', 'material', 'etapa']
    num_features = [col for col in X.columns if col not in cat_features]

    

    # 6. Criação do Processador (Pipeline Robusto)
    # Adicionamos SimpleImputer para que o modelo não quebre se houver nulos em produção
    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='constant', fill_value='desconhecido')),
        ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', categorical_transformer, cat_features),
            ('num', numeric_transformer, num_features)
        ])

    # 7. Pipeline de Produção CCbjj
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        ))
    ])

    # 8. Divisão Treino/Teste
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 9. Execução do Treinamento
    print(f"🧠 Treinando floresta com {len(X_train)} exemplos...")
    model_pipeline.fit(X_train, y_train)

    # 10. Avaliação
    preds = model_pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    print("-" * 40)
    print(f"✅ MODELO CCBJJ PRONTO!")
    print(f"📊 Erro Médio: {mae:.2f} dias")
    print(f"📈 Acurácia (R²): {r2*100:.1f}%")
    print("-" * 40)

    # 11. Exportação
    joblib.dump(model_pipeline, MODEL_PATH)
    print(f"💾 Modelo salvo em: {MODEL_PATH}")

if __name__ == "__main__":
    train()

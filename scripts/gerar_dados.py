import pandas as pd
import numpy as np
from faker import Faker
import random
import os

# Inicialização
fake = Faker('pt_BR')
np.random.seed(42)
random.seed(42)

# Garantir existência das pastas
os.makedirs('data/raw', exist_ok=True)

# Configurações do Ecossistema CCbjj
NUM_OBRAS = 200  # Aumentado levemente para melhorar a convergência do modelo
NUM_FORNECEDORES = 40

# 1. Definições de Domínio (Padronizado em Minúsculo)
cidades = ['recife', 'são paulo', 'manaus', 'rio de janeiro', 'curitiba', 'salvador', 'fortaleza', 'belo horizonte', 'belém', 'porto alegre']
tipos_solo = ['arenoso', 'argiloso', 'rochoso', 'siltoso']
etapas_materiais = {
    'fundação': ['cimento', 'brita', 'areia', 'madeira'],
    'estrutura': ['aço', 'madeira', 'cimento'],
    'acabamento': ['piso', 'tintas', 'revestimento', 'aço']
}

# 2. Gerar Fornecedores
fornecedores = []
for i in range(NUM_FORNECEDORES):
    fornecedores.append({
        'id_fornecedor': f'FORN-{i+1}', # Padronizado minúsculo no nome da coluna
        'nome_fornecedor': fake.company(),
        'rating_confiabilidade': round(random.uniform(1.0, 5.0), 1)
    })
df_fornecedores = pd.DataFrame(fornecedores)

# 3. Gerar Obras
obras = []
for i in range(NUM_OBRAS):
    orcamento = round(random.uniform(5_000_000, 30_000_000), 2)
    obras.append({
        'id_obra': f'CCBJJ-{100+i}',
        'nome_empreendimento': f'Residencial {fake.street_name()}'.title(),
        'cidade': random.choice(cidades),
        'tipo_solo': random.choice(tipos_solo),
        'orcamento_estimado': orcamento,
        'complexidade_obra': np.log1p(orcamento), 
        'data_inicio_prevista': fake.date_between(start_date='-1y', end_date='today')
    })
df_obras = pd.DataFrame(obras)

# 4. Gerar Clima, Atividades e Suprimentos
clima, atividades, base_consulta = [], [], []



for idx, obra in df_obras.iterrows():
    # Nível de chuva acumulado (Feature forte para o modelo)
    chuva_acumulada = random.randint(30, 750)
    clima.append({'id_obra': obra['id_obra'], 'chuva_mm': chuva_acumulada})
    
    for etapa, materiais in etapas_materiais.items():
        id_atv = f"{obra['id_obra']}_{etapa}"
        
        # Seleção de Fornecedor
        forn = df_fornecedores.sample(1).iloc[0]
        taxa_insucesso_base = round(random.uniform(0.05, 0.45), 2)
        
        # Lógica de Atraso Correlacionada (Regras de Engenharia)
        risco_base = 3.0
        if etapa == 'fundação' and obra['tipo_solo'] == 'argiloso': risco_base += 5.5
        if chuva_acumulada > 400: risco_base += 4.0
        if forn['rating_confiabilidade'] < 2.5: risco_base += 6.0
        
        # Variável Alvo: dias_atraso
        dias_atraso = round(max(0, risco_base + random.normalvariate(2, 2.5)), 1)
        
        atividades.append({
            'id_atividade': id_atv,
            'id_obra': obra['id_obra'],
            'id_fornecedor': forn['id_fornecedor'],
            'etapa': etapa,
            'dias_atraso': dias_atraso,
            'status': 'atrasado' if dias_atraso > 5 else 'no prazo'
        })
        
        # Base Consolidada (O que o App e o Bot lerão)
        base_consulta.append({
            'id_obra': obra['id_obra'],
            'orcamento_estimado': obra['orcamento_estimado'],
            'rating_confiabilidade': forn['rating_confiabilidade'],
            'taxa_insucesso_fornecedor': taxa_insucesso_base,
            'complexidade_obra': obra['complexidade_obra'],
            'risco_etapa': dias_atraso, # Target real
            'nivel_chuva': chuva_acumulada,
            'tipo_solo': obra['tipo_solo'],
            'material': random.choice(materiais),
            'cidade': obra['cidade'],
            'etapa': etapa
        })

# 5. Salvamento Padronizado
pd.DataFrame(clima).to_csv('data/raw/climaccbjj.csv', index=False)
pd.DataFrame(atividades).to_csv('data/raw/atividadesccbjj.csv', index=False)
pd.DataFrame(base_consulta).to_csv('data/raw/base_consulta_botccbjj.csv', index=False)
df_fornecedores.to_csv('data/raw/fornecedoresccbjj.csv', index=False)
df_obras.to_csv('data/raw/obrasccbjj.csv', index=False)

print(f"✅ Sucesso! Geradas {NUM_OBRAS} obras com integridade referencial.")
print(f"📂 Arquivos salvos em 'data/raw/' prontos para o Pipeline de IA.")

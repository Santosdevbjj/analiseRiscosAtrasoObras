import pandas as pd
import numpy as np
from faker import Faker
import random

fake = Faker('pt_BR')
np.random.seed(42)

# Configurações
NUM_OBRAS = 50
NUM_FORNECEDORES = 20

# 1. Gerar Obras
obras = []
cidades = ['Belo Horizonte', 'São Paulo', 'Rio de Janeiro', 'Curitiba', 'Salvador']

for i in range(NUM_OBRAS):
    obras.append({
        'id_obra': f'MRV-{100+i}',
        'nome_empreendimento': f'Residencial {fake.street_name()}',
        'cidade': random.choice(cidades),
        'orcamento_estimado': round(random.uniform(5000000, 20000000), 2),
        'data_inicio_prevista': fake.date_between(start_date='-1y', end_date='today')
    })

df_obras = pd.DataFrame(obras)

# 2. Gerar Fornecedores
fornecedores = []
for i in range(NUM_FORNECEDORES):
    fornecedores.append({
        'id_fornecedor': f'FORN-{i}',
        'nome': fake.company(),
        'rating_confiabilidade': round(random.uniform(1, 5), 1) # 1 a 5 estrelas
    })

df_fornecedores = pd.DataFrame(fornecedores)

# 3. Gerar Atividades e Suprimentos (Com correlação de atraso)
atividades = []
suprimentos = []

for idx, obra in df_obras.iterrows():
    # Cada obra tem 3 atividades principais
    for etapa in ['Fundação', 'Estrutura', 'Acabamento']:
        id_atv = f"{obra['id_obra']}_{etapa}"
        
        # Escolhe um fornecedor aleatório
        forn = df_fornecedores.sample(1).iloc[0]
        
        # LÓGICA DE NEGÓCIO: Se o rating do fornecedor for baixo (< 3), 
        # a chance de atraso no suprimento é de 70%
        atraso_suprimento = 1 if forn['rating_confiabilidade'] < 3 and random.random() < 0.7 else 0
        dias_atraso = random.randint(10, 30) if atraso_suprimento == 1 else 0

        atividades.append({
            'id_atividade': id_atv,
            'id_obra': obra['id_obra'],
            'etapa': etapa,
            'dias_atraso': dias_atraso,
            'status': 'Atrasado' if dias_atraso > 0 else 'No Prazo'
        })
        
        suprimentos.append({
            'id_obra': obra['id_obra'],
            'id_atividade': id_atv,
            'id_fornecedor': forn['id_fornecedor'],
            'material': 'Cimento' if etapa == 'Fundação' else 'Aço' if etapa == 'Estrutura' else 'Piso',
            'atrasou_entrega': atraso_suprimento
        })

df_atividades = pd.DataFrame(atividades)
df_suprimentos = pd.DataFrame(suprimentos)

# Salvar tudo em CSV na pasta data/raw
df_obras.to_csv('data/raw/obras.csv', index=False)
df_fornecedores.to_csv('data/raw/fornecedores.csv', index=False)
df_atividades.to_csv('data/raw/atividades.csv', index=False)
df_suprimentos.to_csv('data/raw/suprimentos.csv', index=False)

print("✅ Dados fictícios da MRV gerados com sucesso em data/raw/")

import pandas as pd
import numpy as np
from faker import Faker
import random

fake = Faker('pt_BR')
np.random.seed(42)
random.seed(42)  # Garantir reprodutibilidade também no random

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
        'orcamento_estimado': round(random.uniform(5_000_000, 20_000_000), 2),
        'data_inicio_prevista': fake.date_between(start_date='-1y', end_date='today')
    })

df_obras = pd.DataFrame(obras)
df_obras['data_inicio_prevista'] = pd.to_datetime(df_obras['data_inicio_prevista'])

# 2. Gerar Fornecedores
fornecedores = []
for i in range(NUM_FORNECEDORES):
    fornecedores.append({
        'id_fornecedor': f'FORN-{i+1}',
        'nome': fake.company(),
        'rating_confiabilidade': round(random.uniform(1, 5), 1) # 1 a 5 estrelas
    })

df_fornecedores = pd.DataFrame(fornecedores)

# 3. Gerar Atividades e Suprimentos (Com correlação de atraso)
atividades = []
suprimentos = []

etapas_materiais = {
    'Fundação': ['Cimento', 'Brita'],
    'Estrutura': ['Aço', 'Madeira'],
    'Acabamento': ['Piso', 'Tintas', 'Revestimento']
}

for idx, obra in df_obras.iterrows():
    for etapa, materiais in etapas_materiais.items():
        id_atv = f"{obra['id_obra']}_{etapa}"
        
        # Escolhe um fornecedor aleatório
        forn = df_fornecedores.sample(1).iloc[0]
        
        # LÓGICA DE NEGÓCIO:
        # - Se rating < 3, chance de atraso é 70%
        # - Se orçamento > 15 milhões, chance de atraso aumenta em 20%
        atraso_prob = 0.7 if forn['rating_confiabilidade'] < 3 else 0.2
        if obra['orcamento_estimado'] > 15_000_000:
            atraso_prob += 0.2
        
        atraso_suprimento = 1 if random.random() < atraso_prob else 0
        dias_atraso = random.randint(10, 30) if atraso_suprimento == 1 else 0

        atividades.append({
            'id_atividade': id_atv,
            'id_obra': obra['id_obra'],
            'etapa': etapa,
            'dias_atraso': dias_atraso,
            'status': 'Atrasado' if dias_atraso > 0 else 'No Prazo'
        })
        
        # Cada etapa pode ter múltiplos materiais
        for material in materiais:
            suprimentos.append({
                'id_obra': obra['id_obra'],
                'id_atividade': id_atv,
                'id_fornecedor': forn['id_fornecedor'],
                'material': material,
                'atrasou_entrega': atraso_suprimento
            })

df_atividades = pd.DataFrame(atividades)
df_suprimentos = pd.DataFrame(suprimentos)

# Salvar tudo em CSV no diretório atual
df_obras.to_csv('obras.csv', index=False)
df_fornecedores.to_csv('fornecedores.csv', index=False)
df_atividades.to_csv('atividades.csv', index=False)
df_suprimentos.to_csv('suprimentos.csv', index=False)

print("✅ Dados fictícios da MRV gerados com sucesso!")

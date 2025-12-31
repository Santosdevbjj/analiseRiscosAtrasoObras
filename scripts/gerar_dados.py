import pandas as pd
import numpy as np
from faker import Faker
import random

fake = Faker('pt_BR')
np.random.seed(42)
random.seed(42)

# Configurações
NUM_OBRAS = 100  # Aumentei para 100 para o modelo aprender melhor as novas variáveis
NUM_FORNECEDORES = 20

# 1. Gerar Obras
obras = []
cidades = ['Belo Horizonte', 'São Paulo', 'Rio de Janeiro', 'Curitiba', 'Salvador']
tipos_solo = ['Arenoso', 'Argiloso', 'Rochoso', 'Siltoso']

for i in range(NUM_OBRAS):
    obras.append({
        'id_obra': f'CC-{100+i}',
        'nome_empreendimento': f'Residencial {fake.street_name()}',
        'cidade': random.choice(cidades),
        'tipo_solo': random.choice(tipos_solo), # Nova variável
        'orcamento_estimado': round(random.uniform(5_000_000, 25_000_000), 2),
        'data_inicio_prevista': fake.date_between(start_date='-1y', end_date='today')
    })

df_obras = pd.DataFrame(obras)

# 2. Gerar Fornecedores
fornecedores = []
for i in range(NUM_FORNECEDORES):
    fornecedores.append({
        'id_fornecedor': f'FORN-{i+1}',
        'nome': fake.company(),
        'rating_confiabilidade': round(random.uniform(1, 5), 1)
    })

df_fornecedores = pd.DataFrame(fornecedores)

# 3. Gerar Atividades e Suprimentos com correlações climáticas/geológicas
atividades = []
suprimentos = []

etapas_materiais = {
    'Fundação': ['Cimento', 'Brita'],
    'Estrutura': ['Aço', 'Madeira'],
    'Acabamento': ['Piso', 'Tintas', 'Revestimento']
}

for idx, obra in df_obras.iterrows():
    # Nível de chuva médio para esta obra específica (simulando sazonalidade/local local)
    chuva_obra = random.randint(0, 500) 
    
    for etapa, materiais in etapas_materiais.items():
        id_atv = f"{obra['id_obra']}_{etapa}"
        forn = df_fornecedores.sample(1).iloc[0]
        
        # --- LÓGICA DE RISCO AVANÇADA ---
        atraso_prob = 0.2 # Probabilidade base
        
        # Fator Fornecedor
        if forn['rating_confiabilidade'] < 3: atraso_prob += 0.4
        
        # Fator Clima + Solo (Impacto crítico na Fundação)
        if etapa == 'Fundação':
            if obra['tipo_solo'] == 'Argiloso' and chuva_obra > 200:
                atraso_prob += 0.3  # Solo argiloso encharcado é um pesadelo na fundação
            elif obra['tipo_solo'] == 'Arenoso' and chuva_obra > 350:
                atraso_prob += 0.2
        
        # Fator Estrutura + Chuva (Trabalho em altura/concretagem)
        if etapa == 'Estrutura' and chuva_obra > 300:
            atraso_prob += 0.15

        atraso_suprimento = 1 if random.random() < atraso_prob else 0
        
        # Magnitude do atraso em dias
        base_dias = random.randint(5, 15)
        if atraso_suprimento == 1:
            # Chuva alta aumenta a quantidade de dias de atraso
            dias_atraso = base_dias + int(chuva_obra / 20) 
        else:
            dias_atraso = 0

        atividades.append({
            'id_atividade': id_atv,
            'id_obra': obra['id_obra'],
            'etapa': etapa,
            'nivel_chuva': chuva_obra, # Nova coluna
            'dias_atraso': dias_atraso,
            'status': 'Atrasado' if dias_atraso > 0 else 'No Prazo'
        })
        
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

# Salvar
df_obras.to_csv('data/raw/obras.csv', index=False)
df_fornecedores.to_csv('data/raw/fornecedores.csv', index=False)
df_atividades.to_csv('data/raw/atividades.csv', index=False)
df_suprimentos.to_csv('data/raw/suprimentos.csv', index=False)

print("✅ Dados com variáveis de Chuva e Solo gerados com sucesso!")

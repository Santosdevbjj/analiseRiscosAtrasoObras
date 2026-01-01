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
NUM_OBRAS = 150  # Aumentamos para ter mais massa crítica de dados
NUM_FORNECEDORES = 30

# 1. Definições de Domínio
cidades = ['Recife', 'São Paulo', 'Manaus', 'Rio de Janeiro', 'Curitiba', 'Salvador', 'Fortaleza', 'Belo Horizonte', 'Belém', 'Porto Alegre']
tipos_solo = ['Arenoso', 'Argiloso', 'Rochoso', 'Siltoso']
etapas_materiais = {
    'Fundação': ['Cimento', 'Brita', 'Areia', 'Madeira'],
    'Estrutura': ['Aço', 'Madeira', 'Cimento'],
    'Acabamento': ['Piso', 'Tintas', 'Revestimento', 'Aço']
}

# 2. Gerar Fornecedores (Base de Confiabilidade)
fornecedores = []
for i in range(NUM_FORNECEDORES):
    fornecedores.append({
        'Id_fornecedor': f'FORN-{i+1}',
        'nome_fornecedor': fake.company(),
        'rating_confiabilidade': round(random.uniform(1.0, 5.0), 1)
    })
df_fornecedores = pd.DataFrame(fornecedores)

# 3. Gerar Obras (O Core do Negócio)
obras = []
for i in range(NUM_OBRAS):
    orcamento = round(random.uniform(5_000_000, 30_000_000), 2)
    obras.append({
        'id_obra': f'CCbjj-{100+i}',
        'nome_empreendimento': f'Residencial {i}',
        'cidade': random.choice(cidades),
        'tipo_solo': random.choice(tipos_solo),
        'orcamento_estimado': orcamento,
        'complexidade_obra': np.log1p(orcamento), # Feature Engineering imediata
        'data_inicio_prevista': fake.date_between(start_date='-1y', end_date='today')
    })
df_obras = pd.DataFrame(obras)

# 4. Gerar Clima e Atividades (Simulação de Riscos)
clima = []
atividades = []
suprimentos = []
base_consulta = []

for idx, obra in df_obras.iterrows():
    # Nível de chuva acumulado (Impacto regional)
    chuva_acumulada = random.randint(30, 550)
    clima.append({'id_obra': obra['id_obra'], 'chuva_mm': chuva_acumulada})
    
    for etapa, materiais in etapas_materiais.items():
        id_atv = f"{obra['id_obra']}_{etapa}"
        
        # Seleção de Fornecedor e Cálculo de Risco
        forn = df_fornecedores.sample(1).iloc[0]
        taxa_insucesso_base = round(random.uniform(0.05, 0.45), 2)
        
        # Lógica de Atraso Correlacionada (Regras de Negócio de Engenharia)
        risco_base = 5.0
        if etapa == 'Fundação' and obra['tipo_solo'] == 'Argiloso': risco_base += 4.0
        if chuva_acumulada > 300: risco_base += 3.5
        if forn['rating_confiabilidade'] < 2.5: risco_base += 5.0
        
        # Predição de dias (o que o modelo vai tentar aprender)
        dias_atraso = round(max(0, risco_base + random.normalvariate(2, 3)), 1)
        
        atividades.append({
            'id_atividade': id_atv,
            'id_obra': obra['id_obra'],
            'etapa': etapa,
            'dias_atraso': dias_atraso,
            'status': 'Atrasado' if dias_atraso > 5 else 'No Prazo'
        })
        
        # Base de Consulta para o Bot (Unificada)
        base_consulta.append({
            'id_obra': obra['id_obra'],
            'orcamento_estimado': obra['orcamento_estimado'],
            'cidade': obra['cidade'],
            'rating_confiabilidade': forn['rating_confiabilidade'],
            'complexidade_obra': obra['complexidade_obra'],
            'risco_etapa': dias_atraso + 2, # Proxy de risco
            'nivel_chuva': chuva_acumulada,
            'tipo_solo': obra['tipo_solo'],
            'material': random.choice(materiais),
            'etapa': etapa,
            'taxa_insucesso_fornecedor': taxa_insucesso_base
        })

# 5. Consolidação e Salvamento
pd.DataFrame(clima).to_csv('data/raw/climaccbjj.csv', index=False)
pd.DataFrame(atividades).to_csv('data/raw/atividadesccbjj.csv', index=False)
pd.DataFrame(base_consulta).to_csv('data/raw/base_consulta_botccbjj.csv', index=False)
df_fornecedores.to_csv('data/raw/fornecedoresccbjj.csv', index=False)
df_obras.to_csv('data/raw/obrasccbjj.csv', index=False)

print(f"✅ Sistema de Dados CCbjj gerado com {NUM_OBRAS} obras e correlações geológicas!")

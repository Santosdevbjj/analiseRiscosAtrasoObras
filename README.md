# analiseRiscosAtrasoObras

Prever qual obra tem maior chance de estourar o cronograma..

---


🏗️ Previsão de Riscos e Atrasos em Obras – MRV Engenharia
📖 1. Visão Geral e Problema de Negócio
A MRV enfrenta o desafio de gerenciar atrasos que impactam o fluxo de caixa e a satisfação do cliente. O atraso em uma única etapa (como fundação) gera custos em cascata.
O Problema: A falta de previsibilidade sobre quais fornecedores e etapas oferecem maior risco financeiro.
A Solução: Desenvolvi um modelo de Machine Learning que antecipa o atraso em dias, permitindo que a gestão de suprimentos e obras tome decisões baseadas em dados antes que o custo ocorra.
📂 2. Estrutura do Repositório
O projeto está organizado seguindo padrões de engenharia de dados para garantir escalabilidade:
├── data/
│   └── raw/                # Dados brutos e imutáveis
│       ├── atividades.csv   # Histórico de cronogramas
│       ├── fornecedores.csv # Cadastro e ratings
│       ├── obras.csv        # Orçamentos e localizações
│       └── suprimentos.csv  # Logística de materiais
├── models/
│   └── modelo_random_forest.pkl # Modelo preditivo serializado
├── Notebooks/
│   ├── gerar_dados.ipynb        # Simulação da base de dados
│   └── 02_modelagem_preditiva.ipynb # Desenvolvimento do modelo
├── reports/
│   └── figures/            # Ativos visuais do projeto
│       └── feature_importance.png # Gráfico de relevância
├── scripts/
│   └── gerar_dados.py      # Automação de processamento
├── requirements.txt        # Dependências do ambiente
├── LICENSE                 # Licença do projeto
└── README.md               # Documentação principal

🎯 3. Objetivo do Projeto
Demonstrar a viabilidade de prever atrasos usando o algoritmo RandomForestRegressor, focando na criação de variáveis (Feature Engineering) que capturem a ineficiência de fornecedores e a complexidade financeira de cada empreendimento.
🛠️ 4. Decisões Técnicas e Trade-offs
 * Por que Random Forest? Pela sua capacidade de lidar com variáveis categóricas (cidades, etapas) e fornecer interpretabilidade clara sobre o que está causando o atraso.
 * Feature Engineering: Criei a taxa_insucesso_fornecedor e o logaritmo da complexidade_obra, que se mostraram os maiores preditores do modelo.
 * Persistência: O modelo é salvo em .pkl para garantir que o resultado seja replicável em produção sem necessidade de retreino.
📊 5. Resultados e Performance do Modelo
Após a execução do pipeline em 02_modelagem_preditiva.ipynb, o modelo apresentou os seguintes indicadores de performance:
| Métrica | Valor |
|---|---|
| Erro Médio Absoluto (MAE) | 4.97 dias |
| R² Score | 0.41 |
| Impacto Financeiro (R$) | R$ 248,400.00 |
🔍 Diagnóstico de Variáveis (Insights de Negócio)
O gráfico abaixo, gerado automaticamente, revela que o histórico de insucesso do fornecedor é o fator que mais onera o prazo da MRV. Isso indica que a homologação de fornecedores é o ponto mais crítico para a redução de custos.
🚀 6. Simulador de Risco (Exemplo de Uso)
Este projeto entrega uma ferramenta pronta para ser integrada a um dashboard ou sistema interno:
import joblib
import numpy as np

# Carrega o cérebro do projeto
model = joblib.load('models/modelo_random_forest.pkl')

# Simulação de nova obra: Fornecedor de alto risco em Belo Horizonte
nova_obra = {
    'orcamento_estimado': 12000000,
    'taxa_insucesso_fornecedor': 0.8, # 80% de atrasos anteriores
    'complexidade_obra': np.log1p(12000000),
    'risco_etapa': 10.5
    # ... demais variáveis codificadas
}

# Previsão: 12.91 dias de atraso estimado

📈 7. Aprendizados e Próximos Passos
Aprendizados:
 * A importância de converter métricas de erro (MAE) em impacto financeiro (R$) para facilitar a decisão da diretoria.
 * Como lidar com o viés de orçamentos altos usando transformações logarítmicas.
Próximos Passos:
 * [ ] Implementar um dashboard interativo com Streamlit.
 * [ ] Testar modelos de Gradient Boosting (XGBoost) para melhorar o R².
 * [ ] Integrar dados de APIs meteorológicas para refinar riscos em etapas externas.


---

🤝 Contato e Conexões
Sérgio Santos
[Link para o seu LinkedIn]
[Seu E-mail Profissional]
Este projeto foi desenvolvido como parte de um portfólio profissional para demonstrar habilidades em Ciência de Dados aplicada ao setor imobiliário.





## 🏗️ **Predição de Risco de Atraso em Obras**

**CCbjj Engenharia & Inteligência de Risco**

     *Disciplina, estratégia e dados aplicados à engenharia civil.*
     

> Projeto de Ciência de Dados e Analytics Engineering aplicado à construção civil, com foco em mitigação de riscos operacionais, redução de atrasos e suporte à tomada de decisão estratégica.




---

📌 **Visão Geral**

Este projeto tem como objetivo prever o risco de atraso em obras de construção civil, considerando fatores operacionais, climáticos, logísticos e de fornecedores.

A solução simula um ambiente real de uma empresa de engenharia, utilizando uma arquitetura de dados organizada, modelagem analítica, Machine Learning e uma camada de produto acessível por Streamlit e Bot do Telegram.

O foco do projeto vai além do modelo estatístico, priorizando valor de negócio, governança de dados e capacidade de consumo por usuários não técnicos.


---

⚠️ **Disclaimer**

Todos os dados, nomes de empresas e cenários apresentados neste projeto são fictícios, criados exclusivamente para fins acadêmicos e de portfólio.

Este projeto não possui vínculo com nenhuma empresa real de engenharia e não utiliza dados confidenciais.


---

🎯 **Problema de Negócio**

Atrasos em obras geram impactos diretos como:

Multas contratuais

Aumento de custos operacionais

Quebra de cronograma

Insatisfação de clientes e investidores


O desafio do negócio é antecipar quais obras apresentam maior risco de atraso, permitindo ações preventivas como:

Replanejamento de etapas

Substituição de fornecedores críticos

Ajustes logísticos

Redistribuição de recursos


👉 **Pergunta central do projeto:**

> Quais obras apresentam maior risco de atraso e onde a empresa deve agir primeiro?




---

🧭 **Contexto Operacional**

A CCbjj Engenharia (empresa fictícia) possui dados históricos envolvendo:

Etapas de execução da obra

Condições climáticas

Tipo de solo

Fornecedores e materiais

Orçamento estimado


Apesar da existência desses dados, não havia uma visão analítica integrada, nem mecanismos de simulação de risco em tempo hábil para decisão executiva.

Este projeto preenche essa lacuna ao transformar dados operacionais em insights acionáveis.


---

🧠 **Premissas da Análise**

Os dados utilizados são sintéticos, porém modelados com comportamento realista do setor

O risco de atraso é tratado como um problema operacional e preditivo

Variáveis externas (ex.: clima) são fatores de risco, não determinantes absolutos

O objetivo do modelo é apoio à decisão, não previsão perfeita



---

🧱 **Arquitetura de Dados (Visão Profissional)**

O projeto segue uma arquitetura analítica em camadas, semelhante à adotada em ambientes corporativos.

Supabase
├── raw
│   ├── atividadesccbjj        (dimensão de etapas da obra)
│   ├── fornecedoresccbjj      (dimensão de fornecedores)
│   ├── climaccbjj             (dimensão climática)
│
├── analytics
│   └── dashboard_obras        (tabela fato analítica consolidada)
│
└── products
    └── base_consulta_botccbjj (camada de consumo para app e bot)

Essa separação garante:

Governança de dados

Escalabilidade

Facilidade de manutenção

Consumo eficiente por BI, Streamlit e APIs



---

📊 **Tabela Analítica Principal**

Tabela: dashboard_obras (Supabase)

Principais variáveis:

risco_etapa → indicador central de decisão

rating_confiabilidade → desempenho do fornecedor

taxa_insucesso_fornecedor → histórico operacional

nivel_chuva → risco climático

tipo_solo → risco geotécnico

orcamento_estimado → exposição financeira


Essa tabela funciona como uma tabela fato de risco operacional, preparada para:

Análises SQL

Machine Learning

Simulações

Produtos de dados



---

🔍 **Estratégia da Solução Analítica**

1️⃣ Entendimento do problema de negócio
2️⃣ Consolidação e padronização dos dados
3️⃣ Análise exploratória e validação de hipóteses
4️⃣ Engenharia de atributos orientada a risco
5️⃣ Treinamento do modelo preditivo
6️⃣ Avaliação com foco em impacto operacional
7️⃣ Criação de camada de consumo para usuários finais


---

🤖 **Modelagem Preditiva**

Algoritmo: RandomForestRegressor

Justificativa da escolha:

Captura relações não lineares

Robustez a ruído operacional

Boa performance com variáveis mistas

Adequado para cenários reais de engenharia



O modelo foi salvo e versionado para uso em produção e simulações.


---

📈 **Métricas do Modelo**

Métrica	Valor	Interpretação

MAE	4,97 dias	Erro médio inferior a 5 dias
R²	0,41	Explicação consistente para um ambiente volátil
Economia estimada	R$ 248.400 / ano	Multas evitadas por ação preventiva


👉 O foco está no valor prático da previsão, não apenas na métrica estatística.


---

🖥️ **Produto Final**

📊 Simulador interativo em Streamlit

🤖 Consulta rápida via Bot do Telegram

🗄️ Base analítica governada no Supabase


Esses componentes permitem que gestores não técnicos utilizem inteligência preditiva no dia a dia.


---

📚 **Principais Aprendizados**

Importância da separação entre dados analíticos e dados de consumo

Modelagem de dados orientada a decisão

Conversão de métricas técnicas em impacto financeiro

Comunicação clara é parte essencial do trabalho com dados



---

🚀 **Próximos Passos**

Integração com dados climáticos reais (API)

Monitoramento contínuo do modelo

Alertas automáticos de risco

Expansão do impacto financeiro detalhado



---

🎤 **Como Explicar Este Projeto em Entrevista**

> “Estruturei os dados em camadas analíticas, criei uma tabela fato consolidada, desenvolvi um modelo preditivo e disponibilizei os resultados em um simulador e um bot. O foco foi apoiar decisões operacionais e reduzir risco financeiro, não apenas treinar um modelo.”




---

🧾 **Conclusão:**

Este projeto demonstra:

✔ Capacidade técnica em Ciência de Dados
✔ Visão de Analytics Engineering
✔ Entendimento profundo do negócio de engenharia
✔ Maturidade para atuar em ambientes reais

👉 Não é apenas um projeto de Machine Learning. É uma solução de dados aplicada ao negócio.




---

👤 **Autor:**

Sergio Santos 

---


## 📩 Contato



[![Portfólio Sérgio Santos](https://img.shields.io/badge/Portfólio-Sérgio_Santos-111827?style=for-the-badge&logo=githubpages&logoColor=00eaff)](https://santosdevbjj.github.io/portfolio/)
[![LinkedIn Sérgio Santos](https://img.shields.io/badge/LinkedIn-Sérgio_Santos-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/santossergioluiz) 


---



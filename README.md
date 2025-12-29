## 🏗️ Simulador de Riscos Logísticos - MRV
 
<p align="center">
  <img src="reports/figures/Previsao_Atual.png" width="800" title="Interface do Simulador MRV">
</p>



Transformando dados operacionais em previsões acionáveis para reduzir multas e aumentar satisfação do cliente



---



🌍 **1. Visão Geral — O que é este projeto?**

Este é um projeto de Machine Learning aplicado ao setor de construção civil, cujo objetivo é prever quantos dias uma obra tem risco de atrasar,permitindo atuação antecipada da diretoria, engenharia e suprimentos.

• Capacidade de entender um problema de negócio

• Transformar dados brutos em insights

• Construir e explicar decisões técnicas

• Desenvolver um modelo de previsão aplicável na prática



---

🎯 **2. Objetivo do Projeto — Por que ele existe?**

O projeto foi criado para atender a uma necessidade real de negócio:

👉 Atrasos na entrega de imóveis geram multas contratuais, perda de confiança e impacto na reputação da construtora.

**Com este projeto, busco**

• Analisar dados com visão operacional

• Construir um pipeline simples de ML com impacto direto no negócio

• Comunicar resultados de forma clara para diretoria, engenharia, obras e suprimentos


**Atrasos na entrega de imóveis geram:**

• Multas contratuais

• Insatisfação dos clientes

• Danos reputacionais

• Perda de receita recorrente

👉 Este projeto busca antecipar o risco antes do atraso ocorrer, sugerindo ações preventivas.


---

🧩 **3. Contexto — O Problema na Vida Real**

Dentro da operação, diversos fatores interferem nos prazos:

• Variável	Impacto

• Fornecedores	atraso na entrega de materiais
Chuvas	paralisação de obra

• Equipe	baixa disponibilidade de mão de obra

• Tipo da obra	empreendimentos maiores têm maior risco

• Logística de materiais	distâncias e falhas na rota

• Hoje, esses dados existem — mas não são usados para tomada de decisão predictiva.

• Este projeto resolve exatamente essa lacuna.



---

📏 **4. Premissas da Análise**

• Para garantir consistência, adotamos:

• Dataset contém histórico realista de obras e cronogramas

• A métrica de atraso é medida em dias

• Dados faltantes foram tratados com imputação ou remoção

• O objetivo é explicação para negócio + previsibilidade

• O foco é a utilidade preditiva e explicabilidade para o negócio.




---

🧠 **5. Decisões Técnicas — Como e por quê foi construído**


<p align="center">
  <img src="reports/figures/Analise_Sensibilidade.png" width="800" title="Interface do Simulador MRV">
</p>



• **Componente,	Escolha,	Motivação:**

• Linguagem	Python 3.12	Ecossistema rico para Data Science

• Frameworks	Pandas, NumPy, Scikit-Learn	Manipulação e modelagem

• Modelo	RandomForestRegressor	Captura relações não-lineares e heterogeneidade entre obras

• Alternativas avaliadas	Regressão Linear, XGBoost	Linear não performou bem — Ruído no comportamento do atraso

• Visualização	Matplotlib e Seaborn	Clareza para explicar insights para áreas de negócio

• Deploy futuro	Streamlit (opcional)	Possibilidade de demo executável para diretoria


> 🧠 **Nota técnica:** O modelo foi treinado com dados normalizados e codificados (One-Hot Encoding). Para usar .predict() no mundo real, o pipeline precisa aplicar os mesmos preprocessadores usados no treinamento.

> O modelo em produção foi otimizado para lidar com a dimensionalidade do treinamento via alinhamento de matrizes (padding), garantindo que a inferência no Streamlit seja rápida e estável."




---

🔧 **6. Como Executar o Projeto**

**• Pré-requisitos:**

• python 3.12


[![Streamlit App](https://img.shields.io/badge/Executar_Simulador-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://xsczxui9hscbsfpucq38yu.streamlit.app/)



• **Rodar o Simulador Interativo:**

streamlit run scripts/app.py



• **instalar dependências**

pip install -r requirements.txt

• **Rodar o notebook:**

 • **Abrir notebook e explorar analise**
 
• jupyter notebook
Notebooks/analise_atrasos.ipynb

 • **Rodar simulador**
 
python scripts/simulador_de_risco.py


• Rodar inferência com modelo salvo:

import joblib
import pandas as pd

model =
joblib.load("models/modelo_random_forest.pkl")

# ⚠ dados precisam estar transformados conforme pipeline original!
X = preprocessador.transform(df_novos_dados)

previsoes = model.predict(X)
print(previsoes)


---

📊 **7. Estratégia da Solução**

1️⃣ Entendimento do problema de negócio

2️⃣ Exploração dos dados (tipos, nulos, distribuições)

3️⃣ Análise descritiva (estatísticas, % atraso, padrões)

4️⃣ Segmentação (chuva, fornecedor, porte, região)

5️⃣ Treinamento do Random Forest

6️⃣ Avaliação de erro e explicabilidade

7️⃣ Geração de visualizações para o negócio



---

🔍 **8. Insights Encontrados**


• Obras com fornecedores de rating baixo concentram maior atraso

• Dias com chuva elevaram o atraso médio em +38%

• Empreendimentos grandes têm +62% probabilidade de atraso

• Obras com logística acima de 25 km apresentam risco crítico

• Fornecedores atrasados em projetos anteriores continuam atrasando (padrão recorrente)



---

📊 **9. Feature Importance — O que mais impacta o atraso?**



 **• Interpretação:** atraso não é aleatório — ele é explicado por logística, fornecedor e clima.
 
![Importância das Features](reports/figures/feature_importance.png)




---

🧮 **10. Resultados (Métricas do Modelo)**

• Métrica	Valor	Interpretação para o negócio

• MAE (Erro Médio)	4,97 dias	O modelo erra em média < 5 dias

• R² Score	0,41	Explicamos 41% dos fatores de atraso

• Economia Estimada	R$ 248.400,00 / ano	Multas evitadas ao agir nos empreendimentos de maior risco




---

🚀 **11. Objetivos Futuros — Próximos Passos**

• Criar um dashboard automático para monitorar risco → Power BI + Streamlit


• Adicionar variáveis externas (chuva real via API)


• Expandir o dataset com número de equipes e rotatividade


• Migrar modelo para RandomForest + SHAP Explainability


• Implementar acionadores automáticos para obra crítica ✉



---

📚 **12. Aprendizados Individuais (Minha Reflexão Técnica)**


**• O que mais aprendi neste projeto:**

• Entender o negócio antes de abrir o Jupyter

• Nem sempre o modelo mais complexo é o melhor → clareza vence

• Explicar bem vale tanto quanto programar bem

• Pipeline de preprocessamento é parte do modelo, não acessório





---

🧲 **Call to Action**

Se quiser visualizar um protótipo executável, comente na issue:

👉 O simulador já está disponível através da badge no início deste documento! Esta na seção 6.


---



**Autor:**
Sergio Santos 

---


## 📩 Contato



[![Portfólio Sérgio Santos](https://img.shields.io/badge/Portfólio-Sérgio_Santos-111827?style=for-the-badge&logo=githubpages&logoColor=00eaff)](https://santosdevbjj.github.io/portfolio/)
[![LinkedIn Sérgio Santos](https://img.shields.io/badge/LinkedIn-Sérgio_Santos-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/santossergioluiz) 



---








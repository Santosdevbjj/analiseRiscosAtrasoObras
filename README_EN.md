## 🏗️ **Construction Delay Risk Prediction**

Operational Intelligence Analytics Platform — CCbjj Engineering

> A Data Science & Analytics Engineering project applied to the construction industry, focused on risk anticipation, delay reduction, and executive decision support, delivered as a data product, not just a model.




---

1️⃣ **Project Identity**

Goal:
Anticipate construction delay risks, enabling preventive actions before financial and operational impacts occur.

Target Audience:
Construction managers, PMOs, operational directors, and planning teams.

Deliverables:
Predictive model + Telegram Bot + Streamlit Simulator + Corporate PDF Report.


---

2️⃣ **Business Problem**

Construction delays generate direct impacts:

Contractual penalties

Forced re-planning

Increased indirect costs

Loss of credibility with clients and investors


Although historical data existed, the company lacked a predictive mechanism to act early.

👉 **Core business question:**

> Which construction projects are most likely to be delayed, and where should we act first?




---

3️⃣ **Current Context & Baseline**

📉 Previous State (Baseline)

Decisions based on historical averages

Prediction error around 12 days

Reactive management after delays occurred


📈 **Proposed Solution**

Risk-oriented predictive modeling

Uncertainty reduced to less than 5 days

Preventive operational decision-making


👉 The solution outperforms the historical baseline, significantly reducing operational uncertainty.


---

4️⃣ **Data Architecture (Analytics Engineer Perspective)**

The architecture follows corporate-grade analytical layers:

Supabase
├── raw
│   ├── activitiesccbjj        # Construction stages
│   ├── suppliersccbjj         # Suppliers and ratings
│   ├── weatherccbjj           # Weather data
│
├── analytics
│   └── dashboard_obras        # Consolidated analytical fact table
│
└── products
    └── base_consulta_botccbjj # Consumption layer (Bot / Streamlit)

Benefits:

Data governance

Scalability

Reusability

Decoupled consumption layer



---

5️⃣ **Solution Strategy (Analytical Pipeline)**

1. Business problem understanding


2. Data consolidation and standardization


3. Exploratory Data Analysis (EDA)


4. Risk-oriented feature engineering


5. Predictive model training


6. Technical and business evaluation


7. Product delivery (Bot & Simulator)




---

6️⃣ **Key Managerial Insights** 💡

Exploratory analysis revealed relevant patterns:

🔹 Supplier Rating has ~3x more impact on delays than Weather Levels during finishing stages

🔹 Low-reliability suppliers amplify delays even under favorable weather conditions

🔹 Large-scale projects are more sensitive to accumulated delays

🔹 Weather acts as an aggravating factor, rarely as a standalone root cause


👉 These insights support practical actions, such as supplier renegotiation, replacement, or reinforcement.


---

7️⃣ **Model Performance (Technical)**

Algorithm: RandomForestRegressor

Why Random Forest?

Captures non-linear relationships

Robust to operational noise

Suitable for heterogeneous real-world data



📊 **Metrics**

Metric	Value	Interpretation

MAE	4.97 days	Average error below 5 days
R²	0.41	Strong explanatory power in a volatile environment


👉 Solid performance for a real construction scenario.


---

8️⃣ **Business Performance** 💰

Indicator	Result

Uncertainty reduction	~60%
Estimated penalties avoided	R$ 248,400 / year
Decision model	Preventive


The focus is not only prediction, but early action.


---

9️⃣ **Final Product (In Production)**

🖥️ **Telegram Bot**

Language selection (EN/PT)

Data source selection (Local CSV or Supabase)

Query by construction ID

Output:

Risk status

Explanatory chart

Corporate PDF report



📊 **Streamlit Simulator**

Executive-friendly interface

Fast risk assessment

Decision support tool



---

▶️ **How to Run the Project**

Requirements

Python 3.10+

Telegram account (for the bot)

Optional: Supabase environment


Installation

pip install -r requirements.txt

Run the Bot

python scripts/telegram_bot.py

Usage Example

1. Start the Telegram bot with /start


2. Select language and data mode (CSV or Supabase)


3. Enter the construction ID (e.g., CCBJJ-100)


4. Receive a detailed report, chart, and corporate PDF




---

🔮 **Next Steps**

Integration with real-time weather APIs

Continuous model monitoring

Automated risk alerts

Expanded financial impact analysis



---

🧾 **Conclusion**

This project demonstrates:

✔ Analytics Engineer mindset
✔ Business-driven data modeling
✔ Product-oriented delivery
✔ Clear communication between technical and executive layers

👉 This is not an academic exercise. It is a real-world data solution.


---

👤 **Contact**

Sergio Santos
🔗 Portfolio: https://santosdevbjj.github.io/portfolio/
🔗 LinkedIn: https://linkedin.com/in/santossergioluiz


---

🟢 **Final Status**

✅ Corporate-ready
✅ Baseline-driven
✅ Insight-oriented
✅ Fully documented
✅ International recruiter friendly


---

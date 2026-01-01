# ============================
# Bootstrap: gerar CSVs simulados e robustos para CCbjj
# ============================
import os
import numpy as np
import pandas as pd

np.random.seed(42)
os.makedirs("data/raw", exist_ok=True)

# -----------------------
# fornecedoresccbjj.csv
# -----------------------
forn = pd.DataFrame({
    "Id_fornecedor": [f"FORN-{i}" for i in range(1, 1001)],  # 1k fornecedores
    "nome_ornecedor": np.random.choice(
        ["Carvalho ME","Duarte","Ribeiro Ltda","Macedo S/A","Silva & Filhos","Oliveira Tec","Pereira Construções"], 1000
    ),
    "rating_confiabilidade": np.round(np.random.uniform(1.0, 5.0, 1000), 1)
})
forn.to_csv("data/raw/fornecedoresccbjj.csv", index=False)

# -----------------------
# obrasccbjj.csv
# -----------------------
N_OBRAS = 50000
cidades = ["Belo Horizonte","Rio de Janeiro","São Paulo","Salvador","Curitiba","Porto Alegre","Fortaleza","Manaus","Recife","Belém"]
ids_obras = [f"CCbjj-{100+i}" for i in range(N_OBRAS)]

prazo_prev = np.clip(np.random.normal(360, 60, N_OBRAS).astype(int), 90, 900)
chuva_mm = np.random.randint(30, 500, N_OBRAS)
prazo_real = np.clip(
    prazo_prev
    + (chuva_mm * np.random.uniform(0.02, 0.08, N_OBRAS)).astype(int)
    + np.random.normal(10, 40, N_OBRAS).astype(int),
    60, 1200
)
obras = pd.DataFrame({
    "Id_obra": ids_obras,
    "nome_empreendimento": [f"Residencial {i}" for i in range(N_OBRAS)],
    "cidade": np.random.choice(cidades, N_OBRAS),
    "orcamento_estimado": np.round(np.random.uniform(3_000_000, 25_000_000, N_OBRAS), 2),
    "data_inicio_prevista": pd.to_datetime("2025-01-01") + pd.to_timedelta(np.random.randint(0, 365, N_OBRAS), unit="D"),
    "prazo_previsto_dias": prazo_prev,
    "prazo_real_dias": prazo_real,
    "chuva_mm": chuva_mm,
    "Atrasou": (prazo_real > prazo_prev).astype(int)
})
obras.to_csv("data/raw/obrasccbjj.csv", index=False)

# -----------------------
# climaccbjj.csv
# -----------------------
clima = obras[["Id_obra","chuva_mm"]].rename(columns={"Id_obra":"id_obra"})
clima.to_csv("data/raw/climaccbjj.csv", index=False)

# -----------------------
# mao_obraccbjj.csv
# -----------------------
mao = pd.DataFrame({
    "Id_obra": ids_obras,
    "qtd_engenheiros": np.clip(np.random.poisson(4, N_OBRAS), 1, 20),
    "qtd_pedreiros": np.clip(np.random.poisson(18, N_OBRAS), 5, 120),
    "qtd_servente_pedreiros": np.clip(np.random.poisson(20, N_OBRAS), 5, 150)
})
mao.to_csv("data/raw/mao_obraccbjj.csv", index=False)

# -----------------------
# atividadesccbjj.csv (3 etapas por obra)
# -----------------------
etapas = ["Fundação","Estrutura","Acabamento"]
ativ_rows = []
for oid in ids_obras:
    for e in etapas:
        atras = max(0, int(np.random.normal(5, 10)))  # pode ser 0
        status = "Atrasado" if atras > 0 else "No Prazo"
        ativ_rows.append({
            "id_atividade": f"{oid}_{e}",
            "id_obra": oid,
            "etapa": e,
            "dias_atraso": atras,
            "status": status
        })
ativ = pd.DataFrame(ativ_rows)
ativ.to_csv("data/raw/atividadesccbjj.csv", index=False)

# -----------------------
# suprimentosccbjj.csv
# -----------------------
materiais = ["Cimento","Areia","Brita","Tintas","Madeira","Aço","Piso","Revestimento"]
supr_rows = []
for oid in ids_obras:
    for e in etapas:
        for _ in range(np.random.randint(1, 4)):  # 1 a 3 itens por etapa
            supr_rows.append({
                "id_obra": oid,
                "id_atividade": f"{oid}_{e}",
                "Id_fornecedor": np.random.choice(forn["Id_fornecedor"]),
                "material": np.random.choice(materiais),
                "atrasou_entrega": np.random.choice([0,1], p=[0.7,0.3])  # 30% atraso em entrega
            })
supr = pd.DataFrame(supr_rows)
supr.to_csv("data/raw/suprimentosccbjj.csv", index=False)

# -----------------------
# base_consulta_botccbjj.csv (agregado por obra)
# -----------------------
taxa_obra = supr.groupby("id_obra")["atrasou_entrega"].mean().rename("taxa_insucesso_fornecedor").reset_index()
bot = obras[["Id_obra","orcamento_estimado","cidade"]].rename(columns={"Id_obra":"id_obra"})
bot["rating_confiabilidade"] = np.round(np.random.uniform(1.0, 5.0, len(bot)), 1)
bot["complexidade_obra"] = np.random.normal(15.5, 1.0, len(bot))
bot["risco_etapa"] = np.round(np.random.uniform(6.0, 12.0, len(bot)), 2)
bot["nivel_chuva"] = np.random.randint(50, 300, len(bot))
bot["tipo_solo"] = np.random.choice(["Rochoso","Argiloso","Siltoso","Arenoso"], len(bot))
bot["material"] = np.random.choice(materiais, len(bot))
bot["etapa"] = np.random.choice(etapas, len(bot))
bot = bot.merge(taxa_obra, on="id_obra", how="left").fillna({"taxa_insucesso_fornecedor":0})
bot.to_csv("data/raw/base_consulta_botccbjj.csv", index=False)

# -----------------------
# relatorio_consolidadoccbjj.csv (resumo por obra)
# -----------------------
rel = pd.DataFrame({
    "id_obra": obras["Id_obra"],
    "cidade": obras["cidade"],
    "tipo_solo": np.random.choice(["Rochoso","Argiloso","Siltoso","Arenoso"], len(obras)),
    "nivel_chuva": np.random.randint(50, 300, len(obras)),
    "risco_medio": np.round(np.random.uniform(6.0, 12.0, len(obras)), 2),
    "pior_etapa": np.random.choice(etapas, len(obras)),
    "risco_pior": np.round(np.random.uniform(8.0, 13.0, len(obras)), 2),
    "material_critico": np.random.choice(materiais, len(obras)),
    "taxa_insucesso": np.round(np.random.uniform(0.3, 0.9, len(obras)), 2)
})
rel.to_csv("data/raw/relatorio_consolidadoccbjj.csv", index=False)

print("✅ CSVs simulados e robustos criados em data/raw")

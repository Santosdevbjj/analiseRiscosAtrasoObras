# =====================
# 2. Interface Lateral (Versão à Prova de Falhas)
# =====================
with st.sidebar:
    st.sidebar.image("https://img.icons8.com/fluency/96/construction.png", width=80)
    st.sidebar.header("🕹️ Painel de Controle CCbjj")
    st.markdown("---")
    
    # Função auxiliar para extrair opções ou usar fallback se a coluna for só 'nan'
    def get_safe_options(df, column, default_values):
        if not df.empty and column in df.columns:
            # Filtra nulos e converte para string
            options = df[column].dropna().unique().tolist()
            # Se a lista estiver vazia ou só contiver a string 'nan'
            options = [str(x).title() for x in options if str(x).lower() != 'nan']
            if options:
                return sorted(options)
        return default_values

    # Listas de opções com Fallbacks caso o CSV venha com 'nan'
    cidades_list = get_safe_options(df_base, 'cidade', ['Recife', 'São Paulo', 'Manaus', 'Curitiba'])
    etapas_list = get_options = get_safe_options(df_base, 'etapa', ['Fundação', 'Estrutura', 'Acabamento'])
    solos_list = get_safe_options(df_base, 'tipo_solo', ['Argiloso', 'Arenoso', 'Rochoso', 'Siltoso'])
    materiais_list = get_safe_options(df_base, 'material', ['Cimento', 'Aço', 'Areia', 'Brita'])

    cidade_ui = st.selectbox("Cidade", cidades_list)
    etapa_ui = st.selectbox("Etapa Atual", etapas_list)
    tipo_solo_ui = st.selectbox("Geologia", solos_list)
    material_ui = st.selectbox("Insumo Crítico", materiais_list)
    
    st.divider()
    val_chuva = st.slider("Previsão de Chuva (mm)", 0, 800, 150)
    val_rating = st.slider("Rating de Confiança", 1.0, 5.0, 3.5)

# =====================
# 3. Lógica de Predição (Protegida)
# =====================
if pipeline is None or features_order is None:
    st.error("❌ Erro: Ativos de IA (models/) não encontrados no repositório.")
else:
    # Verificação de segurança: se o usuário não selecionou nada, evita o .lower() no None
    cidade_val = str(cidade_ui).lower() if cidade_ui else "recife"
    etapa_val = str(etapa_ui).lower() if etapa_ui else "fundação"
    solo_val = str(tipo_solo_ui).lower() if tipo_solo_ui else "argiloso"
    material_val = str(material_ui).lower() if material_ui else "cimento"

    input_dict = {
        'orcamento_estimado': 15000000.0,
        'rating_confiabilidade': float(val_rating),
        'taxa_insucesso_fornecedor': 0.15,
        'complexidade_obra': np.log1p(15000000.0),
        'risco_etapa': 0.0,
        'nivel_chuva': float(val_chuva),
        'tipo_solo': solo_val,
        'material': material_val,
        'cidade': cidade_val,
        'etapa': etapa_val
    }

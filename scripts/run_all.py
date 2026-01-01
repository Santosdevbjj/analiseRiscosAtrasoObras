import os
import subprocess
import sys
import time
from tqdm import tqdm

# Configuração de Estilo
BANNER = """
============================================================
       🏗️  CCBJJ - SISTEMA INTEGRADO DE ANTECIPAÇÃO DE RISCO
============================================================
Status: Iniciando Pipeline MLOps...
"""

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def executar_modulo(nome_modulo, script_path):
    """Executa um script python e retorna se houve sucesso."""
    try:
        # shell=True para compatibilidade entre Windows/Linux
        resultado = subprocess.run([sys.executable, script_path], 
                                   capture_output=True, 
                                   text=True)
        
        if resultado.returncode == 0:
            return True, None
        else:
            return False, resultado.stderr
    except Exception as e:
        return False, str(e)

def main():
    limpar_tela()
    print(BANNER)

    # Definição dos estágios do projeto
    etapas = [
        {"nome": "Geração de Dados Brutos", "script": "scripts/gerar_dados.py"},
        {"nome": "Consolidação e Limpeza (Célula 18)", "script": "scripts/consolidar_base.py"},
        {"nome": "Treinamento da IA (Random Forest)", "script": "scripts/train_model.py"},
        {"nome": "BI e Relatórios Executivos (Célula 19)", "script": "scripts/gerar_relatorios.py"}
    ]

    

    # Barra de Progresso Visual
    pbar = tqdm(total=len(etapas), desc="Progresso Geral", bar_format="{l_bar}{bar:30}{r_bar}")

    erros = []

    for etapa in etapas:
        pbar.set_description(f"Processando: {etapa['nome']}")
        
        sucesso, erro_msg = executar_modulo(etapa['nome'], etapa['script'])
        
        if sucesso:
            pbar.update(1)
            time.sleep(0.5) # Pausa dramática para leitura visual
        else:
            erros.append(f"Erro em [{etapa['nome']}]: {erro_msg}")
            break # Interrompe se houver erro crítico

    pbar.close()

    print("\n" + "="*60)
    if not erros:
        print("✅ PIPELINE FINALIZADO COM SUCESSO!")
        print("-" * 60)
        print("📂 RESULTADOS DISPONÍVEIS EM:")
        print("   - Relatórios: /reports/relatorio_top20.csv")
        print("   - Inteligência: /models/pipeline_random_forest.pkl")
        print("   - Dashboard: /reports/charts/status_portfolio.html")
        print("-" * 60)
        print("\n💡 Para iniciar a interface visual, execute:")
        print("   streamlit run scripts/app.py")
    else:
        print("❌ O PIPELINE FALHOU EM UMA ETAPA CRÍTICA:")
        for e in erros:
            print(f"\n{e}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()

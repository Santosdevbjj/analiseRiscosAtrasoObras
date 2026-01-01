import os
import subprocess
import sys
import time

# Configuração de cores para o terminal (opcional, para melhor leitura)
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def log(mensagem, cor=BLUE):
    print(f"{cor}[{time.strftime('%H:%M:%S')}] {mensagem}{RESET}")

def executar_passo(nome, script_path):
    log(f"Iniciando: {nome}...", YELLOW)
    
    if not os.path.exists(script_path):
        log(f"❌ ERRO: Arquivo {script_path} não encontrado.", RED)
        return False

    # Executa o script python como um processo separado
    processo = subprocess.run([sys.executable, script_path], capture_output=True, text=True)

    if processo.returncode == 0:
        log(f"✅ {nome} concluído com sucesso.", GREEN)
        return True
    else:
        log(f"⚠️ FALHA em {nome}:", RED)
        print(f"\n--- LOG DE ERRO ---\n{processo.stderr}\n-------------------")
        return False

def main():
    start_time = time.time()
    
    print("\n" + "="*60)
    print("🏗️  SISTEMA INTEGRADO CCBJJ - INTELECTO DE ENGENHARIA")
    print("="*60 + "\n")

    # Ordem de execução do Pipeline
    pipeline = [
        ("Geração de Dados Sintéticos", "scripts/gerar_dados.py"),
        ("Consolidação de Database (Célula 18)", "scripts/consolidar_base.py"),
        ("Treinamento do Modelo de IA", "scripts/train_model.py"),
        ("Geração de Relatórios e BI (Célula 19)", "scripts/gerar_relatorios.py")
    ]

    

    sucessos = 0
    for nome, script in pipeline:
        if executar_passo(nome, script):
            sucessos += 1
        else:
            log("🛑 Execução interrompida devido a erro crítico no pipeline.", RED)
            break

    total_time = time.time() - start_time
    
    print("\n" + "="*60)
    if sucessos == len(pipeline):
        log(f"🚀 PIPELINE FINALIZADO COM SUCESSO!", GREEN)
        log(f"⏱️  Tempo total de processamento: {total_time:.2f} segundos", BLUE)
        print("\n📂 Ativos disponíveis:")
        print("   - Gráficos: reports/charts/")
        print("   - Modelo IA: models/pipeline_random_forest.pkl")
        print("   - Dashboard: Rode 'streamlit run scripts/app.py'")
    else:
        log("❌ Ocorreram erros durante a execução.", RED)
    print("="*60 + "\n")

if __name__ == "__main__":
    main()

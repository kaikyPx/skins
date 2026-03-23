from playwright.sync_api import sync_playwright
import time
import os
import sys

# Configura o perfil dedicado dentro da pasta do projeto
# Isso permite salvar histórico e logins sem interferir no seu Chrome normal
project_dir = os.path.dirname(os.path.abspath(__file__))
user_data_dir = os.path.join(project_dir, "chrome_bot_profile")

if not os.path.exists(user_data_dir):
    os.makedirs(user_data_dir)
    print(f"Criando novo perfil em: {user_data_dir}")

print("Iniciando Chrome com Playwright (Mesmo motor do Scraper)...")

try:
    with sync_playwright() as p:
        args = [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-notifications",
            "--disable-search-engine-choice-screen",
        ]
        
        # Lança o contexto persistente (igual ao scraper principal)
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=args,
            viewport=None, # Importante para maximizar corretamente
            channel="chrome", # Garante uso do Chrome instalado, não Chromium bundle
            ignore_default_args=["--enable-automation", "--no-sandbox"],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        )
        
        print("Chrome iniciado com sucesso!")
        
        # Scripts de Stealth (Igual ao scraper)
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt']
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)

        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navegando para buff.163.com (Faça login aqui)...")
        try:
            page.goto("https://buff.163.com/market/csgo", timeout=60000)
        except Exception as e:
            print(f"Aviso na navegação inicial: {e}")

        print("\n" + "="*50)
        print("\nO NAVEGADOR ESTÁ ABERTO PARA LOGIN.")
        print("Faça login no site BUFF163 e em qualquer outro serviço necessário.")
        print("Os cookies serão salvos automaticamente neste perfil.")
        print("\nQUANDO TERMINAR, FECHE O NAVEGADOR MANUALMENTE OU FECHE ESTA JANELA.")
        print("="*50 + "\n")

        # Loop infinito mantendo o navegador aberto
        try:
            # Verifica se a página ainda está aberta a cada segundo
            while True:
                if page.is_closed():
                    print("Navegador fechado pelo usuário.")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nEncerrando script via Ctrl+C...")
        
        context.close()
        print("Contexto fechado com segurança.")

except Exception as e:
    print(f"ERRO CRÍTICO: {e}")
    if "already in use" in str(e):
        print("\nATENÇÃO: O perfil já está em uso!")
        print("Feche o scraper principal (botão 'Atualizar Lista' não deve estar rodando)")
        print("e verifique se não há janelas do Chrome abertas.")
    input("\nPressione Enter para sair...")

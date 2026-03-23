from playwright.sync_api import sync_playwright
from src.scrapers.skins_com import SkinsComScraper
import os

def test_scraper(custom_path=None):
    print(f"Testando scraper com path: {custom_path}")
    
    # Configurar ENV se necessário (igual na GUI)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    
    with sync_playwright() as p:
        try:
            headless = False if custom_path else True
            scraper = SkinsComScraper(headless=headless)
            
            print("Iniciando scrape...")
            items = scraper.scrape(p, executable_path=custom_path)
            
            print(f"Sucesso! {len(items)} itens encontrados.")
            for item in items[:3]:
                print(item)
                
        except Exception as e:
            print(f"Erro no teste: {e}")

if __name__ == "__main__":
    # Teste 1: Padrão (sem path customizado)
    print("--- TESTE 1: Padrão ---")
    test_scraper(None)
    
    # Teste 2: Path Inválido (deve dar erro ou fallback dependendo da implementação, mas o Playwright deve lançar exceção se o path não existir)
    print("\n--- TESTE 2: Path Inválido ---")
    test_scraper("C:\\Caminho\\Inexistente\\chrome.exe")
    
    # Teste 3: Path Real (se existir)
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    
    real_path = None
    for path in possible_paths:
        if os.path.exists(path):
            real_path = path
            break
            
    if real_path:
        print(f"\n--- TESTE 3: Path Real ({real_path}) ---")
        test_scraper(real_path)
    else:
        print("\n--- Pulei Teste 3 (Chrome não encontrado nos locais padrão) ---")

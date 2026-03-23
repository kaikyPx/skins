from playwright.sync_api import Playwright
from src.item import SkinItem
import time
import random
import os
import sys
import subprocess


def simulate_human_mouse(page):
    for _ in range(random.randint(2, 4)):
        page.mouse.move(
            random.randint(100, 1200),
            random.randint(100, 800),
            steps=random.randint(5, 15)
        )
        time.sleep(random.uniform(0.2, 0.6))


def simulate_typing_url(page, url):
    # Foca barra de endereço
    page.keyboard.press("Control+L")
    time.sleep(random.uniform(0.2, 0.4))

    # Digita URL como humano
    for char in url:
        page.keyboard.type(char, delay=random.randint(60, 120))

    time.sleep(random.uniform(0.2, 0.4))
    page.keyboard.press("Enter")


class SkinsComScraper:
    def __init__(self):
        self.url = "https://skins.com/market"

    def scrape(
        self,
        playwright: Playwright,
        search_item: str = "",
        search_skin: str = "",
        search_style: str = "",
        float_min: float = 0.0,
        float_max: float = 1.0,
        user_data_dir="chrome_bot_profile",
        executable_path=None,
        on_item_found=None,
        cdp_url=None,
        stattrak_allowed: bool = False
    ):
        items = []
        print(f"🔍 DEBUG: Iniciando scraper Skins.com... (StatTrak: {stattrak_allowed})")
        
        context = None
        
        if cdp_url:
            print(f"🔌 [Skins.com] Conectando a navegador existente em {cdp_url}...")
            try:
                browser = playwright.chromium.connect_over_cdp(cdp_url)
                if len(browser.contexts) > 0:
                    context = browser.contexts[0]
                else:
                    context = browser.new_context()
            except Exception as e:
                print(f"❌ Falha ao conectar via CDP: {e}")
                # Fallback ou re-raise? Melhor falhar se a intenção era usar o navegador aberto
                raise e
        else:
            # 🧹 LIMPA PROCESSOS DO CHROME PARA EVITAR TRAVAMENTO DE PERFIL
            try:
                print("🧹 Fechando processos do Chrome para liberar o perfil...")
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
                else:
                    subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
                time.sleep(2)
            except Exception as e:
                print(f"⚠️ Aviso ao limpar processos: {e}")

            print(f"🔍 DEBUG: Criando contexto persistente (Seguro/Stealth)...")
            args = [
                "--start-maximized",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-notifications",
                "--disable-search-engine-choice-screen",
            ]
            
            try:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel="chrome" if not executable_path else None,
                    executable_path=executable_path,
                    headless=False,
                    args=args,
                    viewport=None,
                    ignore_default_args=["--enable-automation", "--no-sandbox"],
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    ),
                    no_viewport=True,
                )
            except Exception as e:
                print(f"❌ ERRO ao criar contexto: {e}")
                raise

        # 🔐 STEALTH — roda antes de QUALQUER página (apenas se não for CDP ou se quisermos reforçar)
        # Em CDP, não podemos garantir add_init_script em páginas já abertas facilmente sem reload
        try:
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
        except:
            pass

        # 🚀 REUSA A PÁGINA EXISTENTE OU CRIA UMA NOVA
        if len(context.pages) > 0:
            page = context.pages[0]
            # Se for CDP, não fechamos outras páginas para não atrapalhar outros scrapers
            if not cdp_url:
                for extra_page in context.pages[1:]:
                    extra_page.close()
        else:
            page = context.new_page()
            
        print(f"Navegando para {self.url}...")
        try:
            page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
            print(f"🔍 DEBUG: Navegação concluída! URL atual: {page.url}")
        except Exception as e:
            print(f"❌ ERRO na navegação: {e}")
            print(f"🔍 DEBUG: Tentando fechar contexto...")
            context.close()
            raise
        page.bring_to_front()

        # Aguarda a página carregar de fato (espera um elemento chave)
        try:
            print("Aguardando elementos da página (reais)...")
            # Esperamos especificamente pelos cards que NÃO são placeholders
            page.wait_for_selector(".item-listing:not(.item-listing--placeholder)", timeout=60000)
            print("Página carregada com sucesso!")
        except Exception as e:
            if "accounts.google.com" in page.url:
                print("⚠️ REDIRECIONADO PARA LOGIN DO GOOGLE!")
                print("Por favor, faça login manualmente na janela do navegador.")
                print("O scraper aguardará até 5 minutos para você concluir o login...")
                try:
                    # Aguarda até que o login seja concluído e volte para o site original ou o usuário termine
                    page.wait_for_url("**/market**", timeout=300000)
                    print("✅ Login detectado! Continuando...")
                    # Recarrega para garantir que os itens apareçam
                    page.goto(self.url, wait_until="domcontentloaded")
                except:
                    print("❌ Timeout aguardando login ou erro.")
                    print(f"URL atual: {page.url}")
            else:
                print(f"❌ Erro ao aguardar carregamento: {e}")
                print(f"🔍 DEBUG: URL final da página: {page.url}")

        # Pequeno delay extra para garantir renderização completa
        time.sleep(3)

        # 🎯 FILTRO "FACTORY NEW"
        # 🎯 FILTRO "FACTORY NEW"
        # [REMOVIDO A PEDIDO DO USER]
        # O user solicitou remover o filtro explícito de Factory New e confiar apenas no Float.
        # Mantendo o código comentado caso queira reativar.
        '''
        try:
            print("Aplicando filtro 'Factory New'...")
            # Procura pelo container do checkbox de Factory New
            # Baseado nos diagnósticos, está em um generic-checkbox__container
            fn_filter = page.locator(".generic-checkbox__container", has_text="Factory New").first
            if fn_filter.count() > 0:
                # Verifica se já está selecionado (pode ter uma classe --checked ou similar)
                is_checked = "generic-checkbox--checked" in (fn_filter.get_attribute("class") or "")
                if not is_checked:
                    print("Clicando no filtro Factory New...")
                    fn_filter.click()
                    # Aguarda os itens atualizarem
                    page.wait_for_timeout(2000)
                    page.wait_for_selector(".item-listing:not(.item-listing--placeholder)", timeout=15000)
                else:
                    print("Filtro Factory New já está selecionado.")
            else:
                # Tenta por texto direto se o seletor de classe falhar
                fn_btn = page.get_by_text("Factory New", exact=False).first
                if fn_btn.count() > 0:
                    fn_btn.click()
                    page.wait_for_timeout(2000)
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível aplicar o filtro Factory New: {e}")
            # Tenta um scroll se o elemento não estiver visível
            try:
                page.evaluate("window.scrollTo(0, 0)")
            except: pass
        '''
        
        simulate_human_mouse(page)

        # 📜 SCROLL INFINITO para carregar mais itens
        # O site carrega dinamicamente. Vamos rolar até encontrar pelo menos 60 itens ou parar de carregar
        print("📜 Iniciando scroll para carregar mais itens...")
        previous_height = 0
        no_change_count = 0
        
        for i in range(10): # Tenta scrollar até 10 vezes (ajuste conforme necessário)
            # Rola até o fundo
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2) # Aguarda carregamento
            
            # Verifica quantos itens já temos
            count = page.locator(".item-listing:not(.item-listing--placeholder)").count()
            print(f"📜 Scroll {i+1}/10 - Itens visíveis: {count}")
            
            if count >= 60:
                print("✅ Meta de 60 itens atingida!")
                break
                
            # Verifica se a altura da página mudou (se carregou algo novo)
            current_height = page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                no_change_count += 1
                if no_change_count >= 3: # Se não mudar por 3 vezes, parou de carregar
                    print("⚠️ Fim da página ou carregamento estagnado.")
                    break
            else:
                no_change_count = 0
                
            previous_height = current_height
            
            # Pequeno movimento de mouse para "acordar" eventos de scroll se necessário
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))

        # ===== SCRAPING NORMAL =====
        cards = page.locator(".item-listing:not(.item-listing--placeholder)").all()

        for card in cards:
            try:
                category = card.locator(".item-details__category").inner_text().strip()
                name = card.locator(".item-details__name").inner_text().strip()
                full_name = f"{category} | {name}"

                price_text = card.locator(".item-footer__price").inner_text().strip()
                price = float(price_text.replace("$", "").replace(",", ""))

                img = card.locator(".item-image__img img").first
                image_url = img.get_attribute("src") if img.count() > 0 else ""

                # Extração de Float usando Regex no HTML do card
                # O float costuma estar em atributos ou tags que o inner_text() não pega
                # Procuramos por algo como 0.8234, ignorando números muito curtos que podem ser descontos
                card_html = card.evaluate("el => el.innerHTML")
                import re
                # Procuramos por 0. seguido de pelo menos 4 dígitos
                float_matches = re.findall(r"0\.\d{4,}", card_html)
                float_val = float(float_matches[0]) if float_matches else 0.0
                
                if float_val > 0 and not (float_min <= float_val <= float_max):
                    # print(f"⏭️ [Skins.com] Pulando (Float fora da faixa: {float_val}): {full_name}")
                    continue

                items.append(
                    SkinItem(
                        site="skins.com",
                        name=full_name,
                        float_value=float_val,
                        price=price,
                        url=self.url,
                        image_url=image_url
                    )
                )

                if on_item_found:
                    try:
                        on_item_found(items[-1])
                    except Exception as e:
                        print(f"⚠️ Erro no callback on_item_found: {e}")

            except:
                continue

        context.close()
        return items

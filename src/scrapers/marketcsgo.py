from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import random
import re

class MarketCSGOScraper:
    def __init__(self):
        self.base_url = "https://market.csgo.com/pt/"

    def scrape(
        self,
        playwright: Playwright,
        search_item: str,
        search_skin: str,
        search_style: str,
        float_min: float,
        float_max: float,
        user_data_dir="chrome_bot_profile",
        executable_path=None,
        on_item_found=None,
        cdp_url=None,
        stattrak_allowed: bool = False
    ):
        items = []
        count = 0
        print(f"🔍 DEBUG: Iniciando scraper MarketCSGO... (StatTrak: {stattrak_allowed})")
        
        context = None
        
        if cdp_url:
            print(f"🔌 [MarketCSGO] Conectando a navegador existente em {cdp_url}...")
            try:
                browser = playwright.chromium.connect_over_cdp(cdp_url)
                if len(browser.contexts) > 0:
                    context = browser.contexts[0]
                else:
                    context = browser.new_context()
            except Exception as e:
                print(f"❌ Falha ao conectar via CDP: {e}")
                raise e
        else:
            print("⚠️ Iniciando novo contexto (sem CDP)...")
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                viewport=None,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
            )

        # Stealth
        try:
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)
        except:
            pass

        if len(context.pages) > 0:
            page = context.pages[0]
            if not cdp_url:
                for extra_page in context.pages[1:]:
                    extra_page.close()
        else:
            page = context.new_page()

        try:
            # 1. Navegar para base
            print(f"🌍 Navegando para {self.base_url}...")
            page.goto(self.base_url, wait_until="domcontentloaded")
            time.sleep(3) # Aguardar carregamento inicial

            # 2. Busca
            # Termo: Item + skin
            full_search_term = f"{search_item} {search_skin}".strip()
            full_search_term = re.sub(r'\s+', ' ', full_search_term)
            
            print(f"⌨️ Buscando por: '{full_search_term}'")
            
            try:
                # Busca inteligente pelo input
                # Tenta placeholder "Pesquisa rápida" ou "Search" ou genericamente o primeiro input type=text grande
                search_input = page.locator("input[placeholder='Pesquisa rápida']").first
                if not search_input.is_visible():
                    # Tenta outros seletores comuns
                    search_input = page.locator("input[type='text']").first
                
                if search_input.is_visible():
                    search_input.click()
                    search_input.fill("")
                    
                    # Digitação humana
                    for char in full_search_term:
                        page.keyboard.type(char, delay=random.randint(50, 150))
                    
                    time.sleep(0.5)
                    page.keyboard.press("Enter")
                    
                    print("⏳ Aguardando 3 segundos pós-busca...")
                    time.sleep(3)
                else:
                    print("⚠️ Campo de busca não encontrado, tentando navegar via URL direto...")
                
            except Exception as e:
                print(f"⚠️ Erro na busca interativa: {e}")

            # 3. Manipulação de URL
            current_url = page.url
            print(f"🔗 URL Atual: {current_url}")
            
            # https://market.csgo.com/pt/?search=...
            # Adicionar: &phase={estilo}&categories=★&floatMin={float_min}&floatMax={float_max}
            
            # Normalizar estilo: "Phase 1" -> "phase1", "Black Pearl" -> "blackpearl"
            # Remover espaços e lowercase
            normalized_style = search_style.replace(" ", "").lower() if search_style else ""
            
            # Se não tiver ?search=, adiciona ?
            separator = "&" if "?" in current_url else "?"
            
            params = f"categories=★&floatMin={float_min}&floatMax={float_max}"
            if normalized_style:
                params = f"phase={normalized_style}&{params}"
                
            new_url = f"{current_url}{separator}{params}"
            
            # Limpar duplicatas de & ou ? se houver
            new_url = new_url.replace("?&", "?").replace("&&", "&")
            
            print(f"🚀 Navegando para URL Filtrada: {new_url}")
            page.goto(new_url)
            
            # 4. Scroll Infinito
            print("⏳ Aguardando 5 segundos para carregamento da lista...")
            time.sleep(5)
            
            print("📜 Iniciando Scroll Infinito...")
            last_height = page.evaluate("document.body.scrollHeight")
            while True:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3) # Pausa para carregar mais itens
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print("🛑 Fim da página alcançado.")
                    break
                last_height = new_height
                
            # 5. Extração
            print("✅ Processando itens encontrados...")

            # Contar cards iniciais
            item_locator = page.locator("[data-testid='buy-product-card-title-and-quality']")
            item_count = item_locator.count()
            print(f"👀 Encontrados {item_count} potenciais itens.")

            count = 0
            for i in range(item_count):
                try:
                    print(f"\n🔄 Processando item {i+1} de {item_count}...")
                    
                    # Garantir que estamos na página de listagem
                    if "/pt/Knife/" in page.url or "/product/" in page.url:
                        print("⚠️ Detectada página de produto prematura, tentando voltar...")
                        page.go_back()
                        time.sleep(5)

                    # Re-localizar o título
                    current_item_locator = page.locator("[data-testid='buy-product-card-title-and-quality']").nth(i)
                    if not current_item_locator.is_visible():
                        print(f"⚠️ Item {i+1} não está visível, scrollando...")
                        current_item_locator.scroll_into_view_if_needed()
                        time.sleep(1)
                        
                    name = current_item_locator.inner_text().strip()
                    
                    # === FILTRO DE NOME (ESTRITO) ===
                    clean_name = name.replace("StatTrak™ ", "").replace("★ ", "")
                    # Padrão: "Item | Skin (Wear)"
                    if " | " in clean_name:
                        parts = clean_name.split(" | ")
                        item_part = parts[0].strip().lower()
                        skin_full = parts[1].lower()
                        
                        if item_part != search_item.lower():
                            print(f"⏭️ Ignorando (Item incorreto): {name}")
                            continue

                        if search_skin.lower() not in skin_full:
                            print(f"⏭️ Ignorando (Skin incorreta): {name}")
                            continue

                        if "doppler" in search_skin.lower() and "gamma" in skin_full and "gamma" not in search_skin.lower():
                            continue

                        if search_style:
                            # Filtro robusto para Phase: No MarketCSGO, se estamos buscando por Phase, 
                            # o filtro já está na URL. O título raramente contém "Phase X".
                            is_doppler = "doppler" in search_skin.lower()
                            
                            # Se for Doppler, permitimos passar para ver os detalhes
                            if is_doppler:
                                pass # Deixa seguir
                            elif search_style.lower() not in skin_full and search_style.lower().replace(" ", "") not in skin_full.replace(" ", ""):
                                print(f"⏭️ Ignorando (Estilo incorreto): {name}")
                                continue

                    # Ignorar StatTrak se não permitido
                    if not stattrak_allowed and "StatTrak" in name:
                        print(f"⏭️ Ignorando StatTrak: {name}")
                        continue
                    
                    # Verifica se tem a classe 'statTrak'
                    classes = current_item_locator.get_attribute("class") or ""
                    if not stattrak_allowed and "statTrak" in classes:
                        print(f"⏭️ Ignorando StatTrak (classe): {name}")
                        continue

                    print(f"🖱️ Clicando em: {name}")
                    
                    # Clicar para entrar na página do item
                    current_item_locator.click()
                    
                    # Aguardar carregamento dos detalhes
                    print("⏳ Aguardando 10 segundos para carregamento dos detalhes...")
                    time.sleep(10)
                    
                    # Verificar se o item está offline
                    page_content = page.content()
                    if "Este item está offline agora" in page_content or "item is offline" in page_content.lower():
                        print(f"⏭️ Item offline detectado, pulando: {name}")
                        page.go_back()
                        time.sleep(3)
                        continue

                    # --- EXTRAÇÃO NA PÁGINA DE DETALHES ---
                    
                    # Float
                    float_val = 0.0
                    float_el = page.locator("div.float div.res").first
                    if float_el.count():
                        float_text = float_el.inner_text().strip()
                        match = re.search(r"(0\.\d+)", float_text)
                        if match:
                            float_val = float(match.group(1))
                    
                    if float_val > 0 and not (float_min <= float_val <= float_max):
                        print(f"⏭️ [MarketCSGO] Pulando (Float fora da faixa: {float_val}): {name}")
                        page.go_back()
                        time.sleep(3)
                        continue
                    
                    # Porcentagem (Discount)
                    pct_val = 0
                    pct_el = page.locator("span.percent").first
                    if pct_el.count():
                        pct_text = pct_el.inner_text().strip()
                        pct_match = re.search(r"(-?\d+)", pct_text)
                        if pct_match:
                            pct_val = int(pct_match.group(1))

                    # Preço (Mais robusto)
                    price = 0.0
                    # Tenta diferentes seletores para o preço
                    price_selectors = [
                        "app-page-inventory-price .price span",
                        ".price .ng-star-inserted",
                        "div.price span"
                    ]
                    
                    price_text = ""
                    for selector in price_selectors:
                        el = page.locator(selector).first
                        if el.count() > 0:
                            text = el.inner_text().strip()
                            if "$" in text:
                                price_text = text
                                break
                    
                    if price_text:
                        # Parse preço: $1.868,607 -> 1868.607
                        raw_price = price_text.replace("$", "").replace(" ", "").strip()
                        # MarketCSGO usa . para milhar e , para decimal OU vice-versa dependendo da lingua
                        # No exemplo: $1.868,607 -> 1868.607. Então . é milhar e , é decimal.
                        raw_price = raw_price.replace(".", "").replace(",", ".")
                        try:
                            # Converte e arredonda para 2 casas decimais
                            price = round(float(raw_price), 2)
                            print(f"💰 Preço extraído: {price}")
                        except:
                            print(f"⚠️ Falha ao converter preço: {raw_price}")
                    else:
                        print("⚠️ Seletor de preço não encontrou valor com $")

                    # Imagem (Mais robusto)
                    img_url = "https://via.placeholder.com/150"
                    img_selectors = [
                        "div.item-image img",
                        "app-page-inventory-image img",
                        "div.img-block img"
                    ]
                    
                    for selector in img_selectors:
                        el = page.locator(selector).first
                        if el.count() > 0:
                            src = el.get_attribute("src")
                            if src and "http" in src:
                                img_url = src
                                break
                    
                    print(f"🖼️ Imagem: {img_url[:50]}...")

                    # Cria Item
                    item = SkinItem(
                        site="MarketCSGO",
                        name=name,
                        price=price,
                        float_value=float_val,
                        image_url=img_url,
                        url=page.url,
                        percentage=pct_val
                    )

                    items.append(item)
                    count += 1

                    if on_item_found:
                        on_item_found(item)
                    
                    # Voltar para a lista
                    print("🔙 Voltando para a lista...")
                    page.go_back()
                    
                    # Aguardar estabilização
                    print("⏳ Aguardando 5 segundos para a lista estabilizar...")
                    time.sleep(5)
                    
                except Exception as e:
                    print(f"⚠️ Erro ao processar item {i+1}: {e}")
                    # Tenta recuperar voltando para a lista se estiver perdido
                    if "/pt/Knife/" in page.url or "/product/" in page.url:
                        try:
                            page.go_back()
                            time.sleep(5)
                        except:
                            pass
                    continue
        except Exception as ex:
            print(f"❌ Erro no scraper MarketCSGO: {ex}")
        finally:
            if not cdp_url and context:
                context.close()
                
        print(f"✨ {count} itens extraídos do MarketCSGO.")
        return items

from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import random
import re

class CSMoneyScraper:
    def __init__(self):
        self.base_url = "https://cs.money/market/buy"

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
        print(f"🔍 DEBUG: Iniciando scraper CSMoney... (StatTrak: {stattrak_allowed})")
        
        context = None
        
        if cdp_url:
            print(f"🔌 [CSMoney] Conectando a navegador existente em {cdp_url}...")
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
            # Fallback (não deveria ser usado se GUI estiver correta)
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
            page = context.new_context().new_page() if not cdp_url else context.new_page()

        try:
            # 1. Navegar para base
            print(f"🌍 Navegando para {self.base_url}...")
            page.goto(self.base_url, wait_until="domcontentloaded")
            time.sleep(5)

            # 2. Busca
            full_search_term = f"{search_item} {search_skin} {search_style}".strip()
            full_search_term = re.sub(r'\s+', ' ', full_search_term)
            
            print(f"⌨️ Buscando por: '{full_search_term}'")
            
            try:
                # Seletor ajustado conforme pedido: placeholder="Search..."
                search_input = page.locator("input[placeholder='Search...']").first
                search_input.wait_for(state="visible", timeout=10000)
                search_input.click()
                search_input.fill("")
                
                # Digitação humana
                for char in full_search_term:
                    page.keyboard.type(char, delay=random.randint(50, 150))
                
                time.sleep(0.5)
                page.keyboard.press("Enter")
                
                print("⏳ Aguardando 5 segundos pós-busca...")
                time.sleep(5)
                
            except Exception as e:
                print(f"⚠️ Erro na busca: {e}")

            # 3. Construção da URL Otimizada
            current_url = page.url
            print(f"🔗 URL Atual: {current_url}")
            
            # https://cs.money/market/buy/?search=...
            # Adicionar &minFloat=...&maxFloat=...
            
            if "minFloat" in current_url:
                 new_url = re.sub(r"minFloat=[^&]*", f"minFloat={float_min}", current_url)
            else:
                separator = "&" if "?" in current_url else "?"
                new_url = f"{current_url}{separator}minFloat={float_min}"
                
            if "maxFloat" in new_url:
                new_url = re.sub(r"maxFloat=[^&]*", f"maxFloat={float_max}", new_url)
            else:
                new_url = f"{new_url}&maxFloat={float_max}"
                
            # Limpeza
            new_url = new_url.replace("?&", "?").replace("&&", "&")
            
            print(f"🚀 Navegando para URL Filtrada: {new_url}")
            page.goto(new_url)
            
            # Lógica de Rolagem Infinita e Extração Contínua
            print("📜 Iniciando Scroll Infinito e Extração...")
            
            last_height = page.evaluate("document.body.scrollHeight")
            while True:
                # Rola para o fim
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # Aguarda carregamento (User pediu 3s)
                time.sleep(3)
                
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print("🛑 Fim da página alcançado.")
                    break
                last_height = new_height
                
            # Após carregar tudo, extrair itens
            print("✅ Página totalmente carregada. Processando itens...")
            
            float_divs = page.locator("div.csm_8b72a65e.csm_6f5f3612").all()
            print(f"👀 Encontrados {len(float_divs)} possíveis indicadores de float.")
            
            # Se não achar pela classe exata (hash muda?), tenta por texto regex de float
            if len(float_divs) == 0:
                print("⚠️ Classes de float não encontradas. Tentando busca genérica...")
                # Fallback logic later if needed
            
            count = 0
            for float_div in float_divs:
                try:
                    # O card deve ser um pai próximo (avô ou bisavô)
                    # Vamos subir até achar um container que tenha imagem e preço
                    card = float_div.locator("xpath=../../..") # Chute inicial, vamos ajustar
                    
                    # Para garantir que pegamos o card certo, vamos pegar o texto todo dele
                    text_content = card.inner_text()
                    
                    # 1. Filtro de StatTrak
                    is_st = "ST" in text_content or "StatTrak" in text_content
                    if is_st and not stattrak_allowed:
                        print(f"⏭️ [CS.Money] Pulando StatTrak (Não permitido): {text_content[:50]}...")
                        continue
                        
                    # 2. Extrair Preço
                    price_match = re.search(r"\$\s*([\d\s,]+\.?\d*)", text_content)
                    if not price_match:
                        print(f"⏭️ [CS.Money] Pulando (Preço não encontrado): {text_content[:50]}...")
                        continue
                    
                    raw_price = price_match.group(1).replace(" ", "").replace("\xa0", "").replace(",", "")
                    try:
                        price = float(raw_price)
                    except:
                        print(f"⏭️ [CS.Money] Pulando (Erro no parse do preço: {raw_price})")
                        continue
                    
                    # 3. Extrair Float
                    float_match = re.search(r"0\.(\d{4,})", text_content)
                    if float_match:
                        float_val = float(f"0.{float_match.group(1)}")
                    else:
                        float_val = 0.0
                        
                    if not (float_min <= float_val <= float_max):
                        print(f"⏭️ [CS.Money] Pulando (Float fora da faixa: {float_val}): {text_content[:50]}...")
                        continue
                        
                    # 4. Nome e Imagem
                    imgs = card.locator("img").all()
                    img_url = "https://via.placeholder.com/150"
                    name = "Unknown Item"
                    found_valid_img = False
                    target_name_part = search_item.lower() if search_item else ""
                    
                    for img in imgs:
                        alt_text = img.get_attribute("alt")
                        if not alt_text: continue
                        alt_lower = alt_text.lower()
                        if "sticker" in alt_lower: continue
                        img_url = img.get_attribute("src")
                        name = alt_text
                        found_valid_img = True
                        if target_name_part and target_name_part in alt_lower:
                            break
                    
                    if not found_valid_img:
                        print(f"⏭️ [CS.Money] Pulando (Imagem/Nome não encontrado): {text_content[:50]}...")
                        continue

                    # 5. Filtro de Nome (Estrito)
                    clean_name = name.replace("StatTrak™ ", "").replace("StatTrak ", "").replace("★ ", "")
                    if " | " in clean_name:
                        parts = clean_name.split(" | ")
                        item_part = parts[0].strip().lower()
                        skin_base = parts[1].lower()
                        
                        if item_part != search_item.lower():
                            print(f"⏭️ [CS.Money] Pulando (Item mismatch: '{item_part}' != '{search_item.lower()}'): {name}")
                            continue

                        if search_skin.lower() not in skin_base and search_skin.lower() not in name.lower():
                            print(f"⏭️ [CS.Money] Pulando (Skin mismatch: '{search_skin.lower()}' não em '{name}'): {name}")
                            continue

                        if "doppler" in search_skin.lower() and "gamma" in name.lower() and "gamma" not in search_skin.lower():
                            print(f"⏭️ [CS.Money] Pulando (Gamma Doppler filtrado): {name}")
                            continue

                        if search_style and search_style.lower() not in name.lower():
                            print(f"⏭️ [CS.Money] Pulando (Estilo mismatch: '{search_style.lower()}' não em '{name}'): {name}")
                            continue
                    
                    print(f"✅ [CS.Money] Item aceito: {name} (Float: {float_val}, Preço: ${price})")
                    item = SkinItem(
                        site="CS.Money",
                        name=name,
                        price=price,
                        float_value=float_val,
                        image_url=img_url,
                        url=page.url 
                    )
                    
                    items.append(item)
                    count += 1
                    
                    if on_item_found:
                        on_item_found(item)
                        
                except Exception as e:
                    # print(f"Erro ao processar card: {e}")
                    pass
            print(f"✨ {count} itens extraídos do CS.Money.")
        except Exception as ex:
            print(f"❌ Erro no scraper CSMoney: {ex}")
        finally:
            if not cdp_url and context:
                context.close()
                
        return items

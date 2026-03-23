from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import random
import re

class CSFloatScraper:
    def __init__(self):
        self.base_url = "https://csfloat.com/search"

    def scrape(
        self,
        playwright: Playwright,
        search_item: str,
        search_skin: str,
        search_style: str,
        float_min: float,
        float_max: float,
        stattrak_allowed: bool = False,
        user_data_dir="chrome_bot_profile",
        executable_path=None,
        on_item_found=None,
        cdp_url=None
    ):
        items = []
        print(f"🔍 DEBUG: Iniciando scraper CSFloat... (StatTrak: {stattrak_allowed})")
        
        context = None
        
        if cdp_url:
            print(f"🔌 [CSFloat] Conectando a navegador existente em {cdp_url}...")
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
            # Lançamento padrão se não for via CDP (fallback)
            args = [
                "--start-maximized",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-notifications",
                "--disable-blink-features=AutomationControlled",
            ]
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                executable_path=executable_path,
                headless=False,
                args=args,
                viewport=None,
                ignore_default_args=["--enable-automation", "--no-sandbox"],
                no_viewport=True,
            )

        # Stealth básico
        try:
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)
        except:
            pass

        if len(context.pages) > 0:
            page = context.pages[0]
            if not cdp_url: # Só fecha se formos donos do contexto
                for extra_page in context.pages[1:]:
                    extra_page.close()
        else:
            page = context.new_context().new_page() if not cdp_url else context.new_page()

        try:
            # 1. Navegar para a busca inicial
            print(f"🌍 Navegando para {self.base_url}...")
            page.goto(self.base_url, wait_until="domcontentloaded")
            time.sleep(3)

            # 2. Realizar a busca para obter os IDs (def_index, paint_index)
            full_search_term = f"{search_item} {search_skin} {search_style}".strip()
            # Remove espaços duplos
            full_search_term = re.sub(r'\s+', ' ', full_search_term)
            
            print(f"⌨️ Buscando por: '{full_search_term}'")
            
            try:
                # Tenta encontrar o input de busca inicial (que abre o overlay)
                # Geralmente é um input dentro de um form ou com placeholder de busca
                search_trigger = page.locator("input[placeholder*='Search'], input[type='search']").first
                search_trigger.click()
                
                print("⏳ Aguardando 6 segundos para o overlay de busca aparecer...")
                time.sleep(6)
                
                # Localiza o input real do overlay pelo ID fornecido
                search_input = page.locator("#spotlight-overlay-input")
                
                # Garante que está visível e focado
                search_input.wait_for(state="visible", timeout=10000)
                search_input.click()
                
                # Limpa e digita
                search_input.fill("")
                # Digitação humana
                for char in full_search_term:
                    page.keyboard.type(char, delay=random.randint(50, 150))
                
                time.sleep(0.5)
                page.keyboard.press("Enter")
                
                print("⏳ Aguardando 6 segundos após busca...")
                time.sleep(6)

                # Clica fora para remover foco (em uma área neutra)
                try:
                    page.mouse.click(10, 10)
                except:
                    pass
                
                print("⏳ Verificando atualização da URL com parâmetros...")
                # Espera até que a URL contenha 'def_index' ou mude significativamente
                # Timeout de 10s
                for _ in range(20):
                    if "def_index" in page.url:
                        break
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"⚠️ Erro na interação de busca: {e}")

            # 3. Manipular a URL
            current_url = page.url
            print(f"🔗 URL Pós-Busca: {current_url}")
            
            if "def_index" in current_url:
                print(f"⚙️ Ajustando parâmetros da URL... (StatTrak Allowed: {stattrak_allowed})")
                print(f"🔗 URL Original: {current_url}")
                
                # Gerencia category=1 (Skin normal) vs Todos (Normal + StatTrak)
                if not stattrak_allowed:
                    if "category=1" not in current_url:
                        if "?" in current_url:
                            new_url = current_url.replace("?", "?category=1&")
                        else:
                            new_url = current_url + "?category=1"
                    else:
                        new_url = current_url
                else:
                    # Remove category=1 para permitir StatTrak + Normal
                    new_url = current_url.replace("category=1&", "").replace("&category=1", "").replace("category=1", "")

                # Substitui/Adiciona min_float e max_float
                # Remove existentes primeiro para limpar
                new_url = re.sub(r"min_float=[^&]*&?", "", new_url)
                new_url = re.sub(r"max_float=[^&]*&?", "", new_url)
                
                # Adiciona os novos no final (ou inicio, ordem nao importa tanto mas user pediu formato especifico)
                # O user pediu: https://csfloat.com/search?category=1&max_float=0.02&def_index=507&paint_index=420
                # Vamos garantir que min_float e max_float estejam lá
                
                # Remove trailing & or ?
                if new_url.endswith("&") or new_url.endswith("?"):
                    new_url = new_url[:-1]
                    
                separator = "&" if "?" in new_url else "?"
                new_url = f"{new_url}{separator}min_float={float_min}&max_float={float_max}"
                
                # Limpeza de && duplicados
                new_url = new_url.replace("&&", "&")
                
                print(f"🚀 Navegando para URL Otimizada: {new_url}")
                page.goto(new_url)
                time.sleep(3) # Aguarda carregamento inicial
                
            else:
                print("⚠️ URL não mudou conforme esperado (sem def_index). Tentando continuar assim mesmo...")

            # 4. Scroll Infinito e Extração
            print("📜 Iniciando Scroll e Extração...")
            
            seen_ids = set()
            last_height = 0
            consecutive_no_change = 0
            debug_saved = False
            
            while True:
                # Extrai itens visíveis
                # Seletor baseado na análise: .item-card
                cards = page.locator("app-item-card, .item-card").all()
                print(f"👀 Encontrados {len(cards)} cards na tela.")
                
                new_items_count = 0
                
                for card in cards:
                    try:
                        # Tenta extrair dados
                        text_content = card.inner_text()
                        
                        # Nome
                        # Tenta pegar .item-name ou primeira linha
                        name_el = card.locator(".item-name").first
                        name = name_el.inner_text().strip() if name_el.count() > 0 else "Unknown Item"
                        
                        # Preço
                        # Procura por $
                        price_match = re.search(r"\$\s*([\d,]+\.?\d*)", text_content)
                        price = float(price_match.group(1).replace(",", "")) if price_match else 0.0
                        
                        # Float
                        # Tenta pegar diretamente do elemento .wear (mais preciso)
                        wear_el = card.locator(".wear").first
                        if wear_el.count() > 0:
                            wear_text = wear_el.inner_text().strip()
                            try:
                                float_val = float(wear_text)
                            except:
                                float_val = 0.0
                        else:
                            # Fallback: Procura padrão 0.XXXX no texto geral
                            float_match = re.search(r"0\.\d+", text_content)
                            float_val = float(float_match.group(0)) if float_match else 0.0
                        
                        # ID único (usando link ou algo do gênero para evitar duplicatas)
                        # Se não tiver link fácil, usamos combinação de float + preço
                        item_id = f"{name}-{price}-{float_val}"
                        

                        # Filtro de preço 0.0 e float 0.0
                        if price == 0.0 or float_val == 0.0:
                            print(f"⚠️ [Ignorado] Item inválido (Preço: {price}, Float: {float_val}): {name}")
                            continue

                        if item_id in seen_ids:
                            # print(f"⚠️ [Ignorado] ID duplicado: {item_id}")
                            continue
                            
                        seen_ids.add(item_id)
                        
                        # Imagem
                        img_el = card.locator("img").first
                        img_url = img_el.get_attribute("src") if img_el.count() > 0 else ""
                        
                        # Filtro StatTrak
                        if not stattrak_allowed and "StatTrak" in name:
                            print(f"❌ [Ignorado] StatTrak não permitido: {name}")
                            continue
                        
                        # === FILTRO DE NOME (ESTRITO) ===
                        clean_name = name.replace("StatTrak™ ", "").replace("★ ", "")
                        if " | " in clean_name:
                            parts = clean_name.split(" | ")
                            item_part = parts[0].strip().lower()
                            skin_base = parts[1].lower()
                            
                            if item_part != search_item.lower():
                                print(f"❌ [Ignorado] Nome incorreto: '{item_part}' != '{search_item.lower()}' (Full: {name})")
                                continue
                            
                            # Check core skin name
                            if search_skin.lower() not in skin_base and search_skin.lower() not in text_content.lower():
                                print(f"❌ [Ignorado] Skin incorreta: '{skin_base}' não contém '{search_skin.lower()}' (Full: {name})")
                                continue
                                
                            # Exclusive: Gamma Doppler protection
                            if "doppler" in search_skin.lower() and "gamma" in text_content.lower() and "gamma" not in search_skin.lower():
                                print(f"❌ [Ignorado] Gamma Doppler detectado para busca de Doppler normal: {name}")
                                continue
                                
                            # If style is specified, it must be present anywhere in the card
                            if search_style and search_style.lower() not in text_content.lower():
                                print(f"❌ [Ignorado] Estilo '{search_style}' não encontrado em: {name}")
                                continue

                        # Filtra por float se a busca da URL falhou (redundância)
                        # REMOVIDO A PEDIDO: Confiar no filtro da URL
                        # if not (float_min <= float_val <= float_max):
                        #     print(f"❌ [Ignorado] Float fora do range: {float_val} (Min: {float_min}, Max: {float_max}) - {name}")
                        #     continue
                            
                        item = SkinItem(
                            site="CSFloat",
                            name=name,
                            price=price,
                            float_value=float_val,
                            image_url=img_url,
                            url=page.url # Link da busca, já que link direto pode ser popup
                        )
                        
                        items.append(item)
                        new_items_count += 1
                        
                        if on_item_found:
                            on_item_found(item)
                            
                    except Exception as e:
                        print(f"Erro ao extrair card: {e}")
                        continue
                
                print(f"✨ +{new_items_count} novos itens extraídos.")
                
                if not debug_saved and len(items) > 0:
                    try:
                        with open("csfloat_debug.html", "w", encoding="utf-8") as f:
                            f.write(page.content())
                        print("📄 HTML de debug salvo em 'csfloat_debug.html'")
                        debug_saved = True
                    except Exception as e:
                        print(f"⚠️ Erro ao salvar HTML de debug: {e}")
                
                # Scroll
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                try:
                    page.keyboard.press("End")
                except:
                    pass
                time.sleep(2) # Aguarda carregamento
                
                # Verifica fim
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print("⏳ Pareceu chegar ao fim, aguardando 7 segundos para confirmar...")
                    time.sleep(7)
                    new_height = page.evaluate("document.body.scrollHeight")
                    
                    if new_height == last_height:
                        consecutive_no_change += 1
                        if consecutive_no_change >= 2:
                            print("🏁 Fim da página alcançado.")
                            break
                    else:
                        consecutive_no_change = 0
                        last_height = new_height
                else:
                    consecutive_no_change = 0
                    last_height = new_height
                    
                # Limite de segurança
                if len(items) > 500:
                    print("🛑 Limite de segurança de 500 itens atingido.")
                    break
        except Exception as ex:
            print(f"❌ Erro no scraper CSFloat: {ex}")
        finally:
            if not cdp_url and context:
                context.close()
                
        return items

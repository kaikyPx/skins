from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import urllib.parse
import re

class RapidSkinsScraper:
    def __init__(self):
        self.base_url = "https://www.rapidskins.com"

    def _scroll_to_end(self, page: Page, max_scrolls: int = 50, selector: str = ""):
        print(f"📜 [RapidSkins] Iniciando Scroll Infinito (Max {max_scrolls} scrolls)...")
        
        try:
            # Em sites Vue/React com virtual scroll, scrollar o contêiner ou a página
            last_height = page.evaluate("document.body.scrollHeight")
        except Exception:
            print("⚠️ [RapidSkins] Erro ao obter altura inicial da página.")
            return

        last_count = 0
        if selector:
            try:
                last_count = len(page.query_selector_all(selector))
            except Exception: pass
        
        scroll_count = 0
        no_change_count = 0
        
        while scroll_count < max_scrolls:
            try:
                # Scroll para o final
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)  # Aguarda carregar
                
                new_height = page.evaluate("document.body.scrollHeight")
                new_count = last_count
                if selector:
                    new_count = len(page.query_selector_all(selector))
                
                # Verifica se algo mudou
                if new_height == last_height and new_count == last_count:
                    no_change_count += 1
                    if no_change_count >= 2:
                        print("🛑 [RapidSkins] Fim da página ou nenhum item novo.")
                        break
                    page.evaluate("window.scrollBy(0, -300)")
                    time.sleep(1)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                else:
                    no_change_count = 0
                    
                last_height = new_height
                last_count = new_count
                scroll_count += 1
                if scroll_count % 5 == 0:
                    print(f"📜 [RapidSkins] Scroll {scroll_count}... (Itens detectados: {new_count})")
            except Exception as e:
                print(f"⚠️ [RapidSkins] Interrupção no scroll: {e}")
                break

    def scrape(
        self,
        playwright: Playwright,
        search_item: str,
        search_skin: str,
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
        # Prepara a query de busca (Apenas Item + Skin, filtro por estilo é feito depois)
        full_query = f"{search_item} {search_skin}".strip()
        
        encoded_query = urllib.parse.quote(full_query)
        search_url = f"{self.base_url}/buy?search={encoded_query}"
        
        print(f"🔍 [RapidSkins] Iniciando busca para: {full_query} (StatTrak: {stattrak_allowed})")
        print(f"🚀 [RapidSkins] Navegando para: {search_url}")

        context = None
        try:
            if cdp_url:
                browser = playwright.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else browser.new_context()
            else:
                browser = playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    executable_path=executable_path,
                    headless=False
                )
                context = browser

            # Tenta reutilizar uma aba existente da RapidSkins para evitar múltiplas guias
            page = None
            if context and context.pages:
                for p in context.pages:
                    try:
                        if "rapidskins.com" in p.url:
                            page = p
                            print(f"♻️ [RapidSkins] Reutilizando aba existente: {p.url}")
                            break
                    except: continue
            
            if not page:
                page = context.new_page()

            page.goto(search_url)
            page.wait_for_load_state("networkidle")
            
            # Aguarda os itens carregarem (RapidSkins usa virtual scroll dinâmico)
            time.sleep(5)

            # Scroll para carregar itens
            self._scroll_to_end(page, max_scrolls=30, selector="div.inventory-item")

            # Extração
            cards = page.query_selector_all("div.inventory-item")
            print(f"👀 [RapidSkins] Encontrados {len(cards)} cards de itens.")

            # Mapping para fases (Phase 1 -> P1, etc)
            phase_map = {
                "phase 1": ["phase 1", "p1"],
                "phase 2": ["phase 2", "p2"],
                "phase 3": ["phase 3", "p3"],
                "phase 4": ["phase 4", "p4"],
                "ruby": ["ruby"],
                "sapphire": ["sapphire"],
                "black pearl": ["black pearl", "bp"]
            }

            for i, card in enumerate(cards):
                try:
                    # 1. Nome e Style
                    cat_el = card.query_selector(".item-text-small")
                    category = cat_el.inner_text().strip() if cat_el else ""
                    
                    skin_el = card.query_selector(".font-weight-black")
                    skin_val = skin_el.inner_text().strip() if skin_el else ""
                    
                    full_name = f"{category} | {skin_val}"
                    
                    # 2. StatTrak
                    is_st = "StatTrak" in full_name or "ST" in full_name
                    if not is_st:
                        style_attr = skin_el.get_attribute("style") if skin_el else ""
                        if style_attr and ("rgb(255, 134, 0)" in style_attr or "orange" in style_attr):
                            is_st = True

                    print(f"📦 [RapidSkins] Card {i+1}: '{full_name}' | ST: {is_st}")

                    # Filtro StatTrak (Se stattrak_allowed for True, mostramos AMBOS. Se False, apenas normais.)
                    if not stattrak_allowed and is_st:
                        print(f"  ⏩ Ignorado: StatTrak desabilitado.")
                        continue

                    # 3. Preço
                    price_el = card.query_selector(".item-text-medium")
                    price_str = price_el.inner_text().strip() if price_el else "0"
                    price = float(re.sub(r'[^\d.]', '', price_str))

                    # 4. Imagem
                    img_el = card.query_selector(".item-image img")
                    image_url = img_el.get_attribute("src") if img_el else ""

                    # 5. Estilo / Phase
                    match_style = True
                    if search_style:
                        s_style_lower = search_style.lower().strip()
                        # Normaliza o texto do item para facilitar a comparação
                        item_text_lower = f"{full_name} {skin_val}".lower().replace(" ", "").replace("-", "").replace("|", "")
                        
                        # Mapping expandido
                        phase_map = {
                            "phase 1": ["phase1", "p1"],
                            "phase 2": ["phase2", "p2"],
                            "phase 3": ["phase3", "p3"],
                            "phase 4": ["phase4", "p4"],
                            "p1": ["phase1", "p1"],
                            "p2": ["phase2", "p2"],
                            "p3": ["phase3", "p3"],
                            "p4": ["phase4", "p4"],
                            "ruby": ["ruby"],
                            "sapphire": ["sapphire"],
                            "black pearl": ["black pearl", "bp"]
                        }
                        
                        variants = phase_map.get(s_style_lower, [s_style_lower])
                        # Normaliza variantes
                        variants_norm = [v.lower().replace(" ", "").replace("-", "") for v in variants]
                        
                        if not any(v in item_text_lower for v in variants_norm):
                            print(f"  ⏩ Ignorado: Estilo '{search_style}' não encontrado no item. (Buscado: {variants_norm} em {item_text_lower})")
                            match_style = False
                    
                    if not match_style:
                        continue

                    # 6. Float (Hover Logic)
                    float_val = 0.0
                    try:
                        print(f"  🖱️ Hover no card para extrair float...")
                        # Garante que o card está visível antes do hover
                        card.scroll_into_view_if_needed()
                        card.hover()
                        time.sleep(2.5) 
                        
                        page_html = page.content()
                        # Procura por float no HTML (frequentemente injetado via tooltip)
                        float_matches = re.findall(r'0\.\d{2,20}', page_html)
                        
                        if float_matches:
                            float_val = float(float_matches[-1]) 
                            print(f"  ✨ Float detectado: {float_val}")
                        else:
                            # Tenta via seletor de tooltip conhecido ou genérico
                            tooltip = page.locator(".v-tooltip__content, .v-overlay__content").last
                            if tooltip.count() > 0:
                                t_text = tooltip.inner_text()
                                tm = re.search(r'0\.\d+', t_text)
                                if tm:
                                    float_val = float(tm.group())
                                    print(f"  ✨ Float detectado via tooltip: {float_val}")

                    except Exception as e:
                        print(f"  ⚠️ Erro no hover/float: {e}")

                    # Filtro de Float
                    if float_val < float_min or float_val > float_max:
                        # Se não detectou float (0.0), mas o range exige float baixo, ignoramos
                        # A menos que o range seja o padrão 0-1
                        if float_val > 0 or (float_min > 0 or float_max < 1):
                            print(f"  ⏩ Ignorado: Float {float_val} fora do range {float_min}-{float_max}")
                            continue

                    item_url = page.url 

                    new_item = SkinItem(
                        site="RapidSkins",
                        name=full_name,
                        float_value=str(float_val),
                        price=price,
                        url=item_url,
                        image_url=image_url
                    )

                    print(f"  🎯 ADICIONADO: ${price}")
                    if on_item_found:
                        on_item_found(new_item)
                    items.append(new_item)

                except Exception as e:
                    print(f"⚠️ [RapidSkins] Erro ao extrair card: {e}")

            print(f"✅ [RapidSkins] Scraping finalizado. {len(items)} itens extraídos.")
            return items

        except Exception as e:
            print(f"❌ [RapidSkins] Erro durante o scraping: {e}")
            return items
        finally:
            if context and not cdp_url:
                context.close()

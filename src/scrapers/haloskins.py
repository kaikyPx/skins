from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import urllib.parse
import re

class HaloSkinsScraper:
    def __init__(self):
        self.base_url = "https://www.haloskins.com"




    def _scroll_to_end(self, page: Page, max_scrolls: int = 50, selector: str = ""):
        print(f"📜 [HaloSkins] Iniciando Scroll Infinito (Max {max_scrolls} scrolls)...")
        
        try:
            last_height = page.evaluate("document.body.scrollHeight")
        except Exception:
            print("⚠️ [HaloSkins] Erro ao obter altura inicial da página.")
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
                
                # Verifica se algo mudou (altura ou contagem de itens)
                if new_height == last_height and new_count == last_count:
                    no_change_count += 1
                    if no_change_count >= 2: # Tenta 2 vezes antes de desistir
                        print("🛑 [HaloSkins] Fim da página ou nenhum item novo por 2 tentativas.")
                        break
                    # Tenta um "empurrão" pra cima e pra baixo
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
                    print(f"📜 [HaloSkins] Scroll {scroll_count}... (Itens detectados: {new_count})")
            except Exception as e:
                print(f"⚠️ [HaloSkins] Interrupção no scroll (possível navegação ou erro de contexto): {e}")
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
        print(f"🔍 [HaloSkins] Iniciando busca para: {search_item} | {search_skin} (Estilo: {search_style}, StatTrak: {stattrak_allowed})")

        # Mapeamento de Estilo para HaloSkins Tags (Detail Page)
        style_map = {
            "phase 1": "P1",
            "phase 2": "P2",
            "phase 3": "P3",
            "phase 4": "P4",
            "ruby": "Ruby",
            "sapphire": "Sapphire",
            "black pearl": "Black Pearl",
            "emerald": "Emerald"
        }
        target_tag = style_map.get(search_style.lower(), search_style)

        context = None
        if cdp_url:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                viewport=None,
                args=["--start-maximized"]
            )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Busca no Market
            query = f"{search_item} {search_skin}".strip().replace(" ", "+")
            search_url = f"{self.base_url}/market?keyword={query}"
            print(f"🚀 [HaloSkins] Abrindo site para verificação: {search_url}")
            page.goto(search_url)
            
            print("⏳ [HaloSkins] Aguardando 1:30 minuto para verificação do site...")
            time.sleep(90)

            # Re-navega para garantir que estamos na página com um contexto de execução estável pós-verificação
            print(f"🔄 [HaloSkins] Recarregando busca para iniciar carregamento...")
            page.goto(search_url)
            page.wait_for_load_state("load")
            time.sleep(5) # Pequeno buffer extra para garantir scripts carregados

            # Scroll no Market para garantir que todos os cards/tipos carregaram
            self._scroll_to_end(page, max_scrolls=20, selector="a.cursor-pointer.relative.animateFloat.hover_sd.rounded")

            # 2. Localizar os cards corretos
            cards = page.query_selector_all("a.cursor-pointer.relative.animateFloat.hover_sd.rounded")
            target_hrefs = []

            print(f"👀 [HaloSkins] Analisando {len(cards)} cards no market...")
            for card in cards:
                try:
                    name_el = card.query_selector("h4")
                    if not name_el: continue
                    name_text = name_el.inner_text()
                    
                    # Check condition (FN, MW, etc)
                    condition_tag = card.query_selector("div.text-xs")
                    condition_text = condition_tag.inner_text() if condition_tag else ""
                    
                    # Check StatTrak
                    # No HaloSkins, cards com ST geralmente tem um ícone ou ST no texto
                    is_st = "ST" in card.inner_html() or "StatTrak" in name_text
                    
                    match_name = search_item.lower() in name_text.lower() and search_skin.lower() in name_text.lower()
                    
                    # Logica StatTrak Atualizada:
                    # Se stattrak_allowed for True, aceitamos ST E não-ST.
                    # Se stattrak_allowed for False, aceitamos APENAS não-ST.
                    if stattrak_allowed:
                        match_st = True # Aceita qualquer um
                    else:
                        match_st = not is_st # Aceita apenas se NÃO for ST
                    
                    if match_name and match_st:
                        # Se tiver Factory New no nome ou FN na tag
                        if "(Factory New)" in name_text or "FN" in condition_text:
                            href = card.get_attribute("href")
                            if href and href not in target_hrefs:
                                target_hrefs.append(href)
                                print(f"✅ [HaloSkins] Card identificado: {name_text} (ST: {is_st})")
                except Exception:
                    continue

            if not target_hrefs:
                print("❌ [HaloSkins] Nenhum card correspondente encontrado no market.")
                return items

            # 3. Iterar pelos cards encontrados (Pode ser um ST e um normal)
            for target_href in target_hrefs:
                detail_url = f"{self.base_url}{target_href}"
                print(f"🚀 [HaloSkins] Navegando para página de detalhes: {detail_url}")
                page.goto(detail_url)
                page.wait_for_load_state("load")
                
                print("⏳ [HaloSkins] Aguardando 20 segundos para carregamento dos detalhes...")
                time.sleep(20)

                # 4. Scroll infinito na página de detalhes
                self._scroll_to_end(page, max_scrolls=100, selector="div.list_hover")

                # 5. Extrair listagens
                list_items = page.query_selector_all("div.list_hover")
                print(f"👀 [HaloSkins] {len(list_items)} listagens totais nesta página.")

                # Precisamos saber se ESTA página é de um StatTrak ou não para o nome
                parent_name_el = page.query_selector("h3.text-textPrimary")
                current_is_st = False
                if parent_name_el:
                    parent_name = parent_name_el.inner_text()
                    current_is_st = "StatTrak" in parent_name or "ST" in parent_name

                for div in list_items:
                    try:
                        # Float
                        float_div = div.query_selector("div.text-textPrimary.text-xs")
                        if not float_div: continue
                        
                        float_val_text = float_div.inner_text().strip()
                        float_match = re.search(r"0\.\d+", float_val_text)
                        if not float_match: continue
                        f_val = float(float_match.group())

                        if not (float_min <= f_val <= float_max):
                            continue

                        # Preço
                        price_span = div.query_selector("span.numFont")
                        if not price_span: continue
                        price = float(price_span.inner_text().replace(",", ""))

                        # Estilo/Phase
                        tags = div.query_selector_all("div.px-1.w-fit.rounded-sm.text-xs")
                        item_style = ""
                        for tag in tags:
                            tag_text = tag.inner_text().strip()
                            if tag_text in ["P1", "P2", "P3", "P4", "Ruby", "Sapphire", "BP", "Emerald"]:
                                item_style = tag_text
                                break
                        
                        # Filtro de Estilo
                        if target_tag and target_tag.lower() not in ["p1", "p2", "p3", "p4"]:
                            if target_tag.lower() not in item_style.lower():
                                continue
                        elif target_tag and target_tag.upper() in ["P1", "P2", "P3", "P4"]:
                            if target_tag.upper() != item_style.upper():
                                continue

                        # Imagem
                        img_el = div.query_selector('img[width="96"]')
                        image_url = img_el.get_attribute("src") if img_el else ""

                        # Criar Item
                        full_name = f"{'★ StatTrak™ ' if current_is_st else '★ '}{search_item} | {search_skin} (Factory New)"
                        if item_style:
                            full_name = full_name.replace("(Factory New)", f"({item_style}) (Factory New)")

                        new_item = SkinItem(
                            site="HaloSkins",
                            name=full_name,
                            float_value=f_val,
                            price=price,
                            url=detail_url,
                            image_url=image_url
                        )
                        
                        items.append(new_item)
                        if on_item_found:
                            on_item_found(new_item)
                        
                        print(f"✅ [HaloSkins] Item adicionado: {full_name} ({f_val}) - ${price}")

                    except Exception as e:
                        print(f"⚠️ [HaloSkins] Erro ao extrair item individual: {e}")

        except Exception as ex:
            print(f"❌ [HaloSkins] Erro no scraper: {ex}")

        return items

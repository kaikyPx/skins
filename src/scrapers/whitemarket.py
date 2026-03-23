from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import re
import urllib.parse

class WhiteMarketScraper:
    def __init__(self):
        self.base_url = "https://white.market/pt/market"

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
        print(f"🔍 [White Market] Iniciando busca para: {search_item} | {search_skin} (StatTrak Permitido: {stattrak_allowed})")
        
        context = None
        if cdp_url:
            try:
                browser = playwright.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else browser.new_context()
            except Exception as e:
                print(f"❌ Falha ao conectar White Market via CDP: {e}")
                return items
        else:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                viewport=None,
                args=["--start-maximized"]
            )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Construir URL
            # Sempre buscamos pelo nome base para trazer Normal + StatTrak na mesma lista
            query_name = f"{search_item} {search_skin}".strip()

            params = {
                "name": query_name,
                "float-from": str(float_min),
                "float-to": str(float_max)
            }
            url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
            print(f"🚀 White Market: Navegando para {url}")
            
            page.goto(url)
            print("⏳ Aguardando 5 segundos para carregamento...")
            time.sleep(5)

            # 2. Extração Inicial (Cards de Busca)
            cards = page.locator("div[class*='item-card']").all()
            print(f"👀 White Market: Encontrados {len(cards)} potenciais itens na busca inicial.")

            variant_cards = []
            
            for card in cards:
                try:
                    card_text = card.inner_text().strip()
                    if not card_text: continue
                    
                    card_text_lower = card_text.lower()
                    
                    # --- FILTRAGEM ---
                    
                    # 1. Filtro de Nome (Item e Skin)
                    if search_item.lower() not in card_text_lower or search_skin.lower() not in card_text_lower:
                        continue
                        
                    # 2. Proteção Doppler vs Gamma Doppler (Estrita)
                    if "doppler" in search_skin.lower() and "gamma" in card_text_lower and "gamma" not in search_skin.lower():
                        continue
                        
                    # 3. Estilo / Phase
                    if search_style:
                        style_clean = search_style.lower().replace(" ", "")
                        if style_clean not in card_text_lower.replace(" ", ""):
                            continue

                    # 4. StatTrak
                    is_st = any(x in card_text for x in ["StatTrak", "ST™", "ST "])
                    if is_st and not stattrak_allowed:
                        print(f"⏭️ [White Market] Pulando StatTrak (Não permitido): {card_text.splitlines()[0]}...")
                        continue

                    # Localizando Link
                    link_el = card.locator("xpath=ancestor::a").first
                    if not link_el.count():
                        link_el = card.locator("a").first
                    
                    if link_el.count():
                        current_href = link_el.get_attribute("href")
                        if current_href:
                            full_url = "https://white.market" + current_href if current_href.startswith("/") else current_href
                            
                            # --- EXTRAÇÃO DE DADOS ---
                            # Preço
                            price_val = 0.0
                            price_match = re.search(r"\$\s?(\d+[\.,]\d+)", card_text)
                            if price_match:
                                price_val = float(price_match.group(1).replace(",", ""))
                            
                            # Float
                            float_val = 0.0
                            float_match = re.search(r"(0\.\d+)", card_text)
                            if float_match:
                                float_val = float(float_match.group(1))
                            
                            # Imagem
                            img_el = card.locator("img").first
                            img_url = img_el.get_attribute("src") if img_el.count() else "https://via.placeholder.com/150"
                            if img_url and img_url.startswith("/"):
                                img_url = "https://white.market" + img_url
                            
                            # --- FORMATAÇÃO DO NOME COMPLETO (RECONSTRUÇÃO) ---
                            name_final = f"★ {search_item} | {search_skin}"
                            if is_st:
                                name_final = name_final.replace("★ ", "★ StatTrak™ ")
                            
                            # Adicionar Estilo se não estiver no nome (ex: Phase 1)
                            # Se o card já tiver Phase no texto, tentamos capturar a Phase real para o nome
                            actual_style = search_style
                            if not actual_style:
                                # Tenta extrair Phase do texto se houver
                                phase_match = re.search(r"(Phase \d+)", card_text, re.I)
                                if phase_match:
                                    actual_style = phase_match.group(1)

                            if actual_style and actual_style.lower() not in name_final.lower():
                                if " | " in name_final:
                                    name_final = name_final.replace(" | ", f" | {actual_style} ")
                                else:
                                    name_final += f" ({actual_style})"
                            
                            # 5. Filtro de Float (Final)
                            if float_val > 0 and (float_min <= float_val <= float_max):
                                item = SkinItem(
                                    site="WhiteMarket",
                                    name=name_final,
                                    price=price_val,
                                    float_value=float_val,
                                    image_url=img_url,
                                    url=full_url
                                )
                                if not any(it.price == item.price and it.float_value == item.float_value for it in items):
                                    items.append(item)
                                    print(f"✅ [White Market] Item aceito: {name_final} ({float_val}) - ${price_val}")
                                    if on_item_found:
                                        on_item_found(item)
                            else:
                                if float_val > 0:
                                    print(f"⏭️ [White Market] Pulando (Float fora da faixa: {float_val})")
                            
                            variant_cards.append({
                                "title": name_final, 
                                "url": full_url,
                                "is_st": is_st
                            })
                except Exception:
                    continue

            # 3. Processar Variantes (Deep Scraping)
            # Ordenação: Non-ST antes de ST
            variant_cards.sort(key=lambda x: (x["is_st"]))
            
            processed_urls = set()
            for variant in variant_cards:
                url = variant["url"]
                if url in processed_urls: continue
                
                print(f"🚀 [White Market] Explorando ofertas similares: {variant['title']}")
                new_tab = context.new_page()
                try:
                    self.deep_scrape_page(new_tab, url, items, search_item, search_skin, search_style, float_min, float_max, stattrak_allowed, on_item_found)
                except Exception as ex:
                    print(f"⚠️ Erro ao processar variante {variant['title']} no White Market: {ex}")
                finally:
                    new_tab.close()
                
                processed_urls.add(url)
                time.sleep(2)

            if not variant_cards:
                print("⚠️ White Market: Nenhum item compatível encontrado na busca inicial.")
                # Fallback genérico se nada foi encontrado: tentar abrir o primeiro card qualquer
                first_card = page.locator("div[class*='item-card']").first
                if first_card.count():
                    print("Tentando fallback via deep scrape no primeiro item...")
                    card_link = first_card.locator("xpath=ancestor::a").first
                    if card_link.count():
                        fallback_url = card_link.get_attribute("href")
                        if fallback_url:
                            if fallback_url.startswith("/"): fallback_url = "https://white.market" + fallback_url
                            self.deep_scrape_page(page, fallback_url, items, search_item, search_skin, search_style, float_min, float_max, stattrak_allowed, on_item_found)
                
        except Exception as ex:
            print(f"❌ Erro no scraper White Market: {ex}")
        
        return items

    def deep_scrape_page(self, page, target_url, items, search_item, search_skin, search_style, float_min, float_max, stattrak_allowed, on_item_found):
        print(f"🚀 White Market: Entrando na página do produto: {target_url}")
        try:
            page.goto(target_url, wait_until="domcontentloaded")
            time.sleep(5)

            # Localizar Seção "Similar Offers" (Resiliente)
            header = page.get_by_text("Similar Offers", exact=True).first
            if not header.count():
                header = page.locator("h4:has-text('Similar Offers')").first

            rows = []
            if header.count():
                container = header.locator("xpath=ancestor::div[contains(@class, 'block') or contains(@class, 'similar')]").first
                if container.count():
                    rows = container.locator("tbody tr").all()
                    if not rows:
                        rows = container.locator("tr").all()
            
            if not rows:
                rows = page.locator("tr:has(a[href*='/item/'])").all()
            
            if not rows:
                rows = page.locator("div[class*='item-card'], a[href*='/item/']").all()

            print(f"👀 White Market: Analisando {len(rows)} ofertas similares.")
            
            count = 0
            for row in rows:
                try:
                    row_text = row.inner_text().strip()
                    if not row_text or "$" not in row_text:
                        continue
                    
                    # --- FILTRAGEM ---
                    # 1. StatTrak
                    is_st = any(x in row_text for x in ["StatTrak", "ST™", "ST "])
                    if is_st and not stattrak_allowed:
                        continue
                    
                    # 2. Style (Phase)
                    item_style = search_style
                    if not item_style:
                        phase_match = re.search(r"(Phase \d+)", row_text, re.I)
                        if phase_match:
                            item_style = phase_match.group(1)

                    if search_style:
                        style_clean = search_style.lower().replace(" ", "")
                        if style_clean not in row_text.lower().replace(" ", ""):
                            continue

                    # 3. Float
                    float_match = re.search(r"(0\.\d+)", row_text)
                    if not float_match:
                        continue
                    item_float = float(float_match.group(1))
                    
                    if not (float_min <= item_float <= float_max):
                        continue

                    # 4. Preço
                    price_match = re.search(r"\$\s?(\d+[\.,]\d+)", row_text)
                    item_price = 0.0
                    if price_match:
                        price_str = price_match.group(1).replace(",", "")
                        item_price = float(price_str)
                    else:
                        continue

                    # --- FORMATAÇÃO DO NOME COMPLETO (RECONSTRUÇÃO) ---
                    item_name = f"★ {search_item} | {search_skin}"
                    if is_st:
                        item_name = item_name.replace("★ ", "★ StatTrak™ ")
                    
                    if item_style and item_style.lower() not in item_name.lower():
                        if " | " in item_name:
                            item_name = item_name.replace(" | ", f" | {item_style} ")
                        else:
                            item_name += f" ({item_style})"

                    # 6. Imagem
                    img_el = row.locator("img").first
                    item_img = img_el.get_attribute("src") if img_el.count() else "https://via.placeholder.com/150"
                    if item_img and item_img.startswith("/"):
                        item_img = "https://white.market" + item_img

                    # 7. URL
                    link_el = row.locator("a[href*='/item/']").first
                    item_url = ""
                    if link_el.count():
                        item_url = link_el.get_attribute("href")
                    
                    if item_url and item_url.startswith("/"):
                        item_url = "https://white.market" + item_url
                    elif not item_url:
                        item_url = page.url

                    from src.item import SkinItem
                    item = SkinItem(
                        site="WhiteMarket",
                        name=item_name,
                        price=item_price,
                        float_value=item_float,
                        image_url=item_img,
                        url=item_url
                    )

                    if not any(it.price == item.price and it.float_value == item.float_value for it in items):
                        items.append(item)
                        count += 1
                        print(f"✅ [White Market] Oferta similar aceita: {item_name} ({item_float}) - ${item_price}")
                        if on_item_found:
                            on_item_found(item)

                except Exception:
                    continue
            
            print(f"✨ Deep Scraping finalizado: {count} itens adicionados.")
        except Exception as e:
            print(f"⚠️ Erro ao processar página {target_url}: {e}")

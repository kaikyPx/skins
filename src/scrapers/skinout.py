import re
import time
from playwright.sync_api import sync_playwright, Playwright
from src.item import SkinItem


class SkinoutScraper:
    def __init__(self):
        self.base_url = "https://skinout.gg/en/market"
    
    def scrape(
        self,
        playwright: Playwright,
        search_item: str,
        search_skin: str,
        search_style: str = "",
        float_min: float = 0.0,
        float_max: float = 1.0,
        stattrak_allowed: bool = False,
        on_item_found: callable = None,
        user_data_dir="chrome_bot_profile",
        executable_path=None,
        cdp_url=None,
    ):
        """
        Scrape items from Skinout.gg
        
        Args:
            playwright: Playwright instance
            search_item: Item type (e.g., "Karambit", "AK-47")
            search_skin: Skin name (e.g., "Doppler", "Asiimov")
            search_style: Style/Phase (e.g., "Ruby", "Phase 4", "Emerald")
            float_min: Minimum float value
            float_max: Maximum float value
            stattrak_allowed: Whether to include StatTrak items
            on_item_found: Callback function when item is found
            user_data_dir: Chrome user data directory
            executable_path: Path to Chrome executable
            cdp_url: Chrome DevTools Protocol URL
        """
        items = []
        
        # Construct search URL with search parameter
        # Example: https://skinout.gg/en/market?search=karambit+doppler
        search_query = f"{search_item} {search_skin}".strip().replace(" ", "+")
        if search_query:
            search_url = f"{self.base_url}?search={search_query}"
        else:
            search_url = self.base_url
        
        # Connect to browser
        context = None
        if cdp_url:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                executable_path=executable_path,
                headless=False,
                viewport=None,
                args=["--start-maximized"]
            )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        try:
            print(f"[Skinout] Navegando para: {search_url}")
            page.goto(search_url, wait_until="networkidle")
            
            # Wait for items to load - 7 seconds as requested
            print("[Skinout] Aguardando 7 segundos para carregar...")
            time.sleep(7)
            
            print("[Skinout] Aguardando seletor de itens...")
            page.wait_for_selector("ul.market__list.market_container", timeout=10000)
            
            # Check if pagination exists (for future infinite scroll implementation)
            has_pagination = page.query_selector("div.pagination.pagination--market") is not None
            print(f"[Skinout] Paginação detectada: {has_pagination}")
            
            # Extract all items from current page
            print("[Skinout] Extraindo itens...")
            card_elements = page.query_selector_all("li.market__list-item")
            print(f"[Skinout] Encontrados {len(card_elements)} cards")
            
            for idx, card in enumerate(card_elements):
                try:
                    print(f"\n[Skinout] ========== CARD {idx + 1}/{len(card_elements)} ==========")
                    
                    # Extract float value
                    float_elem = card.query_selector("span.item__top-float")
                    float_value = None
                    
                    if float_elem:
                        float_text = float_elem.inner_text().strip()
                        print(f"[Skinout] Float text: '{float_text}'")
                        # Format: "FN / 0.02256"
                        if " / " in float_text:
                            try:
                                float_value = float(float_text.split(" / ")[1])
                                print(f"[Skinout] Float value: {float_value}")
                            except Exception as e:
                                print(f"[Skinout] ❌ Erro ao converter float: {e}")
                    else:
                        print(f"[Skinout] ⚠️ Float element não encontrado")
                    
                    # Extract item name and skin name
                    item_name_elem = card.query_selector("span.item__item-name")
                    skin_name_elem = card.query_selector("span.item__skin-name")
                    
                    if not item_name_elem or not skin_name_elem:
                        print(f"[Skinout] ❌ Nome do item ou skin não encontrado, pulando")
                        continue
                    
                    item_name = item_name_elem.inner_text().strip()
                    skin_name = skin_name_elem.inner_text().strip()
                    print(f"[Skinout] Item: '{item_name}'")
                    print(f"[Skinout] Skin: '{skin_name}'")
                    
                    # Construct full name: "★ Karambit | Doppler Ruby"
                    full_name = f"{item_name} | {skin_name}"
                    print(f"[Skinout] Nome completo: '{full_name}'")
                    
                    # Filter by search criteria
                    # Check if item matches search_item
                    if search_item:
                        item_norm = search_item.lower().replace(" ", "")
                        name_norm = item_name.lower().replace(" ", "").replace("★", "").replace("™", "")
                        if item_norm not in name_norm:
                            print(f"[Skinout] ❌ Item '{search_item}' não encontrado em '{item_name}', pulando")
                            continue
                    
                    # Check if skin matches search_skin
                    if search_skin:
                        skin_norm = search_skin.lower().replace(" ", "")
                        skin_name_norm = skin_name.lower().replace(" ", "")
                        if skin_norm not in skin_name_norm:
                            print(f"[Skinout] ❌ Skin '{search_skin}' não encontrada em '{skin_name}', pulando")
                            continue
                    
                    # Check if style matches search_style
                    if search_style:
                        style_norm = search_style.lower().replace(" ", "")
                        combined_text = f"{skin_name} {full_name}".lower().replace(" ", "")
                        if style_norm not in combined_text:
                            print(f"[Skinout] ❌ Estilo '{search_style}' não encontrado em '{combined_text}', pulando")
                            continue
                        print(f"[Skinout] ✅ Estilo '{search_style}' encontrado")
                    
                    # Extract price
                    price_elem = card.query_selector("span.item__price")
                    if not price_elem:
                        print(f"[Skinout] ❌ Preço não encontrado, pulando")
                        continue
                    
                    price_text = price_elem.inner_text().strip()
                    print(f"[Skinout] Preço text: '{price_text}'")
                    # Clean price: "8&nbsp;628.605 $" -> "8628.605"
                    price_clean = price_text.replace("&nbsp;", "").replace(" ", "").replace("$", "").strip()
                    try:
                        price = float(price_clean)
                        print(f"[Skinout] Preço: ${price}")
                    except Exception as e:
                        print(f"[Skinout] ❌ Erro ao converter preço: {e}")
                        continue
                    
                    # Check for StatTrak
                    is_stattrak = "StatTrak™" in full_name or "StatTrak" in full_name
                    print(f"[Skinout] StatTrak: {is_stattrak}")
                    if not stattrak_allowed and is_stattrak:
                        print(f"[Skinout] ❌ StatTrak não permitido, pulando")
                        continue
                    
                    # Filter by float
                    if float_value is not None:
                        if not (float_min <= float_value <= float_max):
                            print(f"[Skinout] ❌ Float {float_value} fora do range {float_min}-{float_max}, pulando")
                            continue
                        print(f"[Skinout] ✅ Float {float_value} dentro do range")
                    
                    # Extract image URL
                    img_elem = card.query_selector("img.item__gun-pic")
                    image_url = img_elem.get_attribute("src") if img_elem else ""
                    print(f"[Skinout] Image URL: {image_url[:80]}..." if image_url else "[Skinout] ⚠️ Imagem não encontrada")
                    
                    # Extract item URL
                    link_elem = card.query_selector("a.item.item--market")
                    item_url = ""
                    if link_elem:
                        href = link_elem.get_attribute("href")
                        if href:
                            item_url = f"https://skinout.gg{href}" if href.startswith("/") else href
                    print(f"[Skinout] Item URL: {item_url}")
                    
                    # Create SkinItem
                    skin_item = SkinItem(
                        site="Skinout",  # FIXED: Changed from 'source' to 'site'
                        name=full_name,
                        price=price,
                        float_value=float_value if float_value else 0.0,
                        image_url=image_url,
                        url=item_url
                    )
                    
                    print(f"[Skinout] ✅ ITEM CRIADO COM SUCESSO!")
                    print(f"[Skinout]    Nome: {full_name}")
                    print(f"[Skinout]    Preço: ${price}")
                    print(f"[Skinout]    Float: {float_value}")
                    
                    items.append(skin_item)
                    
                    # Callback
                    if on_item_found:
                        on_item_found(skin_item)
                    
                    if (idx + 1) % 10 == 0:
                        print(f"[Skinout] Processados {idx + 1}/{len(card_elements)} cards...")
                
                except Exception as e:
                    print(f"[Skinout] ❌ Erro ao processar card {idx + 1}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"[Skinout] Scraping finalizado. Encontrados {len(items)} itens.")
            return items
        
        except Exception as e:
            print(f"[Skinout] Erro durante scraping: {e}")
            return items
        finally:
            page.close()
            print("[Skinout] Página fechada.")

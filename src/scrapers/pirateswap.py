
import time
import re
from ..item import SkinItem

class PirateSwapScraper:
    def __init__(self, page):
        self.page = page
        self.base_url = "https://pirateswap.com/pt/exchanger"

    def scrape(self, item_name, search_skin=None, search_style=None, min_float=0.0, max_float=1.0, stattrak=False):
        print(f"Iniciando scrape no PirateSwap para: {item_name}, Skin: {search_skin}, Estilo: {search_style}")
        self.page.goto(self.base_url)
        print("Página carregada. Aguardando 5 segundos...")
        time.sleep(5)
        
        # Search
        try:
            print("Procurando campo de busca...")
            search_input = self.page.wait_for_selector('input[data-testid="search-autocomplete-input"]', timeout=10000)
            if search_input:
                print("Campo de busca encontrado. Clicando e digitando...")
                search_input.click()
                time.sleep(0.5)
                
                # Combine item_name with style if provided
                search_query = item_name
                if search_style:
                    search_query += f" {search_style}"
                
                search_input.type(search_query, delay=100) # Human-like typing
                print(f"Texto digitado: '{search_query}'. Aguardando resultados dinâmicos (5s)...")
                time.sleep(5) # Wait for dynamic results without pressing Enter
            else:
                print("Campo de busca não encontrado.")
                return []
        except Exception as e:
            print(f"Erro na busca: {e}")
            return []

        items = []
        try:
            print("Procurando cards de itens...")
            # Wait for at least one card or timeout
            self.page.wait_for_selector('div[data-testid="exchanger-card"]', timeout=5000)
            cards = self.page.query_selector_all('div[data-testid="exchanger-card"]')
            print(f"Encontrados {len(cards)} cards.")

            for idx, card in enumerate(cards):
                # Debug: Print HTML of the first card
                if idx == 0:
                    print(f"DEBUG PIRATESWAP - CARD 0 HTML:\n{card.inner_html()[:2000]}")
                
                try:
                    # Name & Image
                    # Name & Image
                    # Try specific class first, then generic img
                    img_elem = card.query_selector('img[class*="SkinCardImage"]')
                    if not img_elem:
                        img_elem = card.query_selector('img')
                    
                    if not img_elem:
                         print("Imagem não encontrada no card.")
                         continue
                    
                    name_part = img_elem.get_attribute("alt")
                    image = img_elem.get_attribute("src")
                    
                    if not image:
                        # Try data-src or srcset if src is missing (lazy load)
                        image = img_elem.get_attribute("data-src") or img_elem.get_attribute("srcset")
                    
                    if not image:
                        print(f"URL da imagem não encontrada para: {name_part}")
                        image = "https://via.placeholder.com/150" # Fallback placeholder

                        # STRICT FILTERING: Check if name_part matches search_skin
                    if search_skin:
                        # Ex: search_skin="Doppler", name_part="Gamma Doppler" -> NO MATCH (startswith check handles this)
                        # Ex: search_skin="Doppler", name_part="Doppler Phase 1" -> MATCH (startswith allows suffixes)
                        # Use strip() to handle whitespace
                        if not name_part.strip().lower().startswith(search_skin.strip().lower()):
                             print(f"Skipping item: '{name_part}' (Does not match requested skin: '{search_skin}')")
                             continue
                    
                    # Construct full name: Query + Name Part if generic?
                    # The alt seems to be just the skin name e.g. "Doppler" or "Gamma Doppler"
                    # We might want to prepend the weapon name if it is not in the alt using the search query
                    # For now, let's use the alt text. If it is too short, we might prepend the search query words that are not in it.
                    # But the plan said "Combine Search Query + Image Alt". 
                    # Let's try to be smart: if item_name words are not in name_part, prepend them? 
                    # e.g. query="Karambit", alt="Doppler" -> "Karambit Doppler"
                    
                    full_name = name_part
                    if item_name.lower() not in name_part.lower(): 
                         # Simple logic: if the search query is mostly missing, prepend it. 
                         # Actually, let's just use the alt for now as per simple plan, but the user note said "inferred".
                         # Let's check if the generic weapon name is missing.
                         # A safe bet is: if the alt is just "Doppler", and we searched "Karambit Doppler", we want "Karambit Doppler".
                         full_name = f"{item_name} {name_part}" 
                         # Wait, if I search "Karambit Doppler", and alt is "Doppler", result is "Karambit Doppler Doppler" with simple concat?
                         # Let's try checks.
                         if name_part.lower() in item_name.lower():
                             full_name = item_name # Use the query as it likely has the weapon name
                         else:
                             # If they are different, maybe just concat?
                             # Let's just use the alt as the skin name and assume the user knows what they searched. 
                             # Or better: check existing code pattern.
                             pass
                    
                    # Actually, looking at the HTML "alt='Gamma Doppler'". If I search "Karambit", I likely want "Karambit Gamma Doppler".
                    # Let's stick to the plan: "append the search query... to the skin name" -> Actually plan said "append". 
                    # But usually it's "Weapon | Skin". 
                    # Let's try: Weapon (from query) + Skin (from alt). 
                    # Simple heuristic: Just use the query + " | " + alt if it looks like a skin name?
                    # Let's just use: f"{item_name} ({name_part})" or similar?
                    # Re-reading plan: "reconstruct it using the search query + skin name".
                    # Let's do: f"{item_name} NOT IN ALT -> Prepend". 
                    # Actually, usually Scrapers return what they see. 
                    # But here the item card misses the weapon class.
                    # Let's use the logic:
                    
                    item_words = item_name.split()
                    prefix = []
                    for word in item_words:
                         if word.lower() not in name_part.lower():
                             prefix.append(word)
                    
                    if prefix:
                        full_name = " ".join(prefix) + " " + name_part
                    else:
                        full_name = name_part

                    # Pegar todo o texto do card para extração via Regex
                    card_text = card.inner_text()
                    
                    # 1. Extrair Preço ($1,234.56)
                    price = 0.0
                    price_match = re.search(r'\$([0-9,.]+)', card_text)
                    if price_match:
                        try:
                            # Remove vírgulas de milhar
                            price = float(price_match.group(1).replace(",", ""))
                        except:
                            price = 0.0
                    
                    # 2. Extrair Float (0.0123...)
                    float_value = 0.0
                    float_match = re.search(r'0\.\d+', card_text)
                    if float_match:
                        try:
                            float_value = float(float_match.group(0))
                        except:
                            float_value = 0.0

                    # 3. Nome & Imagem (Mais estáveis que o texto)
                    img_elem = card.query_selector('img')
                    if not img_elem:
                         continue
                    
                    name_part = img_elem.get_attribute("alt") or "Skin"
                    image = img_elem.get_attribute("src") or img_elem.get_attribute("data-src") or ""
                    
                    # Filtro de Skin
                    if search_skin and not name_part.strip().lower().startswith(search_skin.strip().lower()):
                         print(f"Skipping item: '{name_part}' (Does not match requested skin: '{search_skin}')")
                         continue
                         
                    # Reconstruir Nome Completo
                    item_words = item_name.split()
                    prefix = [w for w in item_words if w.lower() not in name_part.lower()]
                    full_name = (" ".join(prefix) + " " + name_part).strip()

                    # FILTRO STATTRAK
                    is_stattrak = "StatTrak" in full_name or "StatTrak" in card_text
                    if not stattrak and is_stattrak:
                        continue

                    # Float Filtering
                    if float_value < min_float or float_value > max_float:
                        continue

                    new_item = SkinItem(
                        site="PirateSwap",
                        name=full_name,
                        float_value=float_value,
                        price=price,
                        url=self.base_url, 
                        image_url=image
                    )
                    
                    items.append(new_item)
                    print(f"✅ [PirateSwap] Encontrado: {full_name} | Preço: ${price} | Float: {float_value}")

                except Exception as e:
                    print(f"Erro ao processar card PirateSwap: {e}")
                    continue

        except Exception as e:
            print(f"Erro geral no scraper PirateSwap: {e}")

        return items

import re
import time
from typing import List, Callable
from playwright.sync_api import Page
from src.item import SkinItem

class TradeItScraper:
    def __init__(self, page: Page):
        self.page = page
        self.site_name = "TradeIt.gg"
        self.base_url = "https://tradeit.gg/csgo/store"

    def scrape(self, item_name: str, search_skin: str = "", search_style: str = "", 
               min_float: float = 0.0, max_float: float = 1.0, stattrak: bool = False) -> List[SkinItem]:
        print(f"DEBUG [{self.site_name}]: Iniciando busca robusta por '{item_name} {search_skin} {search_style}'")
        
        if self.page.url != self.base_url:
            self.page.goto(self.base_url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)

        # Localiza o input de busca pelo placeholder. 
        # Geralmente existem dois "Search inventory" (User e Site). 
        # O da loja (Site) costuma ser o segundo no DOM.
        search_input_selector = "input[placeholder*='Search inventory']"
        try:
            # Tenta pegar o segundo input de busca (o da loja)
            inputs = self.page.locator(search_input_selector)
            count = inputs.count()
            if count >= 2:
                search_input = inputs.nth(1)
            else:
                search_input = inputs.first
            
            search_input.wait_for(timeout=10000)
        except:
            print(f"DEBUG [{self.site_name}]: Input de busca (placeholder) não encontrado. Recarregando...")
            self.page.reload()
            self.page.wait_for_load_state("networkidle")
            search_input = self.page.locator(search_input_selector).last

        # Monta a query de busca
        query = f"{item_name} {search_skin}".strip()
        
        search_input.fill("")
        search_input.fill(query)
        search_input.press("Enter")
        
        time.sleep(4)
        
        self.page.evaluate("window.scrollBy(0, 800)")
        time.sleep(2)

        found_items = []
        
        # Identifica os cards via estrutura: um div que contém uma imagem com alt específico
        # XPath: //div[.//img[@alt='item image']]
        # Vamos usar um seletor que pegue o container mais próximo do item
        card_locators = self.page.locator("//div[img[@alt='item image' or @alt='item-image']]")
        cards_count = card_locators.count()
        print(f"DEBUG [{self.site_name}]: Encontrados {cards_count} cards (via alt='item image').")

        for i in range(cards_count):
            try:
                print(f"DEBUG [{self.site_name}]: Processando Card {i} de {cards_count}...")
                card = card_locators.nth(i)
                
                # Extrai texto primeiro
                all_text = card.inner_text()
                print(f"DEBUG [{self.site_name}]: Card {i} - Texto bruto recuperado ({len(all_text)} chars).")
                lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                
                # ... lógica original ...
                
                # Pega a imagem para referência
                img_elem = card.locator("img").first
                image_url = ""
                try:
                    image_url = img_elem.get_attribute("src") or ""
                    if not image_url:
                        srcset = img_elem.get_attribute("srcset")
                        if srcset:
                            image_url = srcset.split(",")[0].split(" ")[0]
                except:
                    pass

                # Preço: Texto que contém $
                price_match = re.search(r'\$(\d+[,.]\d*)', all_text)
                if not price_match:
                    print(f"DEBUG [{self.site_name}]: Card {i} ignorado - Preço não encontrado.")
                    continue
                price = float(price_match.group(1).replace(",", ""))

                # Float/Condição: Texto que contém o ponto médio '·'
                float_val = 0.0
                condition_text = ""
                if "·" in all_text:
                    float_match = re.search(r'([A-Z]+)\s*·\s*([\d.]+)', all_text)
                    if float_match:
                        condition_text = float_match.group(1)
                        try:
                            float_val = float(float_match.group(2))
                        except:
                            pass
                    else:
                        # Tenta só a condição
                        cond_match = re.search(r'([FMWBS][TNW])\s*·', all_text)
                        if cond_match:
                            condition_text = cond_match.group(1)
                
                print(f"DEBUG [{self.site_name}]: Card {i} - Preço: ${price}, Float: {float_val}, Cond: {condition_text}")

                # ... lógica de nome ...
                base_name = ""
                for line in lines:
                    if "$" in line or "·" in line or "x" in line[:2] or "stack" in line.lower():
                        continue
                    if len(line) > 3:
                        base_name = line
                        break
                
                if not base_name:
                    base_name = "Item Desconhecido"

                full_name = f"{base_name} ({condition_text})" if condition_text else base_name
                print(f"DEBUG [{self.site_name}]: Card {i} - Nome identificado: '{full_name}'")
                
                # FILTROS
                is_stattrak = "StatTrak" in full_name or "StatTrak" in all_text
                
                # NOVA REGRA STATTRAK:
                # Se stattrak (checkbox) for OFF, ignoramos itens StatTrak.
                # Se stattrak (checkbox) for ON, aceitamos AMBOS.
                if not stattrak and is_stattrak:
                    print(f"DEBUG [{self.site_name}]: Card {i} ignorado - Item é StatTrak e filtro está OFF.")
                    continue

                if search_style and search_style.lower() not in full_name.lower():
                    print(f"DEBUG [{self.site_name}]: Card {i} ignorado - Estilo '{search_style}' não encontrado no nome.")
                    continue

                if float_val > 0:
                    if float_val < min_float or float_val > max_float:
                        print(f"DEBUG [{self.site_name}]: Card {i} ignorado - Float {float_val} fora do range.")
                        continue
                elif min_float > 0 and "·" in all_text:
                    print(f"DEBUG [{self.site_name}]: Card {i} ignorado - Float não extraído mas range definido.")
                    continue

                item_url = self.base_url + f"?search={query.replace(' ', '+')}"

                item = SkinItem(
                    site=self.site_name,
                    name=full_name,
                    float_value=float_val,
                    price=price,
                    url=item_url,
                    image_url=image_url,
                    percentage=0
                )
                found_items.append(item)
                
            except Exception as e:
                print(f"DEBUG [{self.site_name}]: Erro ao processar card {i}: {e}")
                continue

        return found_items

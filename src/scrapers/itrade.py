
import time
import re
from ..item import SkinItem

class ITradeScraper:
    def __init__(self, page):
        self.page = page
        self.base_url = "https://itrade.gg/trade/csgo"

    def scrape(self, item_name, search_skin=None, search_style=None, min_float=0.0, max_float=1.0, stattrak=False):
        print(f"Iniciando scrape no iTrade para: {item_name}, Skin: {search_skin}, Estilo: {search_style}")
        self.page.goto(self.base_url)
        print("Página carregada. Aguardando 5 segundos...")
        time.sleep(5)
        
        # --- BUSCA ---
        try:
            print("Procurando campo de busca...")
            search_input = self.page.wait_for_selector('input[placeholder="Search by name"]', timeout=10000)
            if search_input:
                print(f"Campo de busca encontrado. Digitando: '{item_name}'")
                search_input.click()
                time.sleep(0.5)
                search_input.fill("") 
                search_input.fill(item_name)
                print("Aguardando resultados (5s)...")
                time.sleep(5)
            else:
                print("Campo de busca não encontrado.")
                return []
        except Exception as e:
            print(f"Erro na busca: {e}")
            return []

        items = []
        try:
            print("Procurando cards de itens...")
            # Pega botões que contém imagens. No iTrade os cards são <button>
            # Vamos esperar que pelo menos um item apareça
            try:
                self.page.wait_for_selector('button:has(img)', timeout=5000)
            except:
                print("DEBUG: Nenhum card 'button:has(img)' encontrado após timeout.")
            
            cards = self.page.query_selector_all('button:has(img)')
            print(f"Encontrados {len(cards)} cards em potencial.")

            for i, card in enumerate(cards):
                try:
                    # EXTRAÇÃO DE NOME
                    full_name = ""
                    img_elem = card.query_selector('img')
                    if img_elem:
                        full_name = img_elem.get_attribute("alt") or ""
                        image = img_elem.get_attribute("src") or img_elem.get_attribute("data-src") or ""
                    
                    if not full_name:
                        # Fallback se não tiver alt
                        name_elem = card.query_selector('*:has-text("|")')
                        if name_elem:
                            full_name = name_elem.inner_text()
                    
                    if not full_name or "|" not in full_name:
                        continue

                    # FILTRO DE SKIN
                    if search_skin:
                        if search_skin.lower() not in full_name.lower():
                            continue

                    print(f"DEBUG: Processando {full_name}")

                    # EXTRAÇÃO DE PREÇO ($)
                    price = 0.0
                    all_text_elems = card.query_selector_all('*:has-text("$")')
                    best_price = 0.0
                    
                    for elem in all_text_elems:
                        text = elem.inner_text().strip()
                        # Tenta extrair o valor. Ignora se terminar em %
                        if "%" in text:
                            continue
                            
                        price_match = re.search(r'\$\s?([\d,.]+)', text)
                        if price_match:
                            try:
                                val = float(price_match.group(1).replace(",", ""))
                                # Geralmente o preço real é o maior valor monetário no card ou o primeiro que não é porcentagem
                                if val > best_price:
                                    best_price = val
                            except:
                                continue
                    
                    price = best_price
                    if price == 0:
                        # Fallback se best_price ainda for 0
                        price_elem = card.query_selector('*:has-text("$")')
                        if price_elem:
                            print(f"DEBUG: Fallback price text: {price_elem.inner_text()}")

                    # EXTRAÇÃO DE FLOAT (style attribute)
                    float_value = 0.0
                    # iTrade usa um indicador visual (uma barrinha colorida). O float costuma estar em uma div 
                    # com 'left: X.XX%'.
                    # Vamos tentar vários seletores possíveis para o indicador de float
                    float_indicator = card.query_selector('div[style*="left"]')
                    if not float_indicator:
                        # Tenta encontrar qualquer elemento com style que tenha 'left'
                        float_indicator = card.query_selector('[style*="left"]')
                    
                    if float_indicator:
                        style_attr = float_indicator.get_attribute("style")
                        float_match = re.search(r'left:\s*([\d.]+)%', style_attr)
                        if float_match:
                            float_value = float(float_match.group(1)) / 100.0
                        else:
                            # Tenta pegar de outro atributo se existir
                            pass
                    else:
                        print(f"DEBUG: Float indicator não encontrado para {full_name}. Verificando estilo do card...")
                        # Se não encontrar a barrinha, o item pode ser vanilla ou ter outro formato
                        pass

                    print(f"DEBUG: Preço: ${price}, Float: {float_value:.5f}")

                    # --- INSPEÇÃO DE ESTILO (RIGHT CLICK) ---
                    if search_style:
                        print(f"Inspecionando estilo para {full_name}...")
                        card.click(button="right")
                        time.sleep(2)
                        
                        modal = self.page.query_selector('body > div:last-child')
                        popup_text = modal.inner_text() if modal else self.page.content()
                        
                        if search_style.lower() in popup_text.lower():
                            print(f"✅ Estilo '{search_style}' confirmado!")
                        else:
                            print(f"❌ Estilo '{search_style}' não encontrado. Ignorando.")
                            self.page.keyboard.press("Escape")
                            time.sleep(0.5)
                            continue
                        
                        self.page.keyboard.press("Escape")
                        time.sleep(0.5)

                    # FILTRO STATTRAK
                    is_stattrak = "StatTrak" in full_name
                    if not stattrak and is_stattrak:
                        print(f"DEBUG: Item {full_name} ignorado - StatTrak e filtro OFF")
                        continue

                    # FILTRO DE FLOAT
                    if float_value < min_float or float_value > max_float:
                        if float_value == 0 and min_float > 0:
                            print(f"DEBUG: Item {full_name} ignorado pq float=0 e min={min_float}")
                        continue

                    items.append(SkinItem(
                        site="itrade",
                        name=full_name,
                        float_value=float_value,
                        price=price,
                        url=self.base_url, 
                        image_url=image if "http" in image else "https://via.placeholder.com/150"
                    ))

                except Exception as e:
                    print(f"DEBUG: Erro no card {i}: {e}")
                    continue

        except Exception as e:
            print(f"Erro geral no scraper iTrade: {e}")

        return items

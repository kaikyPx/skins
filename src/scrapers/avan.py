import time
import urllib.parse
import re
from playwright.sync_api import Page
from src.item import SkinItem

class AvanScraper:
    def __init__(self, base_url="https://avan.market"):
        self.base_url = base_url

    def scrape(self, page: Page, on_item_found, search_item=None, search_skin=None, search_style=None, float_min=0.0, float_max=1.0, stattrak_allowed=True):
        print(f"[{self.__class__.__name__}] Iniciando scraping via API...")

        # 1. Preparar query
        query_parts = []
        if search_item: query_parts.append(search_item)
        if search_skin: query_parts.append(search_skin)
        # Não incluímos o style na query da API para garantir que pegamos tudo e filtramos localmente
        combined_query = " ".join(query_parts).strip()

        # Garante que estamos no domínio certo para o fetch não ser bloqueado por CORS
        if "avan.market" not in page.url:
            page.goto("https://avan.market/en/market/cs", wait_until="domcontentloaded")

        current_page = 1
        total_captured = 0

        while True:
            # Construir URL da API
            # app_id=730 (CS2), currency=1 (USD)
            api_url = f"https://avan.market/v1/api/users/catalog?app_id=730&currency=1&name={urllib.parse.quote(combined_query)}&page={current_page}"
            
            if float_min > 0: api_url += f"&float_min={float_min}"
            if float_max < 1: api_url += f"&float_max={float_max}"

            print(f"[{self.__class__.__name__}] Consultando API (Página {current_page})...")
            
            try:
                # Usa o navegador para fazer o fetch (contorna proteções e usa cookies da sessão)
                response_json = page.evaluate(f'''
                    async (url) => {{
                        const res = await fetch(url);
                        return res.json();
                    }}
                ''', api_url)

                data = response_json.get("data", [])
                if not data:
                    print(f"[{self.__class__.__name__}] Fim dos resultados da API.")
                    break

                for entry in data:
                    # Cada entry é um agrupamento de itens (ex: Karambit Doppler)
                    weapon_type = entry.get("weapon", "")
                    base_name = entry.get("name", "") # Geralmenter "★ Karambit | Doppler"
                    phase = entry.get("phase", "") # Ex: "Phase 1"
                    
                    # Sell items são as listagens individuais com float e preço únicos
                    sell_items = entry.get("sell_items", [])
                    for item in sell_items:
                        try:
                            price = float(item.get("sell_price", 0))
                            float_val = float(item.get("float", 0))
                            is_stattrak = "StatTrak" in base_name or item.get("is_stattrak", False)
                            
                            # Construção do nome completo
                            full_skin_name = base_name
                            if phase and phase.lower() not in full_skin_name.lower():
                                full_skin_name = f"{full_skin_name} {phase}"
                            
                            # --- FILTRAGEM ---
                            # 1. Weapon Type
                            if search_item and search_item.lower() not in full_skin_name.lower():
                                continue
                            
                            # 2. Skin Name
                            if search_skin and search_skin.lower() not in full_skin_name.lower():
                                continue
                                
                            # 3. Style / Phase
                            if search_style and search_style.lower() not in full_skin_name.lower():
                                continue
                                
                            # 4. StatTrak
                            if not stattrak_allowed and is_stattrak:
                                continue
                                
                            # 5. Float (A API já filtra no servidor, mas garantimos aqui)
                            if float_val < float_min or float_val > float_max:
                                continue

                            # Imagem e URL (Correção baseada na estrutura real do JSON)
                            icon_url = entry.get("icon_url", "")
                            image_url = f"https://community.cloudflare.steamstatic.com/economy/image/{icon_url}" if icon_url else ""
                            
                            # Link do item (apenas slugified_name, sem o ID da listagem, conforme pedido)
                            slug = entry.get("slugified_name", "")
                            if slug:
                                item_link = f"https://avan.market/en/market/cs/{slug}"
                            else:
                                item_link = "https://avan.market/en/market/cs"

                            print(f"   - Capturado: {full_skin_name} | ${price} | Float: {float_val}")
                            
                            new_item = SkinItem(
                                name=full_skin_name,
                                price=price,
                                float_value=float_val,
                                image_url=image_url,
                                url=item_link,
                                site="Avan.Market"
                            )
                            on_item_found(new_item)
                            total_captured += 1
                            
                        except Exception as inner_e:
                            continue

                # Se a página tiver menos de 100 itens (ou o limite deles), pode ser a última
                if len(data) < 20: # Ajuste o limite conforme o habitual da API
                    break
                    
                current_page += 1
                time.sleep(1) # Delay amigável

            except Exception as e:
                print(f"[{self.__class__.__name__}] Erro na chamada da API: {e}")
                break

        print(f"[{self.__class__.__name__}] Scraping finalizado. Total: {total_captured} itens.")


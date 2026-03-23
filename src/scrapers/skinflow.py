from playwright.sync_api import Playwright
from src.item import SkinItem
import urllib.parse
import time
import re


class SkinflowScraper:
    """
    Scraper para o site Skinflow (https://skinflow.gg)
    Site usa Nuxt.js com infinite scroll
    """
    
    def __init__(self):
        self.base_url = "https://skinflow.gg/buy"
        self.name = "Skinflow"
    
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
        """
        Realiza scraping no Skinflow
        
        Args:
            playwright: Instância do Playwright
            search_item: Nome do item (ex: "Karambit")
            search_skin: Nome da skin (ex: "Doppler")
            search_style: Estilo específico (ex: "Phase 1")
            float_min: Float mínimo
            float_max: Float máximo
            user_data_dir: Diretório de dados do usuário
            executable_path: Caminho do executável do Chrome
            on_item_found: Callback chamado quando um item é encontrado
            cdp_url: URL CDP para conectar ao navegador existente
            stattrak_allowed: Se permite itens StatTrak
        
        Returns:
            Lista de SkinItem encontrados
        """
        items = []
        
        # Construir query de busca
        full_query = f"{search_item} {search_skin}".strip()
        search_url = f"{self.base_url}?search={urllib.parse.quote(full_query)}"
        
        print(f"[Skinflow] Iniciando scraping: {search_url}")
        
        try:
            # Conectar ou criar contexto do navegador
            if cdp_url:
                try:
                    browser = playwright.chromium.connect_over_cdp(cdp_url)
                    context = browser.contexts[0] if browser.contexts else browser.new_context()
                    page = context.new_page()
                except Exception as e:
                    print(f"[Skinflow] Erro ao conectar via CDP: {e}")
                    print("[Skinflow] Criando novo contexto...")
                    context = playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=False,
                        executable_path=executable_path,
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                    page = context.new_page()
            else:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    executable_path=executable_path,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = context.new_page()
            
            # Navegar para a URL
            print(f"[Skinflow] Aguardando carregamento inicial...")
            page.goto(search_url, wait_until="networkidle")
            
            # Aguardar JavaScript carregar completamente
            print(f"[Skinflow] Aguardando 15 segundos para JavaScript carregar...")
            time.sleep(15)  # Aguardar 15 segundos conforme solicitado
            
            # Tentar diferentes seletores comuns para sites Nuxt.js
            # Baseado no HTML real: div com class "tradeItem" dentro de div#tradeItems
            possible_selectors = [
                "div.tradeItem",  # Seletor correto do Skinflow
                "div[class*='tradeItem']",
                "div[id^='730_']",  # IDs começam com 730_
            ]
            
            container_selector = None
            for selector in possible_selectors:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    container_selector = selector
                    print(f"[Skinflow] Encontrado seletor: {selector}")
                    break
                except:
                    continue
            
            if not container_selector:
                print("[Skinflow] Nenhum item encontrado. Verifique os seletores.")
                return items
            
            time.sleep(3)  # Aguardar estabilização
            
            # Infinite scroll: rolar até não carregar mais itens
            print("[Skinflow] Iniciando infinite scroll...")
            scroll_attempts = 0
            max_scrolls = 50  # Limite de segurança
            
            # Encontrar o container scrollável correto
            scroll_container = page.query_selector("div#tradeItems")
            
            while scroll_attempts < max_scrolls:
                # Pegar altura atual do container
                if scroll_container:
                    previous_height = scroll_container.evaluate("el => el.scrollHeight")
                    # Rolar o container específico
                    scroll_container.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                else:
                    # Fallback para scroll da página inteira
                    previous_height = page.evaluate("document.body.scrollHeight")
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # Aguardar 3 segundos para novos itens carregarem
                time.sleep(3)
                
                # Pegar nova altura
                if scroll_container:
                    new_height = scroll_container.evaluate("el => el.scrollHeight")
                else:
                    new_height = page.evaluate("document.body.scrollHeight")
                
                # Se não mudou, não há mais itens
                if new_height == previous_height:
                    print(f"[Skinflow] Scroll completo após {scroll_attempts} tentativas")
                    break
                
                scroll_attempts += 1
                if scroll_attempts % 5 == 0:
                    print(f"[Skinflow] Scroll {scroll_attempts}/{max_scrolls}...")
            
            # Aguardar um pouco mais para garantir
            time.sleep(2)
            
            # Extrair todos os itens
            print("[Skinflow] Extraindo itens...")
            card_elements = page.query_selector_all(container_selector)
            print(f"[Skinflow] Encontrados {len(card_elements)} cards")
            
            for idx, card in enumerate(card_elements):
                try:
                    print(f"\n[Skinflow] ========== CARD {idx + 1}/{len(card_elements)} ==========")
                    
                    # Mostrar todo o HTML do card para debug
                    card_html = card.inner_html()
                    print(f"[Skinflow] Card HTML (primeiros 500 chars):\n{card_html[:500]}...")
                    
                    # Estrutura do Skinflow:
                    # - Float: <span>0.031</span> / <span>FN</span>
                    # - Estilo: <p>Emerald</p> (ou Phase 1, Phase 2, etc.)
                    # - Nome: <p>GAMMA DOPPLER</p>
                    # - Preço: <p>$9,666.63</p>
                    
                    # Float (primeiro <span> dentro do <p> com float)
                    float_elem = card.query_selector("p.whitespace-pre span")
                    float_value = 0.0
                    
                    print(f"[Skinflow] Float element found: {float_elem is not None}")
                    if float_elem:
                        float_text = float_elem.inner_text().strip()
                        try:
                            float_value = float(float_text)
                        except:
                            float_value = 0.0
                    
                    # Estilo/Phase (div.absolute.mx-3.top-6 > p)
                    style_elem = card.query_selector("div.absolute.mx-3 p")
                    style_text = style_elem.inner_text().strip() if style_elem else ""
                    print(f"[Skinflow] Style element found: {style_elem is not None}")
                    print(f"[Skinflow] Style text: '{style_text}'")
                    
                    # Nome completo (p com color style dentro de div.px-3)
                    name_elem = card.query_selector("div.px-3 p[style*='color']")
                    print(f"[Skinflow] Name element (with color) found: {name_elem is not None}")
                    
                    if not name_elem:
                        # Fallback: tentar pegar qualquer p com texto
                        name_elem = card.query_selector("div.px-3 div.flex p")
                        print(f"[Skinflow] Name element (fallback) found: {name_elem is not None}")
                    
                    if not name_elem:
                        print(f"[Skinflow] ❌ Nenhum elemento de nome encontrado, pulando card")
                        continue
                    
                    skin_name = name_elem.inner_text().strip()
                    print(f"[Skinflow] Skin name: '{skin_name}'")
                    
                    # Construir nome completo: "Karambit | {skin_name} ({style})"
                    # O site mostra apenas o nome da skin, precisamos inferir o item
                    if style_text:
                        full_name = f"{search_item} | {skin_name} ({style_text})"
                    else:
                        full_name = f"{search_item} | {skin_name}"
                    
                    print(f"[Skinflow] Full name: '{full_name}'")
                    
                    # Preço (último <p> dentro de div.px-3)
                    price_elem = card.query_selector("div.px-3 p.font-normal")
                    print(f"[Skinflow] Price element found: {price_elem is not None}")
                    
                    if not price_elem:
                        print(f"[Skinflow] ❌ Nenhum elemento de preço encontrado, pulando card")
                        continue
                    
                    price_text = price_elem.inner_text().strip()
                    print(f"[Skinflow] Price text: '{price_text}'")
                    
                    # Limpar e converter preço ($9,666.63 -> 9666.63)
                    price_clean = re.sub(r'[^\d.]', '', price_text)
                    try:
                        price = float(price_clean)
                        print(f"[Skinflow] Price value: ${price}")
                    except Exception as e:
                        print(f"[Skinflow] ❌ Erro ao converter preço: {e}")
                        continue
                    
                    # Verificar StatTrak (geralmente no nome ou em badge)
                    card_text = card.inner_text()
                    is_stattrak = "StatTrak" in card_text or "ST" in card_text or "stattrak" in card_text.lower()
                    print(f"[Skinflow] StatTrak: {is_stattrak}")
                    
                    if not stattrak_allowed and is_stattrak:
                        print(f"[Skinflow] ❌ StatTrak não permitido, pulando")
                        continue
                    
                    # Filtrar por float
                    if float_value is not None:
                        if not (float_min <= float_value <= float_max):
                            print(f"[Skinflow] ❌ Float {float_value} fora do range {float_min}-{float_max}, pulando")
                            continue
                        print(f"[Skinflow] ✅ Float {float_value} dentro do range")
                    
                    # Filtrar por estilo
                    if search_style:
                        style_norm = search_style.lower().replace(" ", "")
                        # Verificar no style_text e no full_name
                        combined_text = f"{style_text} {full_name}".lower().replace(" ", "")
                        
                        if style_norm not in combined_text:
                            print(f"[Skinflow] ❌ Estilo '{search_style}' não encontrado em '{combined_text}', pulando")
                            continue
                        print(f"[Skinflow] ✅ Estilo '{search_style}' encontrado")
                    
                    # Imagem (div com background-image)
                    img_div = card.query_selector("div[style*='background: url']")
                    image_url = ""
                    if img_div:
                        style_attr = img_div.get_attribute("style")
                        # Extrair URL do background
                        url_match = re.search(r'url\(&quot;([^&]+)&quot;\)', style_attr)
                        if url_match:
                            image_url = url_match.group(1)
                            print(f"[Skinflow] Image URL: {image_url[:80]}...")
                    
                    # URL do item (usar o ID do card)
                    item_id = card.get_attribute("id")
                    item_url = f"https://skinflow.gg/item/{item_id}" if item_id else ""
                    print(f"[Skinflow] Item URL: {item_url}")
                    
                    # Criar SkinItem
                    skin_item = SkinItem(
                        site="Skinflow",
                        name=full_name,
                        float_value=float_value,
                        price=price,
                        url=search_url,
                        image_url=image_url
                    )
                    
                    print(f"[Skinflow] ✅ ITEM CRIADO COM SUCESSO!")
                    print(f"[Skinflow]    Nome: {full_name}")
                    print(f"[Skinflow]    Preço: ${price}")
                    print(f"[Skinflow]    Float: {float_value}")
                    print(f"[Skinflow]    Estilo: {style_text}")
                    
                    items.append(skin_item)
                    
                    # Callback
                    if on_item_found:
                        on_item_found(skin_item)
                    
                    if (idx + 1) % 10 == 0:
                        print(f"[Skinflow] Processados {idx + 1}/{len(card_elements)} itens")
                
                except Exception as e:
                    print(f"[Skinflow] Erro ao processar card {idx}: {e}")
                    continue
            
            print(f"[Skinflow] Scraping concluído: {len(items)} itens encontrados")
            
            # Fechar página
            page.close()
            
        except Exception as e:
            print(f"[Skinflow] Erro no scraping: {e}")
        
        return items

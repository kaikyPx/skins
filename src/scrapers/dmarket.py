from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import urllib.parse
import re

class DMarketScraper:
    def __init__(self):
        self.base_url = "https://dmarket.com"

    def _scroll_to_end(self, page: Page, max_scrolls: int = 50, selector: str = ".c-assets__container"):
        print(f"📜 [DMarket] Scrolling container (Max {max_scrolls} scrolls)...")
        # No DMarket, o container com scroll geralmente é mat-sidenav-content
        # ou o elemento c-app que engloba tudo com overflow.
        container_selector = "mat-sidenav-content"
        
        container = page.query_selector(container_selector)
        if not container:
            # Fallback para o body se não achar o container específico
            container_selector = "body"

        scroll_count = 0
        last_count = 0
        no_change_count = 0
        
        while scroll_count < max_scrolls:
            try:
                # Scrola o container específico
                if container_selector == "body":
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                else:
                    page.evaluate(f"document.querySelector('{container_selector}').scrollTop += 1000")
                
                time.sleep(1.5) 
                
                new_count = len(page.query_selector_all("asset-card-v2"))
                if new_count == last_count:
                    no_change_count += 1
                    if no_change_count >= 5:
                        print("🛑 [DMarket] Fim da lista ou carregamento concluído.")
                        break
                else:
                    no_change_count = 0
                
                last_count = new_count
                scroll_count += 1
                if scroll_count % 5 == 0:
                    print(f"📜 [DMarket] Scroll {scroll_count}... (Itens carregados: {new_count})")
            except Exception as e:
                print(f"⚠️ [DMarket] Interrupção no scroll: {e}")
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
        # Prepara a query (DMarket aceita item + skin)
        full_query = f"{search_item} {search_skin}".strip()
        encoded_query = urllib.parse.quote(full_query)
        # URL base de busca
        search_url = f"{self.base_url}/ingame-items/item-list/csgo-skins?title={encoded_query}"
        
        print(f"🔍 [DMarket] Iniciando busca para: {full_query} (ST: {stattrak_allowed})")
        print(f"🚀 [DMarket] Navegando para: {search_url}")

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

            page = None
            if context and context.pages:
                for p in context.pages:
                    try:
                        if "dmarket.com" in p.url:
                            page = p
                            print(f"♻️ [DMarket] Reutilizando aba: {p.url}")
                            break
                    except: continue
            
            if not page:
                page = context.new_page()

            page.goto(search_url, wait_until="commit")
            # O usuário solicitou aguardar 60 segundos antes de procurar os elementos (para login, etc.)
            print(f"⏳ [DMarket] Aguardando 60 segundos para login e carregamento completo...")
            time.sleep(60)

            # Lógica para processar itens enquanto scrola (mais robusto para listas virtuais)
            processed_ids = set()
            found_count = 0
            
            # Container de scroll
            container_selector = "mat-sidenav-content"
            if not page.query_selector(container_selector):
                container_selector = "body"

            print(f"🔄 [DMarket] Iniciando varredura incremental...")
            
            for scroll_step in range(30): # Tenta scrolar até 30 vezes
                # Scrola um pouco
                if container_selector == "body":
                    page.evaluate("window.scrollBy(0, 500)")
                else:
                    page.evaluate(f"document.querySelector('{container_selector}').scrollBy(0, 500)")
                
                time.sleep(1.0)
                
                # Pega cards visíveis no momento
                visible_cards = page.query_selector_all("asset-card-v2")
                
                for i, card in enumerate(visible_cards):
                    try:
                        # Identificador único do card (usa inner_text + posição se necessário)
                        card_id = card.inner_text().replace("\n", "")[:50]
                        if card_id in processed_ids:
                            continue
                        
                        processed_ids.add(card_id)
                        
                        # Garante que o card está visível para os seletores funcionarem
                        card.scroll_into_view_if_needed()
                        time.sleep(0.1)

                        # 1. Nome 
                        img_el = card.query_selector("myth-image img")
                        full_name = img_el.get_attribute("alt").strip() if img_el else ""
                        if not full_name:
                            title_el = card.query_selector("h3, .c-asset__title")
                            full_name = title_el.inner_text().strip() if title_el else ""
                        
                        if not full_name: continue

                        # 2. StatTrak
                        is_pures = any(x in full_name for x in ["StatTrak", "ST ", "★ StatTrak™"])
                        
                        print(f"📦 [DMarket] Item {len(processed_ids)}: '{full_name}'")

                        if not stattrak_allowed and is_pures:
                            print("  ⏩ Ignorado: StatTrak desabilitado.")
                            continue

                        # 2.1 Verificação estrita de nome (evitar Gamma Doppler em busca de Doppler, etc.)
                        skin_lower = search_skin.lower().strip()
                        name_lower = full_name.lower()
                        
                        # Se procuramos "doppler" mas não "gamma", e o item é "gamma doppler", ignora
                        if "gamma" in name_lower and "gamma" not in skin_lower:
                            print(f"  ⏩ Ignorado: Gamma Doppler detectado para busca de Doppler normal.")
                            continue
                        
                        # Se procuramos "fade" mas não "marble", e o item é "marble fade", ignora
                        if "marble" in name_lower and "marble" not in skin_lower:
                            print(f"  ⏩ Ignorado: Marble Fade detectado para busca de Fade normal.")
                            continue
                        
                        # Verificação genérica: o nome deve conter a skin buscada
                        if skin_lower not in name_lower:
                            print(f"  ⏩ Ignorado: Skin '{search_skin}' não encontrada no nome.")
                            continue

                        # 3. Preço 
                        price_el = card.query_selector(".c-asset__priceNumber, asset-card-price")
                        price_text = price_el.inner_text().strip() if price_el else card.inner_text()
                        
                        pm = re.search(r'\$\s?([\d,.]+)', price_text)
                        if pm:
                            price_str = pm.group(1).replace(',', '')
                            price = round(float(price_str), 2)
                        else:
                            price = 0.0

                        # 4. Imagem
                        image_url = img_el.get_attribute("src") if img_el else ""

                        # 5. Estilo / Phase (EXTRAÇÃO VIA MODAL)
                        item_style = ""
                        float_val_modal = 0.0
                        try:
                            # Seletor exato do usuário para o botão de info
                            info_btn = card.query_selector("button.c-asset__action--info--purge-ignore, button[aria-label='asset action button']")
                            if info_btn:
                                print(f"  📑 Abrindo detalhes para '{full_name}'...")
                                info_btn.click(force=True) # force=True caso haja algum overlay
                                
                                # Espera forçada de 3 segundos (solicitado pelo usuário) para carregar info
                                time.sleep(3.0) 
                                
                                # Polling para dados (Max 3s ADICIONAIS)
                                start_time = time.time()
                                max_wait = 3.5
                                style_found = False
                                float_found_in_modal = False
                                price_found_in_modal = False
                                
                                # Pequeno loop de espera ativa
                                while (time.time() - start_time) < max_wait:
                                    # Verifica se modal existe
                                    modal_el = page.query_selector(".c-dialog--preview, mat-dialog-container")
                                    if not modal_el:
                                        time.sleep(0.1)
                                        continue
                                    
                                    modal_full_text = modal_el.inner_text()

                                    # Tenta pegar Estilo
                                    if not style_found:
                                        selectors = [
                                            ".c-assetPreviewParam__value--phaseTitle--purge-ignore",
                                            ".c-dialog--preview .c-assetPreviewParam__value",
                                            "mat-dialog-container .c-assetPreviewParam__value"
                                        ]
                                        for sel in selectors:
                                            style_el = page.query_selector(sel)
                                            if style_el:
                                                text = style_el.inner_text().strip()
                                                if "Phase" in text or "Ruby" in text or "Sapphire" in text:
                                                    item_style = text
                                                    style_found = True
                                                    print(f"  🔍 Estilo detectado: {item_style}")
                                                    break
                                        
                                        if not style_found:
                                            # Regex fallback No TEXTO GERAL do modal
                                            pm = re.search(r'(Phase\s?\d|Ruby|Sapphire|Black Pearl)', modal_full_text, re.I)
                                            if pm:
                                                item_style = pm.group()
                                                style_found = True
                                                print(f"  🔍 Estilo detectado (Regex): {item_style}")

                                    # Tenta pegar Float
                                    if not float_found_in_modal:
                                        float_el = page.query_selector(".o-qualityChart__infoValue .o-blur")
                                        if float_el:
                                            ft = float_el.inner_text().strip()
                                            fm = re.search(r'0\.\d+', ft)
                                            if fm:
                                                float_val_modal = float(fm.group())
                                                float_found_in_modal = True
                                                print(f"  ✨ Float detectado: {float_val_modal}")
                                        
                                        if not float_found_in_modal:
                                            # Regex No TEXTO GERAL do modal
                                            fm2 = re.search(r'Float\s*:?\s*(0\.\d+)', modal_full_text, re.I)
                                            if not fm2:
                                                fm2 = re.search(r'(0\.\d{3,})', modal_full_text)
                                            if fm2:
                                                float_val_modal = float(fm2.group(1))
                                                float_found_in_modal = True
                                                print(f"  ✨ Float detectado (Regex): {float_val_modal}")
                                    
                                    # Tenta pegar Preço (Busca por $ no texto geral do modal, mais confiável)
                                    if not price_found_in_modal:
                                        # Regex busca $ seguido de numeros, espaços, virgulas e pontos
                                        # Ex: $ 2 198.98  ou  $2,198.98
                                        # Pattern: \$\s?([\d\s.,]+)
                                        pm_price = re.search(r'\$\s?([\d\s.,]+)', modal_full_text)
                                        if pm_price:
                                            raw_price = pm_price.group(1).strip()
                                            # Limpeza robusta
                                            # Remove espaços e caracteres estranhos
                                            clean_p = raw_price.replace(" ", "").replace("\xa0", "")
                                            
                                            # Lógica de pontuação (milhar x decimal)
                                            if "," in clean_p and "." in clean_p:
                                                clean_p = clean_p.replace(",", "") # Remove milhar ,
                                            elif "," in clean_p:
                                                clean_p = clean_p.replace(",", ".") # Troca , por .
                                                
                                            try:
                                                price_val = float(clean_p)
                                                if price_val > 0:
                                                    price = round(price_val, 2)
                                                    price_found_in_modal = True
                                                    print(f"  💲 Preço detectado no modal (Busca $): ${price}")
                                            except:
                                                pass
                                                
                                        if not price_found_in_modal:
                                            # Tenta selector especifico se regex falhar
                                            price_el_modal = page.query_selector("price")
                                            if price_el_modal:
                                                pt = price_el_modal.inner_text().strip()
                                                cp = pt.replace("$", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
                                                try:
                                                    price_val = float(re.sub(r'[^\d.]', '', cp))
                                                    if price_val > 0:
                                                        price = round(price_val, 2)
                                                        price_found_in_modal = True
                                                        print(f"  💲 Preço detectado no modal (Tag Price): ${price}")
                                                except: pass


                                    # Se já achamos o que queríamos, sai (prioridade estilo e float, preço é bônus mas bom ter)
                                    if style_found and float_found_in_modal and price_found_in_modal:
                                        break
                                    
                                    # Se buscamos estilo específico e já achamos, talvez possamos sair?
                                    # Mas melhor tentar o float também.
                                    time.sleep(0.15)
                                
                                # Fecha modal (Tenta ESC primeiro para evitar issues com backdrop, depois botão)
                                # Ou melhor: Tenta botão com force=True, se falhar, ESC.
                                try:
                                    close_btn = page.query_selector("button.c-dialogHeader__close, .c-dialogHeader__inner button, mat-icon:has-text('close')")
                                    if close_btn:
                                        close_btn.click(force=True)
                                    else:
                                        page.keyboard.press("Escape")
                                except:
                                    page.keyboard.press("Escape")
                                
                                # Pequeno delay pós-fechamento
                                time.sleep(0.2)

                            else:
                                print(f"  ⚠️ Botão de info não encontrado no card {i+1}")
                        except Exception as me:
                            print(f"  ⚠️ Erro na interação com modal: {me}")
                            try: page.keyboard.press("Escape")
                            except: pass

                        # Fallback de estilo se modal falhou
                        if not item_style:
                            item_style = full_name

                        # Filtro de Estilo
                        match_style = True
                        if search_style:
                            s_style_lower = search_style.lower().strip()
                            comp_text = f"{full_name} {item_style}".lower().replace(" ", "").replace("-", "").replace("|", "")
                            
                            phase_map = {
                                "phase 1": ["phase1", "p1"],
                                "phase 2": ["phase2", "p2"],
                                "phase 3": ["phase3", "p3"],
                                "phase 4": ["phase4", "p4"],
                                "ruby": ["ruby"],
                                "sapphire": ["sapphire"],
                                "black pearl": ["black pearl", "bp"]
                            }
                            
                            variants = phase_map.get(s_style_lower, [s_style_lower])
                            variants_norm = [v.lower().replace(" ", "").replace("-", "") for v in variants]
                            
                            if not any(v in comp_text for v in variants_norm):
                                print(f"  ⏩ Ignorado: Estilo '{search_style}' não encontrado. (Buscado em: {comp_text})")
                                match_style = False
                        
                        if not match_style:
                            continue

                        # 6. Float 
                        float_val = 0.0
                        if float_val_modal > 0:
                            float_val = float_val_modal
                        else:
                            # Tenta seletor direto no card
                            float_el = card.query_selector(".o-blur, .c-asset__exteriorValue")
                            float_text = float_el.inner_text().strip() if float_el else card.inner_text()
                            fm = re.search(r'0\.\d+', float_text)
                            if fm:
                                float_val = float(fm.group())
                        
                        # Filtro Float (CORRIGIDO)
                        if float_val == 0.0:
                            # Se float é desconhecido, só rejeita se usuário exigiu min > 0
                            if float_min > 0.001:
                                print(f"  ⏩ Ignorado: Float desconhecido (0.0) e filtro requer > {float_min}.")
                                continue
                        elif float_val < float_min or float_val > float_max:
                            print(f"  ⏩ Ignorado: Float {float_val} fora do range ({float_min}-{float_max}).")
                            continue

                        new_item = SkinItem(
                            site="DMarket",
                            name=full_name,
                            float_value=float_val, # Correção: deve ser float, não string "N/A"
                            price=price,
                            url=f"https://dmarket.com/ingame-items/item-list/csgo-skins?title={urllib.parse.quote(full_name)}",
                            image_url=image_url
                        )

                        print(f"  🎯 ADICIONADO: ${price} (Style: {item_style})")
                        if on_item_found:
                            on_item_found(new_item)
                        items.append(new_item)

                    except Exception as e:
                        print(f"⚠️ [DMarket] Erro ao extrair card: {e}")

            print(f"✅ [DMarket] Scraping finalizado. {len(items)} itens extraídos.")
            return items

        except Exception as e:
            print(f"❌ [DMarket] Erro geral no DMarket: {e}")
            return items
        finally:
            if context and not cdp_url:
                context.close()

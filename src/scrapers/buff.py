from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import random
import re
import requests
import urllib.parse

def get_cny_to_usd_rate():
    try:
        # API pública gratuita (AwesomeAPI - Cotação de Moedas)
        # CNY-USD
        response = requests.get("https://economia.awesomeapi.com.br/last/CNY-USD", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Retorna o valor de "bid" (compra) ou "ask" (venda), usamos bid como referência média
            return float(data["CNYUSD"]["bid"])
    except Exception as e:
        print(f"⚠️ Erro ao obter cotação CNY->USD: {e}")
    
    return 0.14 # Fallback se falhar

class BuffScraper:
    def __init__(self):
        self.base_url = "https://buff.163.com/market/csgo"
        self.exchange_rate = get_cny_to_usd_rate()
        print(f"💱 Taxa de câmbio carregada: 1 CNY = {self.exchange_rate:.4f} USD")

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
        on_status_update=None,
        cdp_url=None,
        stattrak_allowed: bool = False
    ):
        items = []
        
        # Buff specific: "Phase 1" -> "Phase1"
        if search_style and "phase" in search_style.lower():
            search_style = search_style.replace(" ", "")
            
        print(f"🔍 DEBUG: Iniciando scraper Buff163... (StatTrak: {stattrak_allowed}, Style: {search_style})")
        
        if on_status_update:
            on_status_update("Iniciando Scraper Buff163...")
        
        context = None
        browser = None

        if cdp_url:
            print(f"🔌 Conectando a navegador existente em {cdp_url}...")
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            # Ao conectar via CDP, o contexto default já existe. 
            # Browser contexts via CDP: browser.contexts[0]
            if len(browser.contexts) > 0:
                context = browser.contexts[0]
            else:
                context = browser.new_context() # Fallback, mas raro em CDP de chrome puro
        else:
            # Monta os argumentos de lançamento (igual ao skins_com)
            args = [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-notifications",
                "--disable-search-engine-choice-screen",
            ]

            print(f"🔍 DEBUG: Criando contexto persistente para BUFF...")
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome" if not executable_path else None,
                executable_path=executable_path,
                headless=False, # Buff exige visualização e login
                args=args,
                viewport=None,
                ignore_default_args=["--enable-automation", "--no-sandbox"],
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                no_viewport=True,
            )

        # Stealth Scripts (Adiciona tanto no launch quanto no connect, se possível)
        # Em CDP connect, add_init_script funciona para novas navegações
        try:
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """)
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível injetar scripts stealth (pode ser normal em CDP): {e}")

        try:
            # Reusa ou cria página
            if len(context.pages) > 0:
                page = context.pages[0]
                # for extra_page in context.pages[1:]:
                #    extra_page.close()
            else:
                page = context.new_context().new_page() if not cdp_url else context.new_page()

            print(f"Navegando para {self.base_url}...")
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
            
            # === AGUARDAR LOGIN ===
            print("⏳ Preparando página base do Buff163...")
            time.sleep(3)
            
            if on_status_update:
                on_status_update("Verificando login e iniciando busca...")
            
            # Verifica Login (Buff exige login para ver detalhes/filtros avançados)
            if "account/login" in page.url or page.locator(".login-btn").count() > 0:
                # ...
                try:
                    page.wait_for_selector(".my-store", timeout=300000) # Aguarda elemento de usuário logado
                    print("✅ Login detectado!")
                except:
                    print("❌ Timeout aguardando login. Continuando mesmo assim (pode falhar)...")

            # Aplica filtros

            # === BUSCA ===
            full_search_term = f"{search_item} {search_skin}"
            print(f"🔍 Buscando por: '{full_search_term}'")
            
            # Input de busca
            search_input = page.locator('input[name="search"]').first
            if search_input.count() == 0:
                 search_input = page.locator('input.i_Text').first

            if search_input.count() > 0:
                search_input.click()
                search_input.fill("")
                # Digitação Humana
                for char in full_search_term:
                    page.keyboard.type(char, delay=random.randint(50, 150))
                time.sleep(0.5)
                page.keyboard.press("Enter")
            else:
                print("⚠️ Input de busca não encontrado!")
                # Fallback URL se possível
                page.goto(f"{self.base_url}?search={urllib.parse.quote(full_search_term)}")
            
            print(f"Aguardando resultados da busca... (Estilo alvo: '{search_style}')")
            time.sleep(3)
            
            # === FILTRO DE DESGASTE (EXTERIOR) ===
            def get_allowed_exteriors(f_min, f_max):
                if f_min <= 0.0 and f_max >= 1.0:
                    return ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
                
                categories = [
                    ("Factory New", 0.00, 0.07),
                    ("Minimal Wear", 0.07, 0.15),
                    ("Field-Tested", 0.15, 0.38),
                    ("Well-Worn", 0.38, 0.45),
                    ("Battle-Scarred", 0.45, 1.00),
                ]
                allowed = []
                for name, low, high in categories:
                    # Sobreposição estrita: se o range do usuário toca a categoria
                    if max(f_min, low) < min(f_max, high):
                        allowed.append(name)
                return allowed

            allowed_exteriors = get_allowed_exteriors(float_min, float_max)
            print(f"👕 Categorias de desgaste permitidas: {allowed_exteriors}")

            # === COLETA DE VARIANTES (MULTI-PASS) ===
            print("⏳ Analisando resultados da busca Buff...")
            try:
                # Atualizado para bater com o HTML real (.card_csgo li)
                page.wait_for_selector(".card_csgo li, .card_goods", timeout=15000)
            except:
                print("⚠️ Nenhum card detectado em 15s.")
            
            # Pega todos os li que representam itens
            items_li = page.locator(".card_csgo li[data-goods_id], .card_goods").all()
            print(f"Encontrados {len(items_li)} cards na busca.")
            
            variant_cards = []
            
            for li in items_li:
                try:
                    # O link e o título podem estar em um 'a' ou 'h3 a'
                    a_tag = li.locator("a[title]").first
                    title = a_tag.get_attribute("title")
                    href = a_tag.get_attribute("href")
                    
                    if not title or not href: continue
                    
                    # 1. Filtro de Nome (Busca Estrita)
                    clean_title = title.replace("StatTrak™ ", "").replace("★ ", "")
                    # Padrão Buff: "Item | Skin (Wear)"
                    if " | " in clean_title:
                        parts = clean_title.split(" | ")
                        item_part = parts[0].strip().lower()
                        skin_base = parts[1].lower()
                        
                        # === NOVOS FILTROS ESTRITOS (Correção Galil Bug) ===
                        # 1.1 Validar se o Item (ex: Karambit) é o mesmo
                        if item_part != search_item.lower():
                            print(f"❌ [Ignorado] Item incorreto: '{item_part}' != '{search_item.lower()}'")
                            continue
                        
                        # 1.2 Validar se a Skin (ex: Doppler) é a mesma
                        # Nota: No Buff, o nome da skin vem antes do desgaste, ex: "Doppler (Factory New)"
                        skin_part_only = skin_base.split("(")[0].strip().lower()
                        search_skin_lower = search_skin.lower()
                        
                        # Inteligente e estrito: Compara o nome exato da skin
                        # Isso evita que busca por "Fade" pegue "Marble Fade" ou "Doppler" pegue "Gamma Doppler"
                        if search_skin_lower != skin_part_only:
                             print(f"❌ [Ignorado] Skin não-exata: '{skin_part_only}' != '{search_skin_lower}' (Original: {title})")
                             continue

                        if search_style:
                            is_doppler = "doppler" in search_skin.lower()
                            search_style_norm = search_style.lower().replace(" ", "")
                            title_norm = title.lower().replace(" ", "")
                            
                            if "phase" in search_style_norm:
                                if not is_doppler and search_style_norm not in title_norm:
                                    continue
                            elif not is_doppler and search_style_norm not in title_norm:
                                continue
                    else:
                        # Fallback se o formato for inesperado
                        if search_item.lower() not in title.lower() or search_skin.lower() not in title.lower():
                            continue
                    
                    # 2. Filtro de StatTrak
                    is_st = "StatTrak" in title or "ST" in title
                    if is_st and not stattrak_allowed:
                        continue
                        
                    # 3. Filtro de Wear (Exterior)
                    wear_match = False
                    for ext in allowed_exteriors:
                        if ext in title:
                            wear_match = True
                            break
                    if not wear_match: continue
                    
                    # 4. Ignorar Souvenir
                    if "Souvenir" in title: continue

                    full_url = "https://buff.163.com" + href if href.startswith("/") else href
                    variant_cards.append({
                        "title": title,
                        "url": full_url,
                        "is_st": is_st
                    })
                    print(f"🎯 Variante encontrada: {title}")
                except: continue
                
            # === ORDENAÇÃO E PROCESSAMENTO SEQUENCIAL ===
            # Ordena para garantir que Normais venham antes dos StatTrak do mesmo desgaste
            variant_cards.sort(key=lambda x: (x["title"].replace("StatTrak™ ", "").replace("★ ", ""), x["is_st"]))
            
            processed_urls = set()
            for variant in variant_cards:
                url = variant["url"]
                if url in processed_urls: continue
                
                print(f"🚀 Abrindo nova aba para: {variant['title']}")
                # Abrimos uma NOVA PÁGINA para não perder a busca
                new_tab = context.new_page()
                try:
                    self.process_goods_page(new_tab, url, items, search_style, float_min, float_max, stattrak_allowed, on_item_found, search_item, search_skin)
                except Exception as ex:
                    print(f"⚠️ Erro ao processar variante {variant['title']}: {ex}")
                finally:
                    new_tab.close()
                    print(f"✅ Aba fechada: {variant['title']}")
                
                processed_urls.add(url)
                # Pequena pausa entre abas
                time.sleep(2)

            if not variant_cards:
                print("⚠️ Nenhum item específico encontrado. Tentando fallback...")
                # Fallback simples se nada foi processado
                for li in items_li:
                     a_tag = li.locator("a").first
                     title = a_tag.get_attribute("title") or ""
                     
                     # Check estrito no fallback
                     clean_t = title.replace("StatTrak™ ", "").replace("★ ", "")
                     if " | " in clean_t:
                         p = clean_t.split(" | ")
                         if p[0].strip().lower() == search_item.lower() and p[1].split("(")[0].strip().lower() == search_skin.lower():
                             href = a_tag.get_attribute("href")
                             if href:
                                 u = "https://buff.163.com" + href if href.startswith("/") else href
                                 self.process_goods_page(page, u, items, search_style, float_min, float_max, stattrak_allowed, on_item_found, search_item, search_skin)
                                 break

        except Exception as e:
            print(f"❌ Erro no scraper Buff: {e}")
        finally:
            if not cdp_url and context:
                context.close()
            
        return items

    def process_goods_page(self, page, url, items, search_style, float_min, float_max, stattrak_allowed, on_item_found, search_item, search_skin):
        try:
            page.goto(url)
            
            # === PÁGINA DE DETALHES & VERIFICAÇÃO DE NOME (ESTRITO) ===
            # Proteção final contra Gamma Doppler
            try:
                page.wait_for_selector(".cru-goods h1", timeout=10000)
                page_title = page.locator(".cru-goods h1").first.inner_text().strip()
                print(f"📄 Título na página Buff (Detalhes): {page_title}")
                
                # Normalização para comparação
                clean_page_title = page_title.replace("StatTrak™ ", "").replace("★ ", "").lower()
                
                # Verificação estrita
                if " | " in clean_page_title:
                    parts = clean_page_title.split(" | ")
                    if len(parts) >= 2:
                        item_part = parts[0].strip()
                        skin_part = parts[1].split("(")[0].strip()
                        
                        if item_part != search_item.lower() or search_skin.lower() not in skin_part:
                            print(f"❌ [Buff] Título ({page_title}) NÃO bate com busca ({search_item} | {search_skin}). Abortando pagina.")
                            return
                    else:
                         print("⚠️ Formato de título inesperado (sem '|')")
                else:
                    # Fallback de verificação se não houver o separador "|"
                    if search_item.lower() not in clean_page_title or search_skin.lower() not in clean_page_title:
                        print(f"❌ [Buff] Título não bate com busca (Fallback). Abortando.")
                        return
                print(f"✅ [Buff] Título verificado com sucesso: {page_title}")
            except:
                print("⚠️ Falha ao verificar título da página. Continuando com cautela...")

            print(f"👉 Processando página do item: {url}")
            print("Aguardando página de detalhes (6s)...")
            try:
                page.wait_for_selector("div.market-list", timeout=30000)
            except:
                print("⚠️ Timeout aguardando lista de mercado. Pular...")
                return

            time.sleep(6) # Aguarda carregamento total dos filtros dinâmicos
            
            if search_style:
                print(f"Procurando filtro de estilo: '{search_style}'...")
                
                # Procura todos os dropdowns de estilo
                style_dropdowns = page.locator("div.w-Select-Multi[category='unlock_style']")
                
                style_dropdown = None
                count = style_dropdowns.count()
                for i in range(count):
                    el = style_dropdowns.nth(i)
                    if el.is_visible():
                        style_dropdown = el
                        break
                
                if not style_dropdown and count > 0:
                    style_dropdown = style_dropdowns.first
                
                if style_dropdown:
                    ul_list = style_dropdown.locator("ul").first
                    if not ul_list.is_visible():
                        style_dropdown.click()
                        time.sleep(1)
                    
                    options = ul_list.locator("li h6").all()
                    target_option = None
                    search_style_clean = search_style.lower().replace(" ", "")
                    
                    for opt in options:
                        opt_text = opt.inner_text().lower().replace(" ", "").strip()
                        if search_style_clean == opt_text:
                            target_option = opt
                            break
                    
                    if target_option:
                        print(f"Clicando no estilo: {target_option.inner_text()}")
                        target_option.click(force=True)
                        time.sleep(3) 
                    else:
                        print(f"⚠️ Estilo '{search_style}' não encontrado no dropdown.")
                else:
                    print("⚠️ Dropdown de estilo não encontrado (pode não existir para esta skin).")

            # === FILTRO DE FLOAT E ORDENAÇÃO (URL QUERY PARAM) ===
            print(f"Aplicando filtros e ordenação via URL...")
            current_url = page.url
            base_url = current_url.split('#')[0]
            
            # Monta os parâmetros necessários, adicionando sort_by=price.asc
            params = ["tab=selling", "page_num=1", "sort_by=price.asc"]
            if float_min > 0.0 or float_max < 1.0:
                params.append(f"min_paintwear={float_min}")
                params.append(f"max_paintwear={float_max}")
                
            new_url = f"{base_url}#{'&'.join(params)}"
            
            print(f"Navegando para URL filtrada e ordenada: {new_url}")
            page.goto(new_url)
            print("Aguardando recarregamento com filtro e ordem (6s)...")
            time.sleep(6)

            # === COLETA DE ITENS (COM PAGINAÇÃO) ===
            main_img_url = ""
            try:
                main_img = page.locator(".detail-pic img").first
                if main_img.count() > 0:
                     main_img_url = main_img.get_attribute("src")
            except: pass

            # Limpa o título da página para remover desgastes e o nome do site
            # Ex: "★ Karambit | Doppler (Factory New) _ CS2 Market - BUFF163" -> "★ Karambit | Doppler"
            raw_title = page.title()
            page_title = raw_title.split("(")[0].split("_")[0].strip()
            
            page_num = 1
            max_pages = 50 
            count_this_variant = 0
            
            while True:
                print(f"--- Processando Página {page_num} ---")
                wait_time = 5 if page_num > 1 else 2
                time.sleep(wait_time)
                
                try:
                    page.wait_for_selector("table.list_tb", timeout=10000)
                except:
                    print("⚠️ Tabela não encontrada ou timeout. Encerrando paginação.")
                    break

                rows = page.locator("table.list_tb > tbody > tr").all()
                print(f"Encontradas {len(rows)} linhas.")

                for row in rows:
                    # Pular se for linha de cabeçalho ou não for um item de venda
                    row_id = row.get_attribute("id") or ""
                    row_class = row.get_attribute("class") or ""
                    
                    if "thead" in row_class.lower() or not row_id.startswith("sell_order_"):
                        continue
                    try:
                        price_el = row.locator("strong.f_Strong")
                        if price_el.count() == 0: 
                             # Tenta pegar qualquer strong que tenha classe de preço
                             price_el = row.locator("strong[class*='f_Strong']")
                            
                        if price_el.count() == 0: 
                            # Se for uma linha vazia ou informativa, não loga erro pesado
                            row_text = row.inner_text().strip()
                            if row_text:
                                print("⏭️ [Buff] Ignorado: Preço não encontrado nesta linha.")
                            continue
                        
                        price_text = price_el.inner_text().strip()
                        if not price_text: 
                            print("⏭️ [Buff] Ignorado: Texto de preço vazio.")
                            continue
                        
                        clean_text = price_text.replace("¥", "").strip().replace(" ", "")
                        if "," in clean_text and "." in clean_text:
                            if clean_text.rfind(",") > clean_text.rfind("."):
                                clean_text = clean_text.replace(".", "").replace(",", ".")
                            else:
                                clean_text = clean_text.replace(",", "")
                        elif "," in clean_text:
                             clean_text = clean_text.replace(",", "")
                        
                        try:
                            price_cny = float(clean_text)
                        except Exception as e: 
                            print(f"⏭️ [Buff] Ignorado: Erro ao converter preço '{clean_text}': {e}")
                            continue
                        
                        price_usd = price_cny * self.exchange_rate
                        
                        float_val = 0.0
                        float_el = row.locator(".wear-value")
                        if float_el.count() > 0:
                            float_val_text = float_el.inner_text().strip()
                            try:
                                match = re.search(r"(\d+\.\d+)", float_val_text)
                                if match: float_val = float(match.group(1))
                                else: float_val = float(float_val_text)
                            except: pass
                        else:
                            wear_td = row.locator("td").nth(2)
                            if wear_td.count() > 0:
                                 wear_text = wear_td.inner_text().strip()
                                 match = re.search(r"(\d+\.\d+)", wear_text)
                                 if match: float_val = float(match.group(1))

                        if float_val > 0 and not (float_min <= float_val <= float_max):
                            print(f"⏭️ [Buff] Ignorado (Float {float_val} fora da faixa: {float_min} - {float_max})")
                            continue
                        elif float_val == 0.0:
                            # Se não encontrou o wear-value, pode ser que o Buff não esteja mostrando.
                            # Mas se a página está filtrada, costumamos aceitar ou avisar.
                            # print(f"ℹ️ [Buff] Item com float 0.0 (não detectado na linha).")
                            pass
                            
                        img_el = row.locator("div.pic-cont img").first
                        if img_el.count() == 0:
                            img_el = row.locator("td img").first
                        
                        img_url = img_el.get_attribute("src") if img_el.count() > 0 else main_img_url
                        
                        # Nome final baseado no título real da página + desgaste
                        base_name = page_title
                        if " | " not in base_name:
                            base_name = f"★ {search_item} | {search_skin}"
                        
                        wear_name = ""
                        for ext, f_min_e, f_max_e in [
                            ("Factory New", 0.0, 0.07),
                            ("Minimal Wear", 0.07, 0.15),
                            ("Field-Tested", 0.15, 0.38),
                            ("Well-Worn", 0.38, 0.45),
                            ("Battle-Scarred", 0.45, 1.0)
                        ]:
                            if f_min_e <= float_val < f_max_e:
                                wear_name = ext
                                break
                        
                        if wear_name and wear_name not in base_name:
                            base_name += f" ({wear_name})"
                            
                        if search_style and search_style.lower() not in base_name.lower().replace(" ", ""):
                            style_display = search_style
                            if "phase" in search_style.lower() and len(search_style) > 5:
                                style_display = f"Phase {search_style[5:]}"
                            base_name += f" ({style_display})"

                        print(f"✅ [Buff] Item aceito: {base_name} (Float: {float_val}, Preço: ¥{price_cny} -> ${price_usd:.2f})")
                        item = SkinItem(
                            site="Buff163",
                            name=base_name,
                            float_value=float_val,
                            price=round(price_usd, 2),
                            url=page.url, 
                            image_url=img_url
                        )
                        
                        items.append(item)
                        count_this_variant += 1
                        if on_item_found:
                            on_item_found(item)
                            
                        # Limite de 20 itens por variante a pedido do usuário
                        if count_this_variant >= 20:
                            print(f"🛑 Limite de 20 itens atingido para a variante {base_name}.")
                            break
                            
                    except Exception as e: 
                        print(f"❌ [Buff] Erro ao processar linha: {e}")
                        continue
                
                if count_this_variant >= 20:
                    break
                
                next_btn = page.locator(".simple-pagination li:not(.disabled) .next").first
                if next_btn.is_visible():
                    next_btn.click()
                    page_num += 1
                    if page_num > max_pages: break
                else: break
                
            print(f"✅ Coleta finalizada para {url}.")
        except Exception as e:
            print(f"❌ Erro ao processar goods page {url}: {e}")

if __name__ == "__main__":
    # Teste isolado
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        scraper = BuffScraper()
        scraper.scrape(p, "Karambit", "Doppler", "Phase 3", 0.0, 0.01)

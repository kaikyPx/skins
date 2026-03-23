from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import random
import re
from src.utils import get_cny_to_usd_rate

class C5GameScraper:
    def __init__(self):
        self.base_url = "https://www.c5game.com/en/csgo"
        self.exchange_rate = get_cny_to_usd_rate()
        print(f"💱 [C5Game] Taxa de câmbio carregada: 1 CNY = {self.exchange_rate:.4f} USD")

    def scrape(
        self,
        playwright: Playwright,
        search_item: str,
        search_skin: str,
        search_style: str,
        float_min: float,
        float_max: float,
        user_data_dir="chrome_bot_profile",
        executable_path=None,
        on_item_found=None,
        cdp_url=None,
        stattrak_allowed: bool = False
    ):
        items = []
        
        # Mapping for Phase/Style
        # Map user friendly names (Phase1) to C5Game UI text (P1)
        phase_map = {
            "Phase1": "P1",
            "Phase2": "P2",
            "Phase3": "P3",
            "Phase4": "P4",
            "Ruby": "Ruby",
            "Sapphire": "Sapphire",
            "BlackPearl": "BlackPearl",
            "Emerald": "Emerald"
        }
        # Use mapped style if available, otherwise use original
        target_style = phase_map.get(search_style, search_style) if search_style else None
        
        context = None
        browser = None

        if cdp_url:
            print(f"🔌 [C5Game] Conectando a navegador existente em {cdp_url}...")
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            if len(browser.contexts) > 0:
                context = browser.contexts[0]
            else:
                context = browser.new_context()
        else:
            args = [
                "--start-maximized",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-notifications",
                "--disable-search-engine-choice-screen",
                "--disable-blink-features=AutomationControlled",
            ]

            print(f"🔍 DEBUG: Criando contexto persistente para C5GAME...")
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome" if not executable_path else None,
                executable_path=executable_path,
                headless=False,
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

        # Stealth Scripts
        try:
            context.add_init_script("""
                // 1. Pass the Webdriver Test
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });

                // 2. Pass the Chrome Test
                if (!window.chrome) {
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                }

                // 3. Pass the Permissions Test
                if (navigator.permissions) {
                    const originalQuery = navigator.permissions.query;
                    navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                        Promise.resolve({ state: 'denied', onchange: null }) :
                        originalQuery(parameters)
                    );
                }

                // 4. Pass the Plugins Length Test
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        var plugin1 = { name: "Chrome PDF Plugin", filename: "internal-pdf-viewer", description: "Portable Document Format" };
                        var plugin2 = { name: "Chrome PDF Viewer", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai", description: "Portable Document Format" };
                        var plugin3 = { name: "Native Client", filename: "internal-nacl-plugin", description: "" };
                        var plugins = [plugin1, plugin2, plugin3];
                        // Mimic PluginArray
                        plugins.item = function(index) { return this[index]; };
                        plugins.namedItem = function(name) { return this.find(p => p.name === name); };
                        plugins.refresh = function() {};
                        return plugins;
                    }
                });

                // 5. Pass the Languages Test
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['pt-BR', 'pt', 'en-US', 'en'],
                });
                
                // 6. Remove CDC_ variables (just in case)
                // Note: Playwright usually handles this with disable-blink-features, but good to be safe
                const cdc_regex = /cdc_[a-z0-9]/ig;
                for (const prop in window) {
                    if (prop.match(cdc_regex)) {
                        delete window[prop];
                    }
                }
            """)
        except:
            pass

        try:
            if len(context.pages) > 0:
                page = context.pages[0]
                for extra_page in context.pages[1:]:
                    extra_page.close()
            else:
                page = context.new_page()

            # 🛡️ INTERCEPTAÇÃO DE ROTA ANTI-BAN
            # Bloqueia qualquer navegação ou requisição que contenha 'console-ban'
            # Isso impede o redirecionamento forçado pelo site
            def block_console_ban(route):
                print(f"🚫 Bloqueando redirecionamento para BAN: {route.request.url}")
                route.abort()

            page.route("**/*console-ban*", block_console_ban)

            # 1. Direct Navigation (Stealth Mode)
            current_url = page.url
            if "console-ban" in current_url:
                print("⚠️ Detectada página de BANIMENTO (console-ban). Limpando cookies e tentando recuperar...")
                try:
                    context.clear_cookies()
                except:
                    pass
                page.goto("about:blank")
                time.sleep(2)
                try:
                    page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    print(f"⚠️ Erro ao recarregar após ban: {e}")
                
                print("⏳ Aguardando 1 minuto no site (Anti-Detection)...")
                time.sleep(60)
            elif "c5game.com" not in current_url:
                print(f"🌍 Navegando diretamente para {self.base_url}...")
                try:
                    page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    print(f"⚠️ Aviso na navegação inicial: {e}")
                
                print("⏳ Aguardando 1 minuto no site (Anti-Detection)...")
                time.sleep(60)
            else:
                print("🌍 Já estamos no C5Game, pulando navegação inicial...")
            
            # Smart Wait for Cloudflare/Bot Verification (Just in case)
            print("🛡️ Verificando proteção contra bots...")
            start_time = time.time()
            max_wait = 60
            
            while True:
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    print("⚠️ Timeout aguardando verificação de bot.")
                    break

                # Check for common bot verification texts/elements
                content = page.content().lower()
                if "just a moment" in content or "verify you are human" in content or "challenge-running" in content:
                    print(f"⏳ Detectada verificação de bot... Aguardando ({int(elapsed)}s)")
                    time.sleep(2)
                    continue
                
                # Check for success indicator (Search input or Logo)
                try:
                    if page.locator('input[placeholder*="Search"], input[name="k"], .header-logo, a.logo').first.is_visible():
                        print("✅ Página carregada com sucesso!")
                        break
                except:
                    pass
                
                time.sleep(1)

            # Extra safety wait after verification clears
            time.sleep(3)

            # === SEARCH ===
            full_search_term = f"{search_item} {search_skin}"
            print(f"🔍 Buscando por: '{full_search_term}'")

            # Try to find search input
            # Based on common structures, usually 'input[name="keyword"]' or similar
            # If not sure, we try generic selectors
            try:
                search_input = page.locator('input[placeholder*="Search"], input[name="k"], input[type="text"]').first
                if search_input.is_visible():
                    search_input.click()
                    search_input.fill(full_search_term)
                    page.keyboard.press("Enter")
                else:
                    print("⚠️ Input de busca não encontrado. Tentando navegar via URL...")
                    # Fallback URL construction if search fails
                    encoded_term = full_search_term.replace(" ", "%20")
                    page.goto(f"https://www.c5game.com/en/csgo?k={encoded_term}")
            except Exception as e:
                print(f"⚠️ Erro na busca: {e}")

            print("⏳ Aguardando resultados (8s)...")
            time.sleep(8)

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
                    if max(f_min, low) < min(f_max, high) or f_min == high or f_max == low:
                        allowed.append(name)
                return allowed

            allowed_exteriors = get_allowed_exteriors(float_min, float_max)
            print(f"👕 [C5Game] Categorias permitidas: {allowed_exteriors}")

            # === COLETA DE VARIANTES (MULTI-PASS) ===
            print("🔍 [C5Game] Analisando resultados da busca...")
            try:
                page.wait_for_selector(".list-item, .selling-list-item", timeout=15000)
            except:
                print("⚠️ Timeou aguardando lista de resultados.")

            item_links = page.locator("a").filter(has_text=search_item).all()
            variant_cards = []
            
            for link in item_links:
                try:
                    txt = link.inner_text()
                    href = link.get_attribute("href")
                    if not txt or not href: continue
                    
                    # Filtro de Nome (Busca Estrita)
                    clean_txt = txt.replace("StatTrak™ ", "").replace("StatTrak ", "").replace("ST ", "").replace("★ ", "")
                    if " | " in clean_txt:
                        parts = clean_txt.split(" | ")
                        item_part = parts[0].strip().lower()
                        skin_base = parts[1].lower()

                        if item_part != search_item.lower():
                            continue
                            
                        if search_skin.lower() not in skin_base and search_skin.lower() not in txt.lower():
                            continue

                        if "doppler" in search_skin.lower() and "gamma" in txt.lower() and "gamma" not in search_skin.lower():
                            continue

                        if search_style and search_style.lower() not in txt.lower():
                            continue
                    else:
                        if search_item.lower() not in txt.lower() or search_skin.lower() not in txt.lower():
                            continue
                        
                    is_st = "StatTrak" in txt or "ST" in txt
                    if is_st and not stattrak_allowed:
                        continue
                    
                    wear_match = False
                    for ext in allowed_exteriors:
                        if ext in txt:
                            wear_match = True
                            break
                    if not wear_match and "Souvenir" not in txt:
                        continue
                        
                    if "Souvenir" in txt: continue

                    full_url = "https://www.c5game.com" + href if href.startswith("/") else href
                    variant_cards.append({
                        "title": txt,
                        "url": full_url,
                        "is_st": is_st
                    })
                    print(f"✅ Variante C5Game encontrada: {txt}")
                except: continue
            
            # Ordenação: Normal antes de StatTrak
            variant_cards.sort(key=lambda x: (x["title"].replace("StatTrak™ ", "").replace("ST ", ""), x["is_st"]))
            
            processed_urls = set()
            for variant in variant_cards:
                url = variant["url"]
                if url in processed_urls: continue
                
                print(f"🚀 [C5Game] Abrindo nova aba para: {variant['title']}")
                new_tab = context.new_page()
                try:
                    self.process_item_listings(new_tab, url, items, target_style, float_min, float_max, on_item_found, search_item, search_skin, stattrak_allowed)
                except Exception as ex:
                    print(f"⚠️ Erro ao processar variante {variant['title']} no C5Game: {ex}")
                finally:
                    new_tab.close()
                
                processed_urls.add(url)
                time.sleep(2)

            if not variant_cards:
                print("⚠️ [C5Game] Nenhum link específico. Tentando fallback...")
                try:
                    first = page.locator(f"a:has-text('{search_item}'):has-text('{search_skin}')").first
                    if first.count() > 0:
                        href = first.get_attribute("href")
                        if href:
                             u = "https://www.c5game.com" + href if href.startswith("/") else href
                             self.process_item_listings(page, u, items, target_style, float_min, float_max, on_item_found, search_item, search_skin, stattrak_allowed)
                except: pass

            # Fallback logic and processing loop are already integrated into variant_cards sequential processing above.
            pass

        except Exception as e:
            print(f"❌ Erro fatal no C5Game scraper: {e}")
        finally:
            if not cdp_url and context:
                pass # Mantém aberto se necessário ou fecha
            
        return items

    def process_item_listings(self, page, url, items, target_style, float_min, float_max, on_item_found, search_item, search_skin, stattrak_allowed):
        print(f"👉 Processando página de listagens: {url}")
        try:
            page.goto(url)
            print("⏳ Aguardando página do item (8s)...")
            time.sleep(8)

            # === APPLY FILTERS (PHASE & FLOAT) ===
            
            # 1. Phase/Style Filter
            if target_style:
                print(f"🔍 Aplicando filtro de estilo: {target_style}")
                try:
                    style_btn = page.locator(f"li:has-text('{target_style}'), a:has-text('{target_style}'), span:has-text('{target_style}')").first
                    
                    if style_btn.is_visible():
                        style_btn.click()
                        print("✅ Estilo clicado.")
                        time.sleep(8)
                    else:
                        print(f"⚠️ Filtro '{target_style}' não encontrado na UI.")
                except Exception as e:
                    print(f"⚠️ Erro ao aplicar estilo: {e}")

            # 2. Float Filter (URL Params)
            if float_min > 0.0 or float_max < 1.0:
                print(f"🔍 Aplicando filtro de Float: {float_min}-{float_max}")
                current_url = page.url
                separator = "&" if "?" in current_url else "?"
                new_url = f"{current_url}{separator}minWear={float_min}&maxWear={float_max}"
                
                if "minWear" in current_url:
                    new_url = re.sub(r"minWear=[^&]*", f"minWear={float_min}", current_url)
                    new_url = re.sub(r"maxWear=[^&]*", f"maxWear={float_max}", new_url)
                
                if new_url != current_url:
                    print(f"Navegando para: {new_url}")
                    page.goto(new_url)
                    time.sleep(8)

            # === SCRAPE ITEMS ===
            page_num = 1
            max_pages = 50 
            
            while page_num <= max_pages:
                print(f"--- Processando Página {page_num} ---")
                
                try:
                    page.wait_for_selector(".sale-item-table, table, .list-container", timeout=10000)
                except:
                    print("⚠️ Tabela de itens não detectada.")
                
                rows = page.locator("tr, .list-item, .selling-item").all()
                print(f"Encontradas {len(rows)} linhas potenciais.")
                
                items_found_on_page = 0
                
                for row in rows:
                    try:
                        text_content = row.inner_text()
                        
                        price_match = re.search(r"[¥￥]\s*([\d\.,]+)", text_content)
                        if not price_match: continue
                            
                        # Tratamento de preço (vírgula vs ponto)
                        raw_price = price_match.group(1).strip()
                        if "," in raw_price and "." not in raw_price:
                            raw_price = raw_price.replace(",", "")
                        elif "," in raw_price and "." in raw_price:
                             raw_price = raw_price.replace(",", "")
                        
                        try:
                            price_cny = float(raw_price)
                        except: continue
                        
                        price_usd = price_cny * self.exchange_rate
                        
                        float_val = 0.0
                        float_match = re.search(r"(\d\.\d{4,})", text_content)
                        if float_match:
                            float_val = float(float_match.group(1))
                        
                        if float_val > 0 and not (float_min <= float_val <= float_max):
                            continue

                        img_url = ""
                        img_el = row.locator("img").first
                        if img_el.count() > 0:
                            img_url = img_el.get_attribute("src")
                            
                        # Nome Final
                        final_name = f"{search_item} | {search_skin}"
                        # Se a URL ou o item indicar ST, adiciona prefixo
                        if "StatTrak" in url or "StatTrak" in text_content or "ST" in text_content:
                            if "StatTrak" not in final_name:
                                final_name = "StatTrak™ " + final_name
                        
                        if target_style:
                            final_name += f" ({target_style})"

                        item = SkinItem(
                            name=final_name,
                            price=price_usd,
                            float_value=float_val,
                            image_url=img_url,
                            site="C5Game",
                            url=page.url 
                        )
                        
                        items.append(item)
                        items_found_on_page += 1
                        
                        if on_item_found:
                            on_item_found(item)
                            
                    except Exception as e: continue
                
                if items_found_on_page == 0:
                    print("⚠️ Nenhum item encontrado nesta página.")
                    break
                    
                # Paginação
                try:
                    next_btn = page.locator("a:has-text('Next'), a:has-text('>'), .next").first
                    if next_btn.is_visible() and "disabled" not in next_btn.get_attribute("class", ""):
                        print("➡️ Indo para próxima página...")
                        next_btn.click()
                        time.sleep(8)
                        page_num += 1
                    else:
                        print("⏹️ Fim da paginação.")
                        break
                except: break
        except Exception as e:
            print(f"❌ Erro ao processar listagem {url}: {e}")


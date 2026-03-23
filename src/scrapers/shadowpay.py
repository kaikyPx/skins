from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import re
import urllib.parse

class ShadowPayScraper:
    def __init__(self):
        self.base_url = "https://shadowpay.com/en/csgo-items"

    def scrape(self, playwright: Playwright, search_item: str, search_skin: str, search_style: str = "", float_min: float = 0.0, float_max: float = 1.0, user_data_dir="chrome_bot_profile", executable_path=None, on_item_found=None, cdp_url=None, stattrak_allowed: bool = False):
        print(f"[{self.__class__.__name__}] Iniciando scraping via DOM...")
        
        context = None
        if cdp_url:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0]
        else:
            context = playwright.chromium.launch_persistent_context(user_data_dir=user_data_dir, headless=False)

        page = context.pages[0] if context.pages else context.new_page()
        
        query_name = f"{search_item} {search_skin}".strip()
        search_url = f"https://shadowpay.com/en/csgo-items?search={urllib.parse.quote(query_name)}&sort_column=price&sort_dir=asc"
        
        print(f"[{self.__class__.__name__}] Navegando para: {search_url}")
        page.goto(search_url)
        
        try:
            # Espera carregar pelo menos um item usando o link do item como seletor
            page.wait_for_selector("a[href*='/item/']", timeout=30000)
            print(f"[{self.__class__.__name__}] Itens detectados. Aguardando estabilização...")
            time.sleep(5) # Aguarda o skeleton sumir totalmente
        except:
            print(f"[{self.__class__.__name__}] Nenhum item encontrado ou falha no carregamento (timeout).")
            return []

        # Scroll para carregar mais itens
        for i in range(2):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

        # Extração via JavaScript para maior robustez
        items_data = page.evaluate(r'''
            () => {
                const results = [];
                const cards = document.querySelectorAll("a[href*='/item/']");
                
                cards.forEach(card => {
                    // Evita cards que ainda são skeletons (podem não ter o texto completo)
                    if (card.innerText.includes("Suggested price")) {
                        const href = card.getAttribute("href");
                        const fullText = card.innerText;
                        
                        // Captura Preço (Ex: $ 1 509.86)
                        const priceMatch = fullText.match(/\$\s*([\d\s.,]+)/);
                        const price = priceMatch ? priceMatch[1].replace(/\s/g, '').replace(',', '.') : "0";
                        
                        // Captura Nome via aria-label ou estrutura de texto
                        let name = card.getAttribute("aria-label") || "";
                        name = name.replace(/^buy\s+/i, ""); // Remove "buy " do início
                        
                        // Captura Float
                        const floatMatch = fullText.match(/0\.\d+/);
                        const floatVal = floatMatch ? floatMatch[0] : "0";
                        
                        // Captura Imagem (Garante URL absoluta)
                        const img = card.querySelector("img");
                        let imgUrl = img ? img.getAttribute("src") : "";
                        if (imgUrl && imgUrl.startsWith("/")) {
                            imgUrl = "https://shadowpay.com" + imgUrl;
                        }
                        
                        // Captura Phase
                        const phaseMatch = fullText.match(/Phase\s*\d+/i);
                        const phase = phaseMatch ? phaseMatch[0] : "";

                        results.push({
                            name: name,
                            price: parseFloat(price),
                            float_val: parseFloat(floatVal),
                            phase: phase,
                            img_url: imgUrl,
                            link: "https://shadowpay.com" + href,
                            raw_text: fullText
                        });
                    }
                });
                return results;
            }
        ''')

        total_captured = 0
        print(f"[{self.__class__.__name__}] Processando {len(items_data)} itens extraídos...")
        
        for entry in items_data:
            try:
                full_name = entry['name']
                price = entry['price']
                float_val = entry['float_val']
                phase = entry['phase']
                is_st = "StatTrak" in full_name or "ST" in entry['raw_text']
                
                # Nome Final com Estilo/Phase se não estiver no nome
                display_name = full_name
                if phase and phase.lower() not in display_name.lower():
                    if " | " in display_name:
                        parts = display_name.split(" | ")
                        display_name = f"{parts[0]} | {parts[1]} ({phase})"
                    else:
                        display_name = f"{display_name} ({phase})"

                # Logs de depuração para cada item
                debug_info = f"   - [Encontrado] {display_name} | ${price} | Float: {float_val}"
                
                # Filtros
                if is_st and not stattrak_allowed:
                    print(f"{debug_info} -> Ignorado: StatTrak não permitido")
                    continue
                
                if float_val > 0:
                    if float_val < float_min or float_val > float_max:
                        print(f"{debug_info} -> Ignorado: Float ({float_val}) fora da faixa ({float_min}-{float_max})")
                        continue
                else:
                    # Se não tem float mas o usuário exige um range específico (não 0-1), ignoramos?
                    # Geralmente, se o float não é detectado mas o usuário quer low float, ignoramos por segurança.
                    if float_min > 0 or float_max < 1.0:
                        print(f"{debug_info} -> Ignorado: Float não disponível e range exigido")
                        continue
                
                # Filtro por Estilo (search_style)
                if search_style and search_style.lower() not in display_name.lower():
                    print(f"{debug_info} -> Ignorado: Estilo '{search_style}' não encontrado no nome")
                    continue

                print(f"   ✅ [ShadowPay] CAPTURADO: {display_name} | ${price} | Float: {float_val}")

                item_obj = SkinItem(
                    site="ShadowPay",
                    name=display_name,
                    price=price,
                    float_value=float_val,
                    image_url=entry['img_url'],
                    url=entry['link']
                )
                
                if on_item_found:
                    on_item_found(item_obj)
                total_captured += 1
                
            except Exception as e:
                print(f"   ❌ Erro ao processar entrada: {e}")
                continue

        print(f"[{self.__class__.__name__}] Finalizado ShadowPay. Total: {total_captured} itens.")
        return []



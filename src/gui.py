import flet as ft
import os
import json
import winreg
import shutil
import pyperclip

# Removido configuração global de PLAYWRIGHT_BROWSERS_PATH para evitar conflitos no modo padrão
# os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

import sys
# Adiciona o diretório raiz ao sys.path para suportar importações do pacote 'src'
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from playwright.sync_api import sync_playwright
from src.scrapers.buff import BuffScraper
from src.scrapers.csfloat import CSFloatScraper
from src.scrapers.csmoney import CSMoneyScraper
from src.scrapers.marketcsgo import MarketCSGOScraper
from src.scrapers.whitemarket import WhiteMarketScraper
from src.scrapers.shadowpay import ShadowPayScraper
from src.scrapers.haloskins import HaloSkinsScraper
from src.scrapers.rapidskins import RapidSkinsScraper
from src.scrapers.dmarket import DMarketScraper
from src.scrapers.avan import AvanScraper
from src.scrapers.lisskins import LisSkinsScraper
from src.scrapers.skinflow import SkinflowScraper
from src.scrapers.skinout import SkinoutScraper
from src.scrapers.dashskins import DashSkinsScraper
from src.scrapers.skinport import SkinportScraper
from src.scrapers.skinplace import SkinPlaceScraper
from src.scrapers.pirateswap import PirateSwapScraper
from src.scrapers.skinsmonkey import SkinsMonkeyScraper
from src.scrapers.itrade import ITradeScraper
from src.scrapers.tradeit import TradeItScraper
import threading

def find_chrome_executable():
    """Tenta encontrar o executável do Chrome de várias maneiras."""
    print("DEBUG: Iniciando busca do executável do Chrome...")
    
    # 1. Tentar ler do Registro do Windows (Maneira mais confiável)
    try:
        # HKEY_LOCAL_MACHINE
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                chrome_path, _ = winreg.QueryValueEx(key, "")
                if chrome_path and os.path.exists(chrome_path):
                    print(f"DEBUG: Chrome encontrado no registro (HKLM): {chrome_path}")
                    return chrome_path
        except:
            pass

        # HKEY_CURRENT_USER
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                chrome_path, _ = winreg.QueryValueEx(key, "")
                if chrome_path and os.path.exists(chrome_path):
                    print(f"DEBUG: Chrome encontrado no registro (HKCU): {chrome_path}")
                    return chrome_path
        except:
            pass
            
    except Exception as e:
        print(f"DEBUG: Erro ao ler registro: {e}")

    # 2. Tentar usar shutil.which (PATH do sistema)
    path_from_shutil = shutil.which("chrome")
    if path_from_shutil and os.path.exists(path_from_shutil):
        print(f"DEBUG: Chrome encontrado no PATH: {path_from_shutil}")
        return path_from_shutil

    # 3. Fallback para locais padrão conhecidos
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe")
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            print(f"DEBUG: Chrome encontrado em local padrão: {path}")
            return path
    
    print("DEBUG: Chrome NÃO encontrado.")
    return None

CONFIG_FILE = "config.json"

def main(page: ft.Page):
    page.title = "CS2 Skin Monitor"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.window_width = 1200
    page.window_height = 800

    # Configurações removidas (uso padrão)
    
    def load_config():
        return {}

    def save_config(path):
        pass

    # Estado dos dados
    items = []
    view_mode = "groups" # "groups" ou "details"
    selected_site = None
    
    # Pré-definir botão de voltar para evitar erros de referência
    btn_back = ft.TextButton("← Voltar para Grupos", visible=False)
    last_item_count = [0]

    # Grid para os cards - USANDO ROW COM WRAP PARA COMPATIBILIDADE COM SCROLL DA PÁGINA
    # GridView as vezes falha com altura 0 em colunas com scroll
    cards_grid = ft.Row(
        wrap=True,
        spacing=20,
        run_spacing=20,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


    # Indicador de carregamento
    loading = ft.ProgressBar(visible=False)
    status_text = ft.Text("Pronto para buscar.")
    result_count_text = ft.Text("Exibindo 0 de 0 itens", size=12, color=ft.Colors.GREY_400)

    loading_overlay = ft.Container(
        content=ft.Column([
            ft.ProgressRing(width=50, height=50, stroke_width=4),
            ft.Text("Aplicando ordem e filtros...", size=16, weight=ft.FontWeight.BOLD)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ft.alignment.Alignment(0, 0),
        padding=50,
        visible=False
    )


    def copy_link(e):
        try:
            pyperclip.copy(e.control.data)
            page.snack_bar = ft.SnackBar(ft.Text("Link copiado para a área de transferência!"))
        except Exception as ex:
            print(f"Erro ao copiar via pyperclip: {ex}")
            # Fallback para tentar método nativo se existir, ou apenas logar
            try:
                page.set_clipboard(e.control.data)
                page.snack_bar = ft.SnackBar(ft.Text("Link copiado via Flet!"))
            except:
                page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao copiar link: {ex}"))
        
        page.snack_bar.open = True
        page.update()

    def go_back(e):
        nonlocal view_mode, selected_site
        view_mode = "groups"
        selected_site = None
        update_table(force=True)

    btn_back.on_click = go_back

    def create_site_card(site_name, site_items):
        count = len(site_items)
        cheapest = min((getattr(item, 'price', 0) for item in site_items if getattr(item, 'price', 0) > 0), default=0)
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.LANGUAGE, size=40, color=ft.Colors.BLUE_400),
                    ft.Text(site_name, size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{count} skins encontradas", size=14, color=ft.Colors.GREY_400),
                    ft.Text(f"A partir de: ${cheapest:,.2f}" if cheapest > 0 else "Preço N/A", 
                            size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                    ft.FilledButton(
                        "Ver Skins",
                        on_click=lambda _: open_site_details(site_name),
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                padding=20,
                width=250,
            ),
            elevation=4
        )

    def open_site_details(site_name):
        nonlocal view_mode, selected_site
        view_mode = "details"
        selected_site = site_name
        update_table(force=True)

    def create_item_card(item):
        img_src = item.image_url if item.image_url else "https://via.placeholder.com/150"
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Stack([
                            ft.Image(
                                src=img_src, 
                                height=140, 
                                width=float("inf"), # Expandir total dentro do grid
                                fit="contain",
                                border_radius=ft.BorderRadius.all(10)
                            ),
                            ft.Container(
                                content=ft.Text(f"{item.percentage}% Off" if item.percentage > 0 else f"{item.site}", size=10, weight=ft.FontWeight.BOLD),
                                bgcolor=ft.Colors.GREEN_700 if item.percentage > 0 else ft.Colors.BLUE_GREY_800,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                border_radius=ft.BorderRadius.only(top_left=10, bottom_right=10),
                                alignment=ft.alignment.Alignment(-1, -1),
                                visible=True if item.percentage > 0 or item.site else False,
                            )
                        ]),
                        ft.Column([
                            ft.Text(
                                item.name, 
                                size=14, 
                                weight=ft.FontWeight.BOLD, 
                                max_lines=2, 
                                overflow=ft.TextOverflow.ELLIPSIS,
                                text_align=ft.TextAlign.CENTER
                            ),
                            ft.Text(f"Site: {item.site}", size=10, color=ft.Colors.GREY_400),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        
                        ft.Container(height=5),
                        
                        ft.Row(
                            [
                                ft.Column([
                                    ft.Text("Float", size=10, color=ft.Colors.GREY_500),
                                    ft.Text(f"{item.float_value:.10f}".rstrip('0').rstrip('.') if (getattr(item, 'float_value', 0) or 0) > 0 else "0.0", size=11, weight=ft.FontWeight.W_500),
                                ], spacing=0),
                                ft.Column([
                                    ft.Text("Preço", size=10, color=ft.Colors.GREY_500, text_align=ft.TextAlign.RIGHT),
                                    ft.Text(f"${item.price:.2f}", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        
                        ft.FilledButton(
                            "Ver Oferta",
                            # icon=ft.icons.OPEN_IN_NEW,
                            data=item.url,
                            on_click=copy_link,
                            style=ft.ButtonStyle(
                                color=ft.Colors.WHITE, 
                                bgcolor=ft.Colors.BLUE_700,
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                            width=float("inf"),
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10
                ),
                padding=12,
                width=250, # Largura fixa para que o wrap na Row funcione
            ),
            elevation=4,
        )

    def update_table(force=False):
        # Evitar reconstrução massiva se for apenas um novo item entrando (feedback visual)
        # Para performance, usamos uma lógica de cache ou apenas rebuild se necessário
        
        sort_mode = dd_sort.value
        display_items = items.copy()
        
        # Aplicar filtros de preço
        try:
            p_min = active_price_filter["min"]
            p_max = active_price_filter["max"]
            if p_min is not None:
                display_items = [i for i in display_items if i.price >= p_min]
            if p_max is not None:
                display_items = [i for i in display_items if i.price <= p_max]
        except:
            pass
            
        # Aplicar filtros de float
        try:
            f_min = active_float_filter["min"]
            f_max = active_float_filter["max"]
            if f_min is not None:
                display_items = [i for i in display_items if i.float_value > 0 and i.float_value >= f_min]
            if f_max is not None:
                display_items = [i for i in display_items if i.float_value > 0 and i.float_value <= f_max]
        except:
            pass
        
        # Ordenação
        # Ordenação
        if sort_mode == "name_asc":
            display_items.sort(key=lambda x: getattr(x, 'name', '').lower())
        elif sort_mode == "name_desc":
            display_items.sort(key=lambda x: getattr(x, 'name', '').lower(), reverse=True)
        elif sort_mode == "best_site":
            best_per_site = {}
            for item in display_items:
                site = getattr(item, 'site', 'Unknown')
                price = getattr(item, 'price', 0) or 0
                if site not in best_per_site:
                    best_per_site[site] = item
                else:
                    current_best = best_per_site[site]
                    current_price = getattr(current_best, 'price', 0) or 0
                    if (price < current_price and price > 0) or (current_price == 0 and price > 0):
                        best_per_site[site] = item
            display_items = list(best_per_site.values())
            display_items.sort(key=lambda x: getattr(x, 'price', 0) or 0)
        
        # Ordenação por preço ou nome (segura)
        if sort_mode == "price_asc":
            display_items.sort(key=lambda x: getattr(x, 'price', 0) or 0)
        elif sort_mode == "price_desc":
            display_items.sort(key=lambda x: getattr(x, 'price', 0) or 0, reverse=True)
        elif sort_mode == "float_asc":
            display_items.sort(key=lambda x: getattr(x, 'float_value', 0) if (getattr(x, 'float_value', 0) or 0) > 0 else 9.9)
        elif sort_mode == "float_desc":
            display_items.sort(key=lambda x: getattr(x, 'float_value', 0) if (getattr(x, 'float_value', 0) or 0) > 0 else -1.0, reverse=True)
        
        if view_mode == "groups":
            # Agrupar itens por site
            grouped = {}
            for item in display_items:
                site = getattr(item, 'site', 'Unknown')
                if site not in grouped:
                    grouped[site] = []
                grouped[site].append(item)
            
            # Ordenar grupos por nome do site ou por menor preço do grupo (baseado no sorting)
            sorted_groups = list(grouped.keys())
            if sort_mode == "price_asc":
                sorted_groups.sort(key=lambda s: min((getattr(i, 'price', 0) or 0 for i in grouped[s] if (getattr(i, 'price', 0) or 0) > 0), default=999999))
            elif sort_mode == "name_asc":
                sorted_groups.sort()
            
            cards_grid.controls = [create_site_card(site, grouped[site]) for site in sorted_groups]
            btn_back.visible = False
        else:
            # Mostrar apenas skins do site selecionado
            site_items = [i for i in display_items if i.site == selected_site]
            cards_grid.controls = [create_item_card(item) for item in site_items]
            btn_back.visible = True
            btn_back.text = f"← Voltar para Grupos (Site: {selected_site})"

        # Determinar se deve atualizar os controles
        # Atualizamos se force=True OU se o modo mudou OU se a quantidade de itens mudou
        should_update = force or len(items) != last_item_count[0]
        last_item_count[0] = len(items)

        if should_update:
            if view_mode == "groups":
                result_count_text.value = f"Exibindo {len(cards_grid.controls)} sites"
            else:
                result_count_text.value = f"Exibindo {len(cards_grid.controls)} skins de {selected_site}"
            
            # Atualizar visibilidade dos indicadores de filtro na UI (badges)
            try:
                price_filter_text.parent.visible = active_price_filter["min"] is not None or active_price_filter["max"] is not None
                float_filter_text.parent.visible = active_float_filter["min"] is not None or active_float_filter["max"] is not None
            except:
                pass

            page.update()
        else:
            # Se a quantidade é a mesma, talvez só a ordem mudou ou valores internos (raro aqui)
            # Re-populamos de qualquer forma se for force, mas evitamos se for idêntico
            if force:
                cards_grid.controls = [create_item_card(item) for item in display_items]
                page.update()

    def trigger_update_with_spinner():
        if not items:
            return
        loading_overlay.visible = True
        page.update()
        
        def work():
            import time
            time.sleep(0.1) # Reduzido delay
            update_table(force=True)
            loading_overlay.visible = False
            page.update()
            
        threading.Thread(target=work, daemon=True).start()

    def run_scraper(e):
        nonlocal items, view_mode, selected_site
        
        # Pega caminho do browser da config atual
        current_browser_path = None

        # Usa perfil dedicado na pasta do projeto
        user_data_dir = os.path.join(os.getcwd(), "chrome_bot_profile")
        
        # Parâmetros de busca
        search_item = txt_item.value.strip()
        search_skin = txt_skin.value.strip()
        search_style = txt_style.value.strip()
        try:
            float_min = float(txt_float_min.value.replace(',', '.'))
        except:
            float_min = 0.0
        try:
            float_max = float(txt_float_max.value.replace(',', '.'))
        except:
            float_max = 1.0
            
        stattrak_allowed = chk_stattrak.value

        print(f"DEBUG: Buscando por Item='{search_item}', Skin='{search_skin}', Estilo='{search_style}', Float={float_min}-{float_max}")
        print(f"DEBUG: Usando perfil: '{user_data_dir}'")

        # UI updates
        btn_refresh.disabled = True
        loading.visible = True
        status_text.value = "Iniciando busca... (Os itens aparecerão conforme encontrados)"
        items = [] # Limpa lista anterior
        view_mode = "groups" # Reset para visão de grupos
        selected_site = None
        cards_grid.controls.clear() # Limpa grid anterior
        page.update()

        # Buffer para atualização em lotes
        pending_items = []
        last_update_time = [0.0] # Inicializado como float
        import time

        def handle_new_item(item):
            nonlocal items
            items.append(item)
            pending_items.append(item)
            
            curr_time = time.time()
            # Atualiza a cada 0.8 segundos ou se tiver mais de 5 itens pendentes
            if curr_time - last_update_time[0] > 0.8 or len(pending_items) >= 5:
                try:
                    update_table()
                    last_update_time[0] = curr_time
                    pending_items.clear()
                except Exception as e:
                    print(f"Erro ao atualizar UI: {e}")

        def scrape_task():
            nonlocal items, page
            import subprocess
            import time
            import requests
            
            # Setup do Navegador Puro
            cdp_port = 9222
            cdp_url = f"http://localhost:{cdp_port}"
            chrome_process = None
            
            try:
                # 0. Verificar se já existe Chrome rodando na porta 9222
                chrome_already_running = False
                try:
                    # Tenta conectar na API de versão do CDP para ver se responde
                    resp = requests.get(f"{cdp_url}/json/version", timeout=2)
                    if resp.status_code == 200:
                        print("✅ Navegador Chrome já detectado rodando na porta 9222. Reutilizando...")
                        chrome_already_running = True
                except:
                    print("⚠️ Nenhum Chrome detectado na porta 9222. Iniciando um novo...")

                if not chrome_already_running:
                    # 1. Encontrar executável do Chrome
                    found_chrome = find_chrome_executable()
                    
                    if not found_chrome:
                        status_text.value = "ERRO: Google Chrome não encontrado! Instale-o e tente novamente."
                        page.update()
                        return

                    chrome_exe = f'"{found_chrome}"'

                    # 2. Matar processos antigos APENAS se fomos lançar um novo e falhamos em conectar
                    # (Removido taskkill agressivo para evitar fechar o navegador do usuário)

                    # 3. Lançar Chrome "Puro" com Debug Port
                    status_text.value = "Iniciando Chrome em modo 'Stealth' (Aguardando 10s)..."
                    page.update()
                    
                    cmd = (
                        f'{chrome_exe} '
                        f'--remote-debugging-port={cdp_port} '
                        f'--user-data-dir="{user_data_dir}" '
                        f'--start-maximized '
                        f'--no-first-run '
                        f'--no-default-browser-check '
                        f'"about:blank"'
                    )
                    
                    print(f"🚀 Lançando Chrome Puro: {cmd}")
                    # Usamos subprocess.Popen mas NÃO guardamos referência forte para matar depois
                    # Queremos que ele sobreviva
                    chrome_process = subprocess.Popen(cmd, shell=True)
                    
                    # 4. Aguardar 10 segundos (Simulação de Humano inicial)
                    for i in range(10, 0, -1):
                        status_text.value = f"Aquecendo motor 'Stealth'... {i}s restantes (Não feche o navegador!)"
                        page.update()
                        time.sleep(1)
                else:
                    status_text.value = "Navegador reutilizado! Iniciando conexão..."
                    page.update()
                    
                status_text.value = "Conectando ao navegador..."
                page.update()

                with sync_playwright() as p:
                    # BUFF SCRAPER
                    if chk_buff.value:
                        buff_scraper = BuffScraper()
                        try:
                            buff_scraper.scrape(
                                p, 
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None, # Não usado via CDP
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                on_status_update=lambda msg: (setattr(status_text, 'value', msg), page.update()), # Atualiza status na UI
                                cdp_url=cdp_url, # Passa a URL de conexão
                                stattrak_allowed=stattrak_allowed # Novo argumento
                            )
                        except TypeError as te:
                            if "unexpected keyword argument 'stattrak_allowed'" in str(te):
                                print(f"⚠️ Scraper Buff163 ainda não suporta StatTrak, chamando sem o argumento...")
                                buff_scraper.scrape(
                                    p, 
                                    search_item=search_item,
                                    search_skin=search_skin,
                                    search_style=search_style,
                                    float_min=float_min,
                                    float_max=float_max,
                                    executable_path=None,
                                    user_data_dir=user_data_dir,
                                    on_item_found=handle_new_item,
                                    cdp_url=cdp_url
                                )
                            else:
                                raise te

                    # CSFLOAT SCRAPER
                    if chk_csfloat.value:
                        print(f"--- Iniciando CSFloat Scraper (StatTrak Allowed: {stattrak_allowed}) ---")
                        csfloat_scraper = CSFloatScraper()
                        try:
                            csfloat_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except TypeError as te:
                            if "unexpected keyword argument 'stattrak_allowed'" in str(te):
                                print(f"⚠️ Scraper CSFloat ainda não suporta StatTrak, chamando sem o argumento...")
                                csfloat_scraper.scrape(
                                    p,
                                    search_item=search_item,
                                    search_skin=search_skin,
                                    search_style=search_style,
                                    float_min=float_min,
                                    float_max=float_max,
                                    executable_path=None,
                                    user_data_dir=user_data_dir,
                                    on_item_found=handle_new_item,
                                    cdp_url=cdp_url
                                )
                            else:
                                raise te

                    # CSMONEY SCRAPER
                    if chk_csmoney.value:
                        print("--- Iniciando CSMoney Scraper ---")
                        csmoney_scraper = CSMoneyScraper()
                        try:
                            csmoney_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except TypeError as te:
                            if "unexpected keyword argument 'stattrak_allowed'" in str(te):
                                print(f"⚠️ Scraper CS.Money ainda não suporta StatTrak, chamando sem o argumento...")
                                csmoney_scraper.scrape(
                                    p,
                                    search_item=search_item,
                                    search_skin=search_skin,
                                    search_style=search_style,
                                    float_min=float_min,
                                    float_max=float_max,
                                    executable_path=None,
                                    user_data_dir=user_data_dir,
                                    on_item_found=handle_new_item,
                                    cdp_url=cdp_url
                                )
                            else:
                                raise te

                    # MARKETCSGO SCRAPER
                    if chk_marketcsgo.value:
                        print("--- Iniciando MarketCSGO Scraper ---")
                        marketcsgo_scraper = MarketCSGOScraper()
                        try:
                            marketcsgo_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except TypeError as te:
                            if "unexpected keyword argument 'stattrak_allowed'" in str(te):
                                print(f"⚠️ Scraper MarketCSGO ainda não suporta StatTrak, chamando sem o argumento...")
                                marketcsgo_scraper.scrape(
                                    p,
                                    search_item=search_item,
                                    search_skin=search_skin,
                                    search_style=search_style,
                                    float_min=float_min,
                                    float_max=float_max,
                                    executable_path=None,
                                    user_data_dir=user_data_dir,
                                    on_item_found=handle_new_item,
                                    cdp_url=cdp_url
                                )
                            else:
                                raise te

                    # WHITE MARKET SCRAPER
                    if chk_whitemarket.value:
                        print("--- Iniciando White Market Scraper ---")
                        whitemarket_scraper = WhiteMarketScraper()
                        try:
                            whitemarket_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except TypeError as te:
                            if "unexpected keyword argument 'stattrak_allowed'" in str(te):
                                print(f"⚠️ Scraper White Market ainda não suporta StatTrak, chamando sem o argumento...")
                                whitemarket_scraper.scrape(
                                    p,
                                    search_item=search_item,
                                    search_skin=search_skin,
                                    search_style=search_style,
                                    float_min=float_min,
                                    float_max=float_max,
                                    executable_path=None,
                                    user_data_dir=user_data_dir,
                                    on_item_found=handle_new_item,
                                    cdp_url=cdp_url
                                )
                            else:
                                raise te

                    # SHADOWPAY SCRAPER
                    if chk_shadowpay.value:
                        print("--- Iniciando ShadowPay Scraper ---")
                        shadowpay_scraper = ShadowPayScraper()
                        try:
                            shadowpay_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper ShadowPay: {e}")

                    # HALOSKINS SCRAPER
                    if chk_haloskins.value:
                        print("--- Iniciando HaloSkins Scraper ---")
                        haloskins_scraper = HaloSkinsScraper()
                        try:
                            haloskins_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper HaloSkins: {e}")

                    # RAPIDSKINS SCRAPER
                    if chk_rapidskins.value:
                        print("--- Iniciando RapidSkins Scraper ---")
                        rapidskins_scraper = RapidSkinsScraper()
                        try:
                            rapidskins_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper RapidSkins: {e}")

                    # DMARKET SCRAPER
                    if chk_dmarket.value:
                        print("--- Iniciando DMarket Scraper ---")
                        dmarket_scraper = DMarketScraper()
                        try:
                            dmarket_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper DMarket: {e}")

                    # AVAN.MARKET SCRAPER
                    if chk_avan.value:
                        print("--- Iniciando Avan.Market Scraper ---")
                        try:
                            browser = p.chromium.connect_over_cdp(cdp_url)
                            context = browser.contexts[0] if len(browser.contexts) > 0 else browser.new_context()
                            playwright_page = context.new_page()
                            
                            avan_scraper = AvanScraper(base_url="https://avan.market")
                            avan_scraper.scrape(
                                page=playwright_page,
                                on_item_found=handle_new_item,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                stattrak_allowed=stattrak_allowed
                            )
                            
                            playwright_page.close() 
                            
                        except Exception as e:
                            print(f"⚠️ Erro no scraper Avan.Market: {e}")

                    # LISSKINS SCRAPER
                    if chk_lisskins.value:
                        print("--- Iniciando LisSkins Scraper ---")
                        lisskins_scraper = LisSkinsScraper()
                        try:
                            lisskins_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper LisSkins: {e}")

                    # SKINFLOW SCRAPER
                    if chk_skinflow.value:
                        print("--- Iniciando Skinflow Scraper ---")
                        skinflow_scraper = SkinflowScraper()
                        try:
                            skinflow_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                on_item_found=handle_new_item,
                                cdp_url=cdp_url,
                                stattrak_allowed=stattrak_allowed
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper Skinflow: {e}")

                    # SKINOUT SCRAPER
                    if chk_skinout.value:
                        print("--- Iniciando Skinout Scraper ---")
                        skinout_scraper = SkinoutScraper()
                        try:
                            skinout_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                stattrak_allowed=stattrak_allowed,
                                on_item_found=handle_new_item,
                                executable_path=None,
                                user_data_dir=user_data_dir,
                                cdp_url=cdp_url
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper Skinout: {e}")

                    # DASHSKINS SCRAPER
                    if chk_dashskins.value:
                        print("--- Iniciando DashSkins Scraper ---")
                        dashskins_scraper = DashSkinsScraper()
                        try:
                            dashskins_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                stattrak_allowed=stattrak_allowed,
                                on_item_found=handle_new_item,
                                user_data_dir=user_data_dir,
                                executable_path=None,
                                cdp_url=cdp_url
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper DashSkins: {e}")

                    # SKINPORT SCRAPER
                    if chk_skinport.value:
                        print("--- Iniciando Skinport Scraper ---")
                        skinport_scraper = SkinportScraper()
                        try:
                            skinport_scraper.scrape(
                                p,
                                search_item=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                float_min=float_min,
                                float_max=float_max,
                                stattrak_allowed=stattrak_allowed,
                                on_item_found=handle_new_item,
                                user_data_dir=user_data_dir,
                                executable_path=None,
                                cdp_url=cdp_url
                            )
                        except Exception as e:
                            print(f"⚠️ Erro no scraper Skinport: {e}")

                    # SKINPLACE SCRAPER
                    if chk_skinplace.value:
                        print("--- Iniciando SkinPlace Scraper ---")
                        skinplace_scraper = SkinPlaceScraper(page=p) # Pass playwright page or context if needed, but the class takes 'page' in constructor
                        # Wait, the class __init__ takes 'page'.
                        # In scrape_task we have 'p' which is playwright context manager.
                        # But other scrapers take 'p' in 'scrape' method.
                        # SkinPlaceScraper.__init__ takes 'page'.
                        # Let's check how other scrapers are initialized.
                        # Most take 'p' in 'scrape'.
                        # My SkinPlaceScraper takes 'page' in __init__.
                        # This matches how I wrote it: start browser inside? No, it takes 'page'.
                        # But here in gui.py we are inside 'with sync_playwright() as p:'.
                        # We need to launch browser or connect to CDP.
                        # The existing code connects to CDP: browser = p.chromium.connect_over_cdp(cdp_url)
                        # Then context = browser.contexts[0] -> page = context.new_page()
                        # See Avan logic (lines 580-586).
                        # I should perform the CDP connection for SkinPlace too.
                        
                        try:
                            # Reuse browser connection logic
                            browser = p.chromium.connect_over_cdp(cdp_url)
                            context = browser.contexts[0] if len(browser.contexts) > 0 else browser.new_context()
                            playwright_page = context.new_page()
                            
                            skinplace_scraper = SkinPlaceScraper(page=playwright_page)
                            
                            # Construct broad query (Item + Skin only)
                            query_parts = [p for p in [search_item, search_skin] if p]
                            broad_query = " ".join(query_parts).strip()
                            
                            found_items = skinplace_scraper.scrape(
                                item_name=broad_query,
                                style=search_style if search_style else None
                            )
                            
                            for item in found_items:
                                handle_new_item(item)
                                
                            playwright_page.close()
                        except Exception as e:
                            print(f"⚠️ Erro no scraper SkinPlace: {e}")

                    # PIRATESWAP SCRAPER
                    if chk_pirateswap.value:
                        print("--- Iniciando PirateSwap Scraper ---")
                        try:
                            # Reusing the browser connection pattern
                            browser = p.chromium.connect_over_cdp(cdp_url)
                            context = browser.contexts[0] if len(browser.contexts) > 0 else browser.new_context()
                            playwright_page = context.new_page()
                            
                            pirateswap_scraper = PirateSwapScraper(page=playwright_page)
                            
                            # Construct full search query
                            pirate_query = f"{search_item} {search_skin}".strip()
                            
                            found_items = pirateswap_scraper.scrape(
                                item_name=pirate_query,
                                search_skin=search_skin,
                                search_style=search_style,
                                min_float=float_min,
                                max_float=float_max,
                                stattrak=stattrak_allowed
                            )
                            
                            for item in found_items:
                                handle_new_item(item)
                                
                            playwright_page.close()
                        except Exception as e:
                            print(f"⚠️ Erro no scraper PirateSwap: {e}")

                    # SKINSMONKEY SCRAPER
                    if chk_skinsmonkey.value:
                        print("--- Iniciando SkinsMonkey Scraper ---")
                        try:
                            # Reusing the browser connection pattern
                            browser = p.chromium.connect_over_cdp(cdp_url)
                            context = browser.contexts[0] if len(browser.contexts) > 0 else browser.new_context()
                            playwright_page = context.new_page()
                            
                            skinsmonkey_scraper = SkinsMonkeyScraper(page=playwright_page)
                            
                            # Construct full search query
                            monkey_query = f"{search_item} {search_skin}".strip()
                            
                            found_items = skinsmonkey_scraper.scrape(
                                item_name=monkey_query,
                                search_skin=search_skin,
                                search_style=search_style,
                                min_float=float_min,
                                max_float=float_max,
                                stattrak=stattrak_allowed
                            )
                            
                            for item in found_items:
                                handle_new_item(item)
                                
                            playwright_page.close()
                        except Exception as e:
                            print(f"⚠️ Erro no scraper SkinsMonkey: {e}")

                    # ITRADE SCRAPER
                    if chk_itrade.value:
                        print("--- Iniciando iTrade Scraper ---")
                        try:
                            browser = p.chromium.connect_over_cdp(cdp_url)
                            context = browser.contexts[0] if len(browser.contexts) > 0 else browser.new_context()
                            playwright_page = context.new_page()
                            
                            itrade_scraper = ITradeScraper(page=playwright_page)
                            
                            # Search ONLY by item base name (e.g. "Karambit") for broader results
                            itrade_query = search_item.strip()
                            
                            print(f"DEBUG: iTrade enviando query: '{itrade_query}'")
                            
                            found_items = itrade_scraper.scrape(
                                item_name=itrade_query,
                                search_skin=search_skin,
                                search_style=search_style,
                                min_float=float_min,
                                max_float=float_max,
                                stattrak=stattrak_allowed
                            )
                            
                            for item in found_items:
                                handle_new_item(item)
                            
                            playwright_page.close()
                        except Exception as e:
                            print(f"⚠️ Erro no scraper iTrade: {e}")

                    # TRADEIT SCRAPER
                    if chk_tradeit.value:
                        print("--- Iniciando TradeIt Scraper ---")
                        try:
                            browser = p.chromium.connect_over_cdp(cdp_url)
                            context = browser.contexts[0] if len(browser.contexts) > 0 else browser.new_context()
                            playwright_page = context.new_page()
                            
                            tradeit_scraper = TradeItScraper(page=playwright_page)
                            
                            found_items = tradeit_scraper.scrape(
                                item_name=search_item,
                                search_skin=search_skin,
                                search_style=search_style,
                                min_float=float_min,
                                max_float=float_max,
                                stattrak=stattrak_allowed
                            )
                            
                            for item in found_items:
                                handle_new_item(item)
                            
                            playwright_page.close()
                        except Exception as e:
                            print(f"⚠️ Erro no scraper TradeIt: {e}")


            except Exception as ex:
                status_text.value = f"Erro: {str(ex)}"
                print(f"Erro no scrape_task: {ex}")
            finally:
                print(f"Busca finalizada com {len(items)} itens.")
                try:
                    # Forçar exibição final de qualquer item remanescente
                    update_table(force=True)
                except Exception as e:
                    print(f"Erro ao forçar atualização final: {e}")
                
                try:
                    btn_refresh.disabled = False
                    loading.visible = False
                    status_text.value = f"Pronto! {len(items)} itens encontrados."
                    page.update()
                except Exception as e:
                    print(f"Erro ao atualizar status final na UI: {e}")

        # Executar em thread separada para não travar a UI
        threading.Thread(target=scrape_task, daemon=True).start()

    def run_login_browser(e):
        nonlocal items
        
        # Pega caminho do browser da config atual
        current_browser_path = None
        user_data_dir = os.path.join(os.getcwd(), "chrome_bot_profile")
        
        # UI updates
        btn_login.disabled = True
        status_text.value = "Abrindo navegador para login..."
        page.update()

        def login_task():
            import subprocess
            
            # Tenta encontrar o executável do Chrome no Windows
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
            ]
            
            chrome_exe = "chrome.exe" # Fallback
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_exe = f'"{path}"' # Aspas para caminhos com espaço
                    break
            
            # Argumentos simplificados para evitar crash
            # Removido --no-first-run que as vezes causa problema em perfil novo via CLI
            cmd = f'{chrome_exe} --user-data-dir="{user_data_dir}" --start-maximized "https://www.google.com"'
            
            try:
                # Usando shell=True e string única para comando
                subprocess.Popen(cmd, shell=True)
                
                status_text.value = "Navegador nativo aberto. Faça login e feche-o manualmente."
            except Exception as ex:
                status_text.value = f"Erro ao abrir navegador nativo: {str(ex)}"
            finally:
                btn_login.disabled = False
                page.update()

        threading.Thread(target=login_task, daemon=True).start()

    # Campos de Busca
    txt_item = ft.TextField(label="Item", hint_text="Karambit", width=200)
    txt_skin = ft.TextField(label="Skin", hint_text="Doppler", width=200)
    txt_style = ft.TextField(label="Estilo", hint_text="Phase 3", width=200)
    
    # Float para busca nos scrapers
    txt_float_min = ft.TextField(label="Float Min", value="0.0", width=100, keyboard_type=ft.KeyboardType.NUMBER)
    txt_float_max = ft.TextField(label="Float Max", value="1.0", width=100, keyboard_type=ft.KeyboardType.NUMBER)
    
    # Filtros de faixa de preço (após a busca)
    txt_filter_price_min = ft.TextField(label="Preço Min $", value="", hint_text="0.00", width=100, keyboard_type=ft.KeyboardType.NUMBER)
    txt_filter_price_max = ft.TextField(label="Preço Max $", value="", hint_text="9999.00", width=100, keyboard_type=ft.KeyboardType.NUMBER)
    
    # Filtros de faixa de float (após a busca)
    txt_filter_float_min = ft.TextField(label="Float Min", value="", hint_text="0.0", width=100, keyboard_type=ft.KeyboardType.NUMBER)
    txt_filter_float_max = ft.TextField(label="Float Max", value="", hint_text="1.0", width=100, keyboard_type=ft.KeyboardType.NUMBER)

    # Checkboxes para seleção de sites
    chk_buff = ft.Checkbox(label="Buff163", value=True)
    chk_csfloat = ft.Checkbox(label="CSFloat", value=True)
    chk_csmoney = ft.Checkbox(label="CS.Money", value=True)
    chk_marketcsgo = ft.Checkbox(label="MarketCSGO", value=True)
    chk_whitemarket = ft.Checkbox(label="White Market", value=True)
    chk_shadowpay = ft.Checkbox(label="ShadowPay", value=True)
    chk_haloskins = ft.Checkbox(label="HaloSkins", value=True)
    chk_rapidskins = ft.Checkbox(label="RapidSkins", value=True)
    chk_dmarket = ft.Checkbox(label="DMarket", value=True)
    chk_avan = ft.Checkbox(label="Avan.Market", value=True)
    chk_lisskins = ft.Checkbox(label="LisSkins", value=True)
    chk_skinflow = ft.Checkbox(label="Skinflow", value=True)
    chk_skinout = ft.Checkbox(label="Skinout", value=True)
    chk_dashskins = ft.Checkbox(label="DashSkins", value=True)
    chk_skinport = ft.Checkbox(label="Skinport", value=True)
    chk_skinplace = ft.Checkbox(label="SkinPlace", value=True)
    chk_pirateswap = ft.Checkbox(label="Pirateswap", value=True)
    chk_skinsmonkey = ft.Checkbox(label="SkinsMonkey", value=True)
    chk_itrade = ft.Checkbox(label="iTrade.gg", value=True)
    chk_tradeit = ft.Checkbox(label="TradeIt.gg", value=True)
    chk_stattrak = ft.Checkbox(label="StatTrak?", value=False)

    # Botão de refresh
    btn_refresh = ft.FilledButton(
        "Atualizar Lista",
        icon="search", # Mudado para search pois agora é uma busca
        on_click=run_scraper,
        height=50,
    )

    # Botão de login
    btn_login = ft.FilledButton(
        "Logar em sites",
        icon="login",
        on_click=run_login_browser,
        height=50,
    )
    
    # Layout
    # --- Layout Refactor ---
    
    # Advanced Settings (Collapsible)
    advanced_controls = ft.ExpansionTile(
        title=ft.Text("Configurações Avançadas (Sites & StatTrak)", size=14, weight=ft.FontWeight.BOLD),
        subtitle=ft.Text("Selecione quais sites buscar e opções de StatTrak", size=12, color=ft.Colors.GREY_400),
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("Sites & Filtros Especiais:", weight=ft.FontWeight.BOLD),
                    ft.Row([chk_buff, chk_csfloat, chk_csmoney, chk_marketcsgo, chk_whitemarket], spacing=10),
                    ft.Row([chk_shadowpay, chk_haloskins, chk_rapidskins, chk_dmarket, chk_avan], spacing=10),
                    ft.Row([chk_lisskins, chk_skinflow, chk_skinout, chk_dashskins, chk_skinport], spacing=10),
                    ft.Row([chk_skinplace, chk_pirateswap, chk_skinsmonkey, chk_itrade, chk_tradeit], spacing=10),
                    ft.Row([chk_stattrak], spacing=10),
                ]),
                padding=10,
                bgcolor=ft.Colors.BLUE_GREY_900 if page.theme_mode == ft.ThemeMode.DARK else ft.Colors.GREY_200,
                border_radius=5
            )
        ]

    )

    # Sorting Dropdown
    def on_sort_change(e):
        print(f"DEBUG: on_sort_change acionado. Valor: {dd_sort.value}. Itens atuais: {len(items)}")
        # Re-ordena a lista atual
        if items:
            trigger_update_with_spinner()
        else:
            print("DEBUG: Lista de itens vazia, nada a ordenar.")

    dd_sort = ft.Dropdown(
        label="Ordenar por",
        width=220,
        options=[
            ft.dropdown.Option("price_asc", "Preço: Menor → Maior"),
            ft.dropdown.Option("price_desc", "Preço: Maior → Menor"),
            ft.dropdown.Option("float_asc", "Float: Menor → Maior"),
            ft.dropdown.Option("float_desc", "Float: Maior → Menor"),
            ft.dropdown.Option("name_asc", "Nome: A → Z"),
            ft.dropdown.Option("name_desc", "Nome: Z → A"),
            ft.dropdown.Option("best_site", "Melhor Preço por Site"),
        ],
        value="price_asc",
    )
    dd_sort.on_change = on_sort_change

    # Header Section (Fixed)
    header_section = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Monitoramento de Skins CS2", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                btn_login
            ]),
            ft.Divider(),
            ft.Text("Filtros de Busca:", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([
                txt_item,
                txt_skin,
                txt_style,
                txt_float_min,
                txt_float_max,
                # dd_sort movido para baixo
            ], wrap=True, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START),
            
            # Botão agora fica ao lado ou abaixo, vamos mantê-lo visível
            ft.Row([
                 btn_refresh
            ], alignment=ft.MainAxisAlignment.END),

            advanced_controls, # Seção Expansível
            
            ft.Divider(height=1, thickness=1),
            loading,
            status_text,
        ]),
        padding=10,
        # bgcolor=ft.Colors.SURFACE_VARIANT, # Opcional para distinguir header
    )

    # Variáveis para armazenar os valores dos filtros ativos
    active_price_filter = {"min": None, "max": None}
    active_float_filter = {"min": None, "max": None}
    
    # Textos que mostram os filtros ativos
    price_filter_text = ft.Text("Preço: Todos", size=12, color=ft.Colors.GREY_400)
    float_filter_text = ft.Text("Float: Todos", size=12, color=ft.Colors.GREY_400)
    
    def open_price_filter_modal(e):
        # Campos temporários para o modal
        temp_price_min = ft.TextField(
            label="Preço Mínimo $",
            value=str(active_price_filter["min"]) if active_price_filter["min"] else "",
            hint_text="0.00",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        temp_price_max = ft.TextField(
            label="Preço Máximo $",
            value=str(active_price_filter["max"]) if active_price_filter["max"] else "",
            hint_text="9999.00",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        
        def apply_price_filter(e):
            try:
                active_price_filter["min"] = float(temp_price_min.value.replace(',', '.')) if temp_price_min.value.strip() else None
            except:
                active_price_filter["min"] = None
            try:
                active_price_filter["max"] = float(temp_price_max.value.replace(',', '.')) if temp_price_max.value.strip() else None
            except:
                active_price_filter["max"] = None
            
            # Atualizar texto do filtro
            if active_price_filter["min"] is not None and active_price_filter["max"] is not None:
                price_filter_text.value = f"Preço: ${active_price_filter['min']:.2f} - ${active_price_filter['max']:.2f}"
            elif active_price_filter["min"] is not None:
                price_filter_text.value = f"Preço: ≥ ${active_price_filter['min']:.2f}"
            elif active_price_filter["max"] is not None:
                price_filter_text.value = f"Preço: ≤ ${active_price_filter['max']:.2f}"
            else:
                price_filter_text.value = "Preço: Todos"
            
            # Atualizar campos de filtro
            txt_filter_price_min.value = temp_price_min.value
            txt_filter_price_max.value = temp_price_max.value
            
            modal.open = False
            page.update()
            if items:
                trigger_update_with_spinner()
        
        def clear_price_filter(e):
            temp_price_min.value = ""
            temp_price_max.value = ""
            page.update()
        
        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Text("💰", size=24),
                ft.Text("Filtrar por Preço", size=20, weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Defina a faixa de preço desejada:", size=14, color=ft.Colors.GREY_400),
                    ft.Divider(),
                    ft.Row([
                        temp_price_min,
                        ft.Text("até", size=14, color=ft.Colors.GREY_400),
                        temp_price_max,
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                width=400,
            ),
            actions=[
                ft.TextButton("Limpar", on_click=clear_price_filter),
                ft.Button(
                    "Aplicar Filtro",
                    on_click=apply_price_filter,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.overlay.append(modal)
        modal.open = True
        page.update()
    
    def open_float_filter_modal(e):
        # Campos temporários para o modal
        temp_float_min = ft.TextField(
            label="Float Mínimo",
            value=str(active_float_filter["min"]) if active_float_filter["min"] else "",
            hint_text="0.00",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        temp_float_max = ft.TextField(
            label="Float Máximo",
            value=str(active_float_filter["max"]) if active_float_filter["max"] else "",
            hint_text="1.00",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        
        # Informações sobre faixas de float
        float_info = ft.Column([
            ft.Text("Referência de Float:", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400),
            ft.Row([
                ft.Text("FN: 0.00-0.07", size=10, color=ft.Colors.GREEN_400),
                ft.Text("MW: 0.07-0.15", size=10, color=ft.Colors.TEAL_400),
                ft.Text("FT: 0.15-0.38", size=10, color=ft.Colors.YELLOW_400),
                ft.Text("WW: 0.38-0.45", size=10, color=ft.Colors.ORANGE_400),
                ft.Text("BS: 0.45-1.00", size=10, color=ft.Colors.RED_400),
            ], spacing=10),
        ])
        
        def apply_float_filter(e):
            try:
                active_float_filter["min"] = float(temp_float_min.value.replace(',', '.')) if temp_float_min.value.strip() else None
            except:
                active_float_filter["min"] = None
            try:
                active_float_filter["max"] = float(temp_float_max.value.replace(',', '.')) if temp_float_max.value.strip() else None
            except:
                active_float_filter["max"] = None
            
            # Atualizar texto do filtro
            if active_float_filter["min"] is not None and active_float_filter["max"] is not None:
                float_filter_text.value = f"Float: {active_float_filter['min']:.2f} - {active_float_filter['max']:.2f}"
            elif active_float_filter["min"] is not None:
                float_filter_text.value = f"Float: ≥ {active_float_filter['min']:.2f}"
            elif active_float_filter["max"] is not None:
                float_filter_text.value = f"Float: ≤ {active_float_filter['max']:.2f}"
            else:
                float_filter_text.value = "Float: Todos"
            
            # Atualizar campos de filtro
            txt_filter_float_min.value = temp_float_min.value
            txt_filter_float_max.value = temp_float_max.value
            
            modal.open = False
            page.update()
            if items:
                trigger_update_with_spinner()
        
        def clear_float_filter(e):
            temp_float_min.value = ""
            temp_float_max.value = ""
            page.update()
        
        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Text("⚙️", size=24),
                ft.Text("Filtrar por Float", size=20, weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Defina a faixa de float desejada:", size=14, color=ft.Colors.GREY_400),
                    ft.Divider(),
                    ft.Row([
                        temp_float_min,
                        ft.Text("até", size=14, color=ft.Colors.GREY_400),
                        temp_float_max,
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                    ft.Divider(),
                    float_info,
                ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                width=450,
            ),
            actions=[
                ft.TextButton("Limpar", on_click=clear_float_filter),
                ft.Button(
                    "Aplicar Filtro",
                    on_click=apply_float_filter,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.overlay.append(modal)
        modal.open = True
        page.update()
    
    def clear_all_filters(e):
        active_price_filter["min"] = None
        active_price_filter["max"] = None
        active_float_filter["min"] = None
        active_float_filter["max"] = None
        txt_filter_price_min.value = ""
        txt_filter_price_max.value = ""
        txt_filter_float_min.value = ""
        txt_filter_float_max.value = ""
        price_filter_text.value = "Preço: Todos"
        float_filter_text.value = "Float: Todos"
        page.update()
        if items:
            trigger_update_with_spinner()
    
    # Botões de filtro estilo "chip"
    btn_price_filter = ft.Button(
        content=ft.Row([
            ft.Text("💰", size=14),
            ft.Text("Preço", size=12),
        ], spacing=5),
        on_click=open_price_filter_modal,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN_900,
            color=ft.Colors.GREEN_100,
            shape=ft.RoundedRectangleBorder(radius=20),
        ),
    )
    
    btn_float_filter = ft.Button(
        content=ft.Row([
            ft.Text("⚙️", size=14),
            ft.Text("Float", size=12),
        ], spacing=5),
        on_click=open_float_filter_modal,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_900,
            color=ft.Colors.BLUE_100,
            shape=ft.RoundedRectangleBorder(radius=20),
        ),
    )
    
    btn_clear_all = ft.Button(
        content=ft.Text("🗑️ Limpar", size=12),
        tooltip="Limpar todos os filtros",
        on_click=clear_all_filters,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
            color=ft.Colors.RED_400,
            shape=ft.RoundedRectangleBorder(radius=20),
        ),
    )
    
    # Results Section (Scrollable Area)
    results_section = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Resultados", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                btn_back,
                result_count_text,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=1),
            # Barra de ferramentas de filtro moderna
            ft.Container(
                content=ft.Row([
                    # Botões de filtro
                    ft.Row([
                        btn_price_filter,
                        btn_float_filter,
                        btn_clear_all,
                    ], spacing=10),
                    ft.Container(expand=True),
                    # Filtros ativos
                    ft.Row([
                        ft.Container(
                            content=price_filter_text,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.GREEN),
                            border_radius=15,
                            visible=False,
                        ),
                        ft.Container(
                            content=float_filter_text,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.BLUE),
                            border_radius=15,
                            visible=False,
                        ),
                    ], spacing=10),
                    ft.VerticalDivider(width=20),
                    # Ordenação
                    ft.Container(
                        content=ft.Row([
                            ft.Text("📊", size=14),
                            dd_sort,
                        ], spacing=5),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=ft.Padding.symmetric(horizontal=15, vertical=10),
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                border_radius=10,
                border=ft.Border(
                    left=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    top=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    right=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                ),
                margin=ft.Margin.symmetric(vertical=10),
            ),
            loading_overlay,
            cards_grid,
        ]),
        expand=False,
    )


    # Main Layout
    page.add(
        ft.Column(
            [
                header_section,
                results_section
            ],
            expand=False, 
            spacing=0 
        )
    )

    # TUDO ROLA JUNTO
    page.scroll = ft.ScrollMode.AUTO

if __name__ == "__main__":
    ft.run(main)

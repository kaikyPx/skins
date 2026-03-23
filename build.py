import PyInstaller.__main__
import os
import shutil

# Nome do executável
APP_NAME = "CS2SkinMonitor"

# Arquivo principal
MAIN_SCRIPT = "main.py"

# Limpar builds anteriores
if os.path.exists("build"):
    shutil.rmtree("build")
if os.path.exists("dist"):
    shutil.rmtree("dist")

print("Iniciando build com PyInstaller...")

# Argumentos do PyInstaller
args = [
    MAIN_SCRIPT,
    f"--name={APP_NAME}",
    "--onefile",           # Arquivo único (Portable)
    "--noconsole",         # Não mostrar janela de console
    "--clean",             # Limpar cache
    "--noconfirm",         # Não perguntar para sobrescrever
    
    # Imports ocultos que o PyInstaller pode não detectar
    "--hidden-import=flet",
    "--hidden-import=playwright",
    "--hidden-import=src",
]

# Tentar encontrar flet_desktop para incluir binários
try:
    import flet_desktop
    flet_desktop_path = os.path.dirname(flet_desktop.__file__)
    print(f"Encontrado flet_desktop em: {flet_desktop_path}")
    
    # Caminho para a pasta 'app' dentro do flet_desktop
    app_path = os.path.join(flet_desktop_path, "app")
    
    if os.path.exists(app_path):
        # Adicionar aos argumentos: source;dest
        # No Windows usa-se ; como separador
        add_data_arg = f"--add-data={app_path};flet_desktop/app"
        args.append(add_data_arg)
        print(f"Adicionando binários do Flet: {add_data_arg}")
    else:
        print("AVISO: Pasta 'app' não encontrada dentro do flet_desktop!")

except ImportError:
    print("AVISO: flet_desktop não encontrado. O executável pode não funcionar.")

# Add config to args
# args.append("--add-data=config.json;.")

PyInstaller.__main__.run(args)

print(f"Build concluído! Verifique a pasta 'dist/{APP_NAME}'")

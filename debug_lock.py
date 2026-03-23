from playwright.sync_api import sync_playwright
import os
import shutil

user_data_dir = os.path.abspath("chrome_bot_profile")
print(f"Testando perfil em: {user_data_dir}")

# Verifica locks
locks = [
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "LOCK",
    os.path.join("Default", "LOCK")
]

print("Verificando arquivos de lock:")
for lock in locks:
    path = os.path.join(user_data_dir, lock)
    if os.path.exists(path):
        print(f"  [EXISTE] {lock}")
        try:
            os.remove(path)
            print(f"  [REMOVIDO] {lock}")
        except Exception as e:
            print(f"  [ERRO AO REMOVER] {lock}: {e}")
    else:
        print(f"  [OK] {lock} não existe")

print("\nTentando lançar Playwright...")
try:
    with sync_playwright() as p:
        args = [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-notifications",
            "--disable-search-engine-choice-screen",
        ]
        
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=args,
            ignore_default_args=["--enable-automation", "--no-sandbox"],
            channel="chrome"
        )
        print("SUCESSO! Browser abriu.")
        context.close()
except Exception as e:
    print("\nERRO FATAL:")
    print(e)

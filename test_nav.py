from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

options = Options()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

print("Iniciando Chrome minimal...")
driver = webdriver.Chrome(options=options)

try:
    print("Navegando para Google...")
    driver.get("https://www.google.com")
    print("Sucesso ao navegar!")
    time.sleep(5)
finally:
    driver.quit()

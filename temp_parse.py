from bs4 import BeautifulSoup
import re
with open("paginaitem.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

item = soup.find("div", class_="item")
print(item.prettify())

print("Base info:")
name_el = soup.find("h1")
print("Name:", name_el.text.strip())
img_el = soup.find("meta", property="og:image")
print("Image:", img_el["content"] if img_el else None)
url_el = soup.find("meta", property="og:url")
print("Url:", url_el["content"] if url_el else None)

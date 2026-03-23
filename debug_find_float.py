
import re

with open("d:/projetos/skins/csfloat_debug.html", "r", encoding="utf-8") as f:
    content = f.read()

target = "0.165615305305"
index = content.find(target)

if index != -1:
    print(f"Found at index: {index}")
    start = max(0, index - 500)
    end = min(len(content), index + 500)
    print(content[start:end])
else:
    print("Target not found.")

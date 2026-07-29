import os

py_files = []
for root, dirs, files in os.walk("."):
    if ".venv" in root or ".git" in root or "__pycache__" in root:
        continue
    for file in files:
        if file.endswith(".py"):
            py_files.append(os.path.join(root, file))

for path in py_files:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        try:
            with open(path, "r", encoding="latin-1") as f:
                content = f.read()
        except Exception:
            continue
    
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if "/" in line and any(w in line.lower() for w in ["margen", "costo", "venta", "porc"]):
            print(f"{path}:{idx}: {line.strip()}")

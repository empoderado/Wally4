import os

db_dir = "database/wallybd"
for root, dirs, files in os.walk(db_dir):
    for file in files:
        if file.endswith(".sql"):
            path = os.path.join(root, file)
            # Try different encodings
            content = ""
            for encoding in ["utf-8", "utf-16", "latin-1"]:
                try:
                    with open(path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            if "margen" in content.lower():
                print(f"Match in {path}:")
                for line_no, line in enumerate(content.splitlines(), start=1):
                    if "margen" in line.lower():
                        print(f"  Line {line_no}: {line}")

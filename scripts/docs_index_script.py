"""
Script para gerar docs/INDEX.md automaticamente a partir dos arquivos em docs/.
"""
import os

docs_dir = "docs"
index_path = os.path.join(docs_dir, "INDEX.md")

entries = []
for fname in sorted(os.listdir(docs_dir)):
    if fname.endswith(".md") and fname.lower() != "index.md":
        with open(os.path.join(docs_dir, fname), encoding="utf-8") as f:
            first_line = f.readline().strip().lstrip("# ")
        entries.append(f"- [{first_line}]({fname})")

with open(index_path, "w", encoding="utf-8") as f:
    f.write("# Índice de Documentação OpenClaw\n\n")
    f.write("\n".join(entries))
    f.write("\n")

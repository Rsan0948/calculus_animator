import sys
import os
import ast

sys.path.insert(0, os.getcwd())

source_path = "ai_tutor/rag/concept_engine.py"

try:
    with open(source_path, "r", encoding="utf-8") as f:
        source_code = f.read()
    
    ast.parse(source_code)
    print("CLEAN: Module syntax is valid.")
    sys.exit(0)
except SyntaxError as e:
    print(f"REPRODUCED: SyntaxError found at line {e.lineno}: {e.msg}")
    sys.exit(1)

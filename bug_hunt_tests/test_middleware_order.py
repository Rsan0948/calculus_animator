import sys
import os
sys.path.insert(0, os.getcwd())

import ast
import types

# Stub dependencies to allow parsing without imports
for mod in ['fastapi', 'fastapi.middleware.cors', 'fastapi.responses', 'starlette.exceptions', 'ai_tutor.config', 'ai_tutor.logging_config', 'ai_tutor.middleware', 'ai_tutor.rag.concept_engine', 'ai_tutor.routers']:
    sys.modules[mod] = types.ModuleType(mod)

# Read source
with open('ai_tutor/main.py', 'r') as f:
    source = f.read()

# Parse AST
tree = ast.parse(source)

# Find the create_app function and extract add_middleware calls
middleware_calls = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'add_middleware':
            # Get the middleware class name (first argument)
            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Name):
                    middleware_calls.append(first_arg.id)

# The bug is that RequestIdMiddleware is registered last (innermost),
# but it should be first (outermost) to ensure ContextVar is set early.
# Expected order: RequestIdMiddleware, AccessLogMiddleware, CORSMiddleware, MaxBodySizeMiddleware
expected_order = ['RequestIdMiddleware', 'AccessLogMiddleware', 'CORSMiddleware', 'MaxBodySizeMiddleware']

if middleware_calls == expected_order:
    print("CLEAN: Middleware registration order is correct.")
    sys.exit(0)
else:
    print(f"REPRODUCED: Middleware registration order is incorrect. Found {middleware_calls}, expected {expected_order}.")
    sys.exit(1)
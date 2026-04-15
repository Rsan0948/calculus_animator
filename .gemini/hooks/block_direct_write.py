#!/usr/bin/env python3
"""BeforeTool hook: block direct write_file/replace, force MCP pipeline."""
import json
import sys


def main():
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", data.get("input", {})).get("file_path", "")
    # Block all direct writes — force everything through HelicOps MCP
    # (propose_write -> validate_write -> commit_write)
    json.dump({
        "decision": "deny",
        "reason": (
            "BLOCKED: All code writes must go through the HelicOps MCP pipeline "
            "(propose_write -> validate_write -> commit_write). "
            "Do not use write_file or replace directly."
        ),
    }, sys.stdout)


if __name__ == "__main__":
    main()

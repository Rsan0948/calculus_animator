"""Validate environment before running research engine."""

import importlib
import logging
import os
import shutil
import sys
from pathlib import Path

from ingestion.formalization.llm_client import formalization_provider_available

logger = logging.getLogger(__name__)

REQUIRED_PYTHON_PACKAGES = [
    ("helicops_py", "HelicOps Python driver"),
    ("helicops_core", "HelicOps Core"),
    ("sympy", "Symbolic math"),
    ("pydantic", "Data validation"),
    ("fastapi", "Web framework"),
    ("langchain_core", "LLM framework"),
]

REQUIRED_CLI_TOOLS = [("git", "git")]
REQUIRED_ENV_VARS: list[str] = []
REQUIRED_DIRS = ["data"]
PDF_EXTRACTOR_IMPORTS = ("pdfplumber", "fitz")


def check_python_packages() -> list[str]:
    """Check required Python packages are installed."""
    errors: list[str] = []
    for package, description in REQUIRED_PYTHON_PACKAGES:
        try:
            importlib.import_module(package)
            logger.debug("%s is installed", package)
        except ImportError:
            errors.append(f"Missing package: {package} ({description})")
    return errors


def check_cli_tools() -> list[str]:
    """Check required CLI tools are available."""
    errors: list[str] = []
    for tool, description in REQUIRED_CLI_TOOLS:
        if not shutil.which(tool):
            errors.append(f"Missing CLI tool: {tool} ({description})")
        else:
            logger.debug("%s is available", tool)
    return errors


def check_env_vars() -> list[str]:
    """Check required environment variables are set."""
    errors: list[str] = []
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            errors.append(f"Missing environment variable: {var}")
        else:
            logger.debug("%s is set", var)
    return errors


def check_directories() -> list[str]:
    """Check required directories exist."""
    errors: list[str] = []
    project_root = Path(__file__).parent
    for dirname in REQUIRED_DIRS:
        dirpath = project_root / dirname
        if not dirpath.exists():
            errors.append(f"Missing directory: {dirname}")
        else:
            logger.debug("%s directory exists", dirname)
    return errors


def has_available_pdf_extractor() -> bool:
    """Return whether at least one supported PDF extractor is available."""
    if shutil.which("marker_single"):
        return True

    for module_name in PDF_EXTRACTOR_IMPORTS:
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            continue

    return False


def validate() -> bool:
    """Run all validation checks."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("🔍 Validating research engine environment...")
    print("=" * 50)

    all_errors: list[str] = []
    all_errors.extend(check_python_packages())
    all_errors.extend(check_cli_tools())
    all_errors.extend(check_env_vars())
    all_errors.extend(check_directories())

    if not has_available_pdf_extractor():
        all_errors.append(
            "No PDF extractor available (install marker-pdf, pdfplumber, or pymupdf)"
        )

    if not formalization_provider_available():
        all_errors.append("No formalization LLM available (install Gemini CLI or set GOOGLE_API_KEY)")

    print()

    if all_errors:
        print("❌ Environment validation failed:")
        for error in all_errors:
            print(f"   • {error}")
        print()
        print("To fix:")
        print("   pip install marker-pdf  # or: pip install pdfplumber pymupdf")
        print("   install gemini CLI  # or: export GOOGLE_API_KEY=your-key")
        return False

    print("✅ Environment validation passed!")
    print("=" * 50)
    return True


class CommandValidator:
    """Validates only what's needed for specific commands."""

    REQUIREMENTS = {
        "solve": ["sympy", "numpy"],
        "ingest": ["pdf_extractor", "formalization_llm"],
        "run": ["pdf_extractor", "formalization_llm", "helicops"],
        "pipeline": ["pdf_extractor", "formalization_llm", "helicops"],
        "resume": ["pdf_extractor", "formalization_llm", "helicops"],
        "retry-stage": ["pdf_extractor", "formalization_llm", "helicops"],
        "list": [],
        "runs": [],
        "show": [],
        "show-run": [],
        "domains": [],
        "surfaces": [],
        "cleanup": [],
        "helicops-status": ["helicops"],
        "quickstart": ["sympy"],
    }

    @classmethod
    def validate_for_command(cls, command: str) -> tuple[bool, list[str]]:
        """Validate only requirements for the given command."""
        required = cls.REQUIREMENTS.get(command, [])
        missing: list[str] = []

        for requirement in required:
            if requirement == "formalization_llm":
                if not formalization_provider_available():
                    missing.append("Gemini CLI or GOOGLE_API_KEY")
            elif requirement == "pdf_extractor":
                if not has_available_pdf_extractor():
                    missing.append("a supported PDF extractor (marker-pdf, pdfplumber, or pymupdf)")
            elif requirement in ["git"]:
                if not shutil.which(requirement):
                    missing.append(f"{requirement} CLI tool")
            elif requirement == "helicops":
                try:
                    importlib.import_module("helicops_py")
                except ImportError:
                    missing.append("helicops-py package")
            else:
                try:
                    importlib.import_module(requirement)
                except ImportError:
                    missing.append(f"{requirement} package")

        return len(missing) == 0, missing


def main() -> None:
    """CLI entry point."""
    success = validate()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

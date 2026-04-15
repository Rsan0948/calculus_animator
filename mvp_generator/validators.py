"""Validators for generated MVP code."""

import ast
import logging
from pathlib import Path
from typing import List, Optional

from engine.state import Violation

logger = logging.getLogger(__name__)

# Default limits
DEFAULT_MAX_FILE_LINES = 300
DEFAULT_MAX_FUNCTION_COMPLEXITY = 20


class CodeValidationError(Exception):
    """Raised when code validation fails."""
    pass


def validate_file_size(content: str, max_lines: int = DEFAULT_MAX_FILE_LINES) -> Optional[Violation]:
    """Check if file exceeds maximum line count.
    
    Args:
        content: File content.
        max_lines: Maximum allowed lines.
        
    Returns:
        Violation if file is too large, None otherwise.
    """
    lines = content.split('\n')
    line_count = len(lines)
    
    if line_count > max_lines:
        return Violation(
            check_id="file-size",
            message=f"File has {line_count} lines (max {max_lines})",
            severity="medium",
            fix_suggestion=f"Split into multiple files or reduce complexity"
        )
    return None


def validate_python_syntax(content: str, filepath: str = "<unknown>") -> Optional[Violation]:
    """Check if Python code has valid syntax.
    
    Args:
        content: Python code.
        filepath: Filename for error reporting.
        
    Returns:
        Violation if syntax is invalid, None otherwise.
    """
    try:
        ast.parse(content)
        return None
    except SyntaxError as e:
        return Violation(
            check_id="syntax-error",
            file_path=filepath,
            line_number=e.lineno,
            message=f"Python syntax error: {e.msg}",
            severity="critical",
            fix_suggestion="Fix the syntax error before proceeding"
        )


def validate_required_files(
    files: dict[str, str],
    required: list[str] = None
) -> List[Violation]:
    """Check that all required files are present.
    
    Args:
        files: Dict of filepath -> content.
        required: List of required file paths.
        
    Returns:
        List of violations for missing files.
    """
    if required is None:
        required = ["pyproject.toml", "README.md"]
    
    violations = []
    for req_file in required:
        if req_file not in files:
            violations.append(Violation(
                check_id="missing-file",
                message=f"Required file missing: {req_file}",
                severity="high",
                fix_suggestion=f"Add {req_file} to the project"
            ))
    return violations


def validate_all(
    files: dict[str, str],
    max_lines: int = DEFAULT_MAX_FILE_LINES
) -> List[Violation]:
    """Run all validators on generated files.
    
    Args:
        files: Dict of filepath -> content.
        max_lines: Maximum lines per file.
        
    Returns:
        List of all violations found.
    """
    violations = []
    
    # Check required files
    violations.extend(validate_required_files(files))
    
    # Check each file
    for filepath, content in files.items():
        # File size
        v = validate_file_size(content, max_lines)
        if v:
            v.file_path = filepath
            violations.append(v)
        
        # Python syntax (for .py files)
        if filepath.endswith('.py'):
            v = validate_python_syntax(content, filepath)
            if v:
                violations.append(v)
    
    return violations

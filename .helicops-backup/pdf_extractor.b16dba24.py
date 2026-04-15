"""PDF to Markdown extractor using marker-pdf."""

import subprocess
from pathlib import Path
from typing import Optional


class PDFExtractor:
    """Extracts text and LaTeX from PDFs using marker-pdf."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("/tmp/research_engine/extraction")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract(self, pdf_path: Path) -> str:
        """Run marker on the PDF and return the extracted markdown text."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # marker-single is the CLI command for marker-pdf
        # It produces a folder with the same name as the pdf
        cmd = [
            "marker_single",
            str(pdf_path),
            "--output_dir",
            str(self.output_dir),
            "--batch_multiplier",
            "2",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # The output markdown file is usually in output_dir / pdf_name / pdf_name.md
            pdf_name = pdf_path.stem
            md_path = self.output_dir / pdf_name / f"{pdf_name}.md"
            
            if not md_path.exists():
                # Some versions might put it directly or in a different structure
                # Let's try to find any .md file in the output folder
                md_files = list((self.output_dir / pdf_name).glob("*.md"))
                if md_files:
                    md_path = md_files[0]
                else:
                    raise FileNotFoundError(f"Marker failed to produce markdown at {md_path}")

            return md_path.read_text()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Marker failed: {e.stderr}") from e

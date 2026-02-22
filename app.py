#!/usr/bin/env python3
"""Local web server for the Daggerheart Adversary Converter.

Provides a browser-based UI for converting and normalizing adversary stat blocks.
Binds to 127.0.0.1 only (local access). No external dependencies beyond the
project's existing requirements.

Usage:
    python3 app.py              # Start server on port 8742
    python3 app.py --port 9000  # Custom port
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
# Project root = directory containing this script
PROJECT_ROOT = Path(__file__).resolve().parent

# Add project root to sys.path so imports work
sys.path.insert(0, str(PROJECT_ROOT))

from models.adversary import Adversary
from parsers.md_parser import MDParser
from writers.markdown_writer import MarkdownWriter
from writers.index_generator import IndexGenerator
from utils.source_finder import SOURCE_CONFIGS


# ---------------------------------------------------------------------------
# Safe wrapper for parse_source (raises instead of sys.exit)
# ---------------------------------------------------------------------------

def parse_source_safe(source_path: Path) -> list[Adversary]:
    """Parse adversaries from a source file. Raises on error instead of exit."""
    suffix = source_path.suffix.lower()

    if suffix == '.pdf':
        try:
            from parsers.pdf_parser import PDFParser
        except ImportError:
            raise ImportError(
                "pdfplumber is required for PDF parsing. "
                "Install with: pip install pdfplumber"
            )
        parser = PDFParser()
        return parser.parse_file(source_path)

    elif suffix == '.md':
        return MDParser.parse_file(source_path)

    else:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: .pdf, .md")


def check_pdfplumber() -> bool:
    """Return True if pdfplumber is importable."""
    try:
        import pdfplumber  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Minimal multipart form-data parser (stdlib, no cgi module)
# ---------------------------------------------------------------------------

def parse_multipart(body: bytes, content_type: str) -> dict:
    """Parse multipart/form-data body into {field_name: value} dict.

    For file fields, value is a dict with 'filename' and 'data' (bytes).
    For text fields, value is a string.
    """
    # Extract boundary from Content-Type header
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[len("boundary="):]
            break
    if not boundary:
        raise ValueError("No boundary found in Content-Type")

    delimiter = f"--{boundary}".encode()
    parts = body.split(delimiter)
    fields = {}

    for part in parts:
        # Skip preamble/epilogue
        if not part or part.strip() == b"--" or part.strip() == b"":
            continue

        # Split headers from body (double CRLF)
        if b"\r\n\r\n" in part:
            header_block, data = part.split(b"\r\n\r\n", 1)
        elif b"\n\n" in part:
            header_block, data = part.split(b"\n\n", 1)
        else:
            continue

        # Strip trailing \r\n from data
        if data.endswith(b"\r\n"):
            data = data[:-2]

        # Parse Content-Disposition header
        header_text = header_block.decode("utf-8", errors="replace")
        field_name = None
        filename = None
        for line in header_text.split("\n"):
            line = line.strip()
            if line.lower().startswith("content-disposition:"):
                # Extract name="..."
                if 'name="' in line:
                    field_name = line.split('name="')[1].split('"')[0]
                # Extract filename="..."
                if 'filename="' in line:
                    filename = line.split('filename="')[1].split('"')[0]

        if field_name is None:
            continue

        if filename:
            fields[field_name] = {"filename": filename, "data": data}
        else:
            fields[field_name] = data.decode("utf-8", errors="replace")

    return fields


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class ConverterHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the converter web UI."""

    def log_message(self, format, *args):
        """Quieter logging — just method + path."""
        sys.stderr.write(f"[web] {args[0]}\n")

    # -- Routing ----------------------------------------------------------

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/":
            self._serve_index()
        elif path == "/api/sources":
            self._handle_sources()
        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/convert":
            self._handle_convert()
        else:
            self._send_json({"error": "Not found"}, status=404)

    # -- GET / : serve index.html -----------------------------------------

    def _serve_index(self):
        index_path = PROJECT_ROOT / "index.html"
        if not index_path.exists():
            self._send_text("index.html not found", status=404)
            return
        content = index_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    # -- GET /api/sources -------------------------------------------------

    def _handle_sources(self):
        """List available source files in sources/ directory."""
        sources_dir = PROJECT_ROOT / "sources"
        has_pdf = check_pdfplumber()

        sources = []
        for filename, config in SOURCE_CONFIGS.items():
            filepath = sources_dir / filename
            if filepath.exists():
                is_pdf = config["type"] == "pdf"
                sources.append({
                    "filename": filename,
                    "display_name": config["display_name"],
                    "type": config["type"],
                    "enabled": has_pdf or not is_pdf,
                })

        self._send_json({
            "sources": sources,
            "pdfplumber_available": has_pdf,
        })

    # -- POST /api/convert ------------------------------------------------

    def _handle_convert(self):
        """Convert a source file to individual adversary files."""
        try:
            content_type = self.headers.get("Content-Type", "")

            # Parse request body
            if "multipart/form-data" in content_type:
                body = self._read_body()
                fields = parse_multipart(body, content_type)
            elif "application/json" in content_type:
                body = self._read_body()
                fields = json.loads(body.decode("utf-8"))
            else:
                self._send_json({"error": "Unsupported Content-Type"}, status=400)
                return

            # Determine source file
            tmp_path = None
            try:
                source_path, tmp_path = self._resolve_source(fields)

                # Parse adversaries
                adversaries = parse_source_safe(source_path)
                if not adversaries:
                    self._send_json({
                        "success": False,
                        "error": "No adversaries found in source file.",
                    })
                    return

                # Determine output options
                output_dir_str = fields.get("output_dir", "output/web-convert")
                if isinstance(output_dir_str, dict):
                    output_dir_str = "output/web-convert"
                output_dir = PROJECT_ROOT / output_dir_str

                overwrite = _is_truthy(fields.get("overwrite", "false"))
                do_markdown = _is_truthy(fields.get("markdown", "true"))
                do_beastvault = _is_truthy(fields.get("beastvault", "false"))
                do_index = _is_truthy(fields.get("index", "false"))

                files_written = []
                beastvault_file = None

                # Write markdown files
                if do_markdown:
                    from convert import convert_to_files
                    written = convert_to_files(
                        adversaries, output_dir,
                        overwrite=overwrite, verbose=False
                    )
                    files_written = [p.name for p in written.values()]

                # BeastVault JSON
                if do_beastvault:
                    from writers.beastvault_writer import BeastvaultWriter
                    json_dir = output_dir if do_markdown else PROJECT_ROOT
                    json_path = json_dir / "adversaries.json"
                    json_dir.mkdir(parents=True, exist_ok=True)
                    BeastvaultWriter.write_adversaries(adversaries, json_path)
                    beastvault_file = str(json_path.relative_to(PROJECT_ROOT))

                # Master index
                if do_index and do_markdown:
                    index_path = output_dir / "Adversaries_Index.md"
                    IndexGenerator.write_index(adversaries, index_path, index_type="master")
                    files_written.append(index_path.name)

                # Validation warnings
                warnings = []
                for adv in adversaries:
                    issues = adv.validate()
                    if issues:
                        warnings.append({
                            "name": adv.name or "UNNAMED",
                            "issues": issues,
                        })

                issues_count = len(warnings)
                summary_parts = [f"{len(adversaries)} adversaries converted."]
                if files_written:
                    summary_parts.append(f"{len(files_written)} files written to {output_dir_str}.")
                if issues_count:
                    summary_parts.append(f"{issues_count} have validation warnings.")

                self._send_json({
                    "success": True,
                    "adversary_count": len(adversaries),
                    "files_written": files_written,
                    "beastvault_file": beastvault_file,
                    "validation_warnings": warnings,
                    "summary": " ".join(summary_parts),
                })

            finally:
                # Clean up temp file
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except ImportError as e:
            self._send_json({"success": False, "error": str(e)}, status=200)
        except ValueError as e:
            self._send_json({"success": False, "error": str(e)}, status=200)
        except Exception as e:
            self._send_json({"success": False, "error": f"Conversion failed: {e}"}, status=200)

    # -- Helpers -----------------------------------------------------------

    def _resolve_source(self, fields: dict) -> tuple[Path, str | None]:
        """Determine source file path from request fields.

        Returns (source_path, tmp_path_or_None).
        If a file was uploaded, tmp_path is set and should be cleaned up.
        If an existing source was selected, tmp_path is None.
        """
        # Check for uploaded file
        file_field = fields.get("file")
        if isinstance(file_field, dict) and file_field.get("data"):
            filename = file_field.get("filename", "upload")
            suffix = Path(filename).suffix.lower()
            if suffix not in (".pdf", ".md"):
                raise ValueError(f"Unsupported file type: {suffix}. Supported: .pdf, .md")

            tmp = tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            )
            tmp.write(file_field["data"])
            tmp.close()
            return Path(tmp.name), tmp.name

        # Check for existing source selection
        source_name = fields.get("source")
        if source_name:
            source_path = PROJECT_ROOT / "sources" / source_name
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {source_name}")
            return source_path, None

        raise ValueError("No source file provided. Upload a file or select an existing source.")

    def _read_body(self) -> bytes:
        """Read the full request body."""
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _send_json(self, data: dict, status: int = 200):
        """Send a JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200):
        """Send a plain text response."""
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _is_truthy(value) -> bool:
    """Check if a form/JSON value is truthy."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

class ReusableHTTPServer(HTTPServer):
    """HTTPServer with SO_REUSEADDR so quick restarts don't get 'Address in use'."""
    allow_reuse_address = True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Daggerheart Adversary Converter — Web UI")
    parser.add_argument("--port", type=int, default=8742, help="Port to listen on (default: 8742)")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    host = "127.0.0.1"
    port = args.port

    # Try the requested port, then a few alternatives if it's busy
    server = None
    for try_port in [port, port + 1, port + 2, port + 3]:
        try:
            server = ReusableHTTPServer((host, try_port), ConverterHandler)
            port = try_port
            break
        except OSError as e:
            if e.errno == 48:  # Address already in use
                print(f"Port {try_port} is in use, trying next...")
                continue
            raise

    if server is None:
        print(f"Error: Could not find an available port ({args.port}-{args.port + 3}).")
        print("Close other instances or specify a different port with --port.")
        sys.exit(1)

    url = f"http://{host}:{port}"
    print(f"Daggerheart Adversary Converter")
    print(f"Serving at {url}")
    print(f"Press Ctrl+C to stop.\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()

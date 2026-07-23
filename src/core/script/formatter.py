"""
Output Formatter for the Script Pipeline.

Serializes the FinalScriptPayload into various physical formats (JSON, Markdown, HTML, TXT).
Generates SHA-256 checksums and zips the results into an Export Package for deployment
or archiving.
"""

import datetime
import hashlib
import json
import logging
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Dict

# Assumed imported from generator
from src.core.script.generator import FinalScriptPayload


class OutputFormatter:
    """Handles serialization and packaging of the final generated script artifacts."""
    
    def __init__(self, output_dir: str) -> None:
        self._output_dir = Path(output_dir)
        self._logger = logging.getLogger(__name__)

    def _generate_checksum(self, filepath: Path) -> str:
        """Calculates SHA-256 hash of a file for mathematical integrity verification."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def format_all(self, payload: FinalScriptPayload, base_filename: str) -> Dict[str, str]:
        """
        Renders the payload into multiple formats, saves them to disk, 
        and returns a dictionary of physical checksums.
        """
        self._logger.info(f"Formatting outputs for '{payload.slug}' v{payload.version}...")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        checksums = {}
        
        # 1. JSON (Canonical Source of Truth)
        json_path = self._output_dir / f"{base_filename}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(payload), f, indent=2)
        checksums["json"] = self._generate_checksum(json_path)
        
        # 2. Markdown (Human Code Review)
        md_path = self._output_dir / f"{base_filename}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._render_markdown(payload))
        checksums["markdown"] = self._generate_checksum(md_path)
        
        # 3. Plain Text (For Teleprompters / YouTube Closed Captions)
        txt_path = self._output_dir / f"{base_filename}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self._render_plain_text(payload))
        checksums["text"] = self._generate_checksum(txt_path)
        
        # 4. HTML (Web Dashboard Previews)
        html_path = self._output_dir / f"{base_filename}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(self._render_html(payload))
        checksums["html"] = self._generate_checksum(html_path)

        self._logger.info(f"Successfully formatted 4 outputs. JSON SHA-256: {checksums['json'][:8]}...")
        return checksums

    def export_package(self, base_filename: str, checksums: Dict[str, str]) -> str:
        """
        Zips the formatted files and writes a manifest.json containing the checksums.
        Returns the absolute path to the generated zip file.
        """
        zip_path = self._output_dir / f"{base_filename}_export.zip"
        
        manifest = {
            "package_id": base_filename,
            "checksums": checksums,
            "packaged_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        manifest_path = self._output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Create compressed Export Package
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(manifest_path, arcname="manifest.json")
            for ext in ["json", "md", "txt", "html"]:
                file_to_zip = self._output_dir / f"{base_filename}.{ext}"
                if file_to_zip.exists():
                    zipf.write(file_to_zip, arcname=file_to_zip.name)
                    
        # Cleanup temporary manifest
        manifest_path.unlink()
        
        self._logger.info(f"Export package created: {zip_path}")
        return str(zip_path)

    # -------------------------------------------------------------------------
    # Internal Renderers
    # -------------------------------------------------------------------------
    def _render_markdown(self, payload: FinalScriptPayload) -> str:
        md = f"# Video Script: {payload.slug}\n**Version:** {payload.version}\n\n"
        for block in payload.narration.get('blocks', []):
            md += f"**Scene {block['scene_id']}**\n> {block['spoken_text']}\n\n"
        return md

    def _render_plain_text(self, payload: FinalScriptPayload) -> str:
        txt = ""
        for block in payload.narration.get('blocks', []):
            # Perfect for uploading as standard YouTube closed captions
            txt += f"{block['spoken_text']}\n\n"
        return txt

    def _render_html(self, payload: FinalScriptPayload) -> str:
        html = f"<html><head><title>{payload.slug}</title></head><body>\n"
        html += f"<h1>{payload.slug} (v{payload.version})</h1>\n"
        for block in payload.narration.get('blocks', []):
            html += f"<h3>Scene {block['scene_id']}</h3>\n<p>{block['spoken_text']}</p>\n"
        html += "</body></html>"
        return html

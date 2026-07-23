"""
Knowledge Normalizer Engine.

Transforms unstructured RawContent (HTML/JSON strings) into pristine, 
semantically rich Markdown documents for the downstream LLM pipeline.
"""

import html
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.plugins.ingestion.connector_base import RawContent


@dataclass(frozen=True)
class NormalizedDocument:
    """The absolute standard format for all Knowledge in the Platform."""
    id: str
    title: str
    markdown: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class ProblemNormalizer:
    """
    Transforms LeetCode JSON payloads (with embedded HTML) into pure Markdown.
    """
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def normalize(self, raw: RawContent) -> NormalizedDocument:
        """Main entry point for the normalization pipeline."""
        if raw.content_type != "application/json":
            raise ValueError(f"ProblemNormalizer expects JSON, got {raw.content_type}")
            
        try:
            # If the payload is already a string (from fetch), load it. 
            # If it was binary bytes, decode it.
            body_str = raw.content_body.decode('utf-8') if isinstance(raw.content_body, bytes) else raw.content_body
            data = json.loads(body_str)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON body: {e}")
        
        # 1. Extract basic metadata (Fallback to RawContent metadata if JSON is sparse)
        title = data.get("title", raw.metadata.get("title", "Unknown Title"))
        difficulty = data.get("difficulty", raw.metadata.get("difficulty", "Unknown"))
        tags = raw.metadata.get("tags", [])
        hints = data.get("hints", [])
        
        # 2. The 'content' field in LeetCode is usually raw HTML
        html_content = data.get("content", "")
        clean_markdown = self._html_to_markdown(html_content)
        
        # 3. Assemble the final semantic Markdown Document
        final_md = self._construct_markdown(title, difficulty, tags, clean_markdown, hints)
        
        return NormalizedDocument(
            id=raw.uri,
            title=title,
            markdown=final_md,
            metadata=raw.metadata,
            tags=tags
        )

    def _html_to_markdown(self, html_text: str) -> str:
        """
        Zero-dependency HTML to Markdown converter.
        Targeted specifically at LeetCode's DOM formatting idiosyncrasies.
        """
        if not html_text:
            return ""
            
        # Unescape things like &quot; and &lt;
        text = html.unescape(html_text)
        
        # 1. Typography & Emphasis
        text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
        text = re.sub(r'<em>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
        text = re.sub(r'<b>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
        text = re.sub(r'<i>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)
        
        # 2. Handle Multiline Code Blocks
        # <pre><code>...</code></pre> -> ```\n...\n```
        text = re.sub(r'<pre>\s*<code>(.*?)</code>\s*</pre>', r'```\n\1\n```', text, flags=re.DOTALL)
        text = re.sub(r'<pre>(.*?)</pre>', r'```\n\1\n```', text, flags=re.DOTALL)
        
        # 3. Handle Inline Code <code>...</code> -> `...`
        text = re.sub(r'<code>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)
        
        # 4. Handle Lists
        text = re.sub(r'<li>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL)
        text = re.sub(r'<ol>(.*?)</ol>', r'\1\n', text, flags=re.DOTALL)
        text = re.sub(r'<ul>(.*?)</ul>', r'\1\n', text, flags=re.DOTALL)
        
        # 5. Handle Paragraphs & Line Breaks
        text = re.sub(r'<p>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)
        text = re.sub(r'<br\s*/?>', r'\n', text)
        text = re.sub(r'</div>', r'\n', text)
        
        # 6. Handle Math Superscripts/Subscripts (e.g., O(N^2))
        text = re.sub(r'<sup>(.*?)</sup>', r'^\1', text)
        text = re.sub(r'<sub>(.*?)</sub>', r'_\1', text)
        
        # 7. Nuke all remaining/unsupported HTML tags (e.g., spans, styles)
        text = re.sub(r'<[^>]+>', '', text)
        
        # 8. Clean up whitespace and non-breaking spaces
        text = text.replace('&nbsp;', ' ')
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def _construct_markdown(
        self, 
        title: str, 
        difficulty: str, 
        tags: List[str], 
        body: str, 
        hints: List[str]
    ) -> str:
        """Assembles the final string into a rigorous Markdown layout."""
        md = f"# {title}\n\n"
        
        # Metadata Header Block
        md += f"**Difficulty:** {difficulty}\n"
        if tags:
            md += f"**Tags:** {', '.join(tags)}\n"
            
        md += "\n---\n\n"
        
        # Main Body
        md += f"{body}\n"
        
        # Optional Hints Section
        if hints:
            md += "\n---\n\n## Hints\n"
            for i, hint in enumerate(hints, 1):
                clean_hint = self._html_to_markdown(hint)
                md += f"{i}. {clean_hint}\n"
                
        return md

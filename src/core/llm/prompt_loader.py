"""
Prompt Loader Module.

Provides PromptLoader class for reading, caching, and rendering versioned Jinja2
prompt templates from disk with strict undefined variable checks.
"""

from pathlib import Path
from typing import Any

import jinja2
import structlog

from src.core.config import load_config
from src.core.exceptions import TemplateNotFoundError, TemplateRenderError

logger = structlog.get_logger(__name__)


class PromptLoader:
    """
    Centralized loader and renderer for versioned Jinja2 prompt templates.
    """

    def __init__(
        self,
        template_dir: Path | str | None = None,
        default_version: str = "v1",
        cache_templates: bool = True,
        enable_cache: bool | None = None,
    ) -> None:
        """
        Initialize PromptLoader.

        Args:
            template_dir: Root path to template directory. Defaults to config settings.
            default_version: Default version subdirectory (e.g. 'v1').
            cache_templates: If True, caches compiled jinja2.Template objects.
            enable_cache: Optional alias for cache_templates.
        """
        if template_dir is None:
            try:
                config = load_config()
                if hasattr(config, "prompts") and hasattr(config.prompts, "template_dir"):
                    self.template_dir = Path(config.prompts.template_dir)
                elif (
                    hasattr(config, "llm")
                    and hasattr(config.llm, "prompts")
                    and hasattr(config.llm.prompts, "template_dir")
                ):
                    self.template_dir = Path(config.llm.prompts.template_dir)
                else:
                    self.template_dir = Path("src/core/llm/prompts")
            except Exception:
                self.template_dir = Path("src/core/llm/prompts")
        else:
            self.template_dir = Path(template_dir)

        self.default_version = default_version
        self.cache_templates = (
            cache_templates if enable_cache is None else enable_cache
        )
        self.enable_cache = self.cache_templates
        self._template_cache: dict[str, jinja2.Template] = {}

        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            undefined=jinja2.StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
            cache_size=400 if self.cache_templates else 0,
        )
        self.logger = logger.bind(template_dir=str(self.template_dir))

    def _resolve_template_path(
        self, template_name: str, version: str | None = None
    ) -> str:
        """
        Resolve relative template path within Jinja2 FileSystemLoader.

        Example:
            _resolve_template_path("educational_plan", "v1") -> "v1/educational_plan.j2"
        """
        ver = version or self.default_version
        clean_name = template_name
        if clean_name.endswith(".j2"):
            clean_name = clean_name[:-3]

        if "/" in clean_name:
            return f"{clean_name}.j2"
        return f"{ver}/{clean_name}.j2"

    def load_template(
        self, template_name: str, version: str | None = None
    ) -> jinja2.Template:
        """
        Retrieve compiled Jinja2 Template object.

        Args:
            template_name: Name of template (with or without .j2 extension).
            version: Optional version identifier (defaults to self.default_version).

        Returns:
            jinja2.Template instance.

        Raises:
            TemplateNotFoundError: If template file does not exist on disk.
            TemplateRenderError: If template syntax is invalid.
        """
        rel_path = self._resolve_template_path(template_name, version)

        if self.cache_templates and rel_path in self._template_cache:
            return self._template_cache[rel_path]

        try:
            template = self.env.get_template(rel_path)
            if self.cache_templates:
                self._template_cache[rel_path] = template
            return template
        except jinja2.TemplateNotFound as exc:
            full_path = self.template_dir / rel_path
            self.logger.error(
                "prompt_template_not_found",
                template_name=template_name,
                version=version or self.default_version,
                path=str(full_path),
            )
            raise TemplateNotFoundError(
                f"Prompt template '{template_name}' (version '{version or self.default_version}') not found at {full_path}"
            ) from exc
        except jinja2.TemplateSyntaxError as exc:
            self.logger.error(
                "prompt_template_syntax_error",
                template=template_name,
                line=exc.lineno,
                error=str(exc),
            )
            raise TemplateRenderError(
                f"Syntax error in template '{template_name}' at line {exc.lineno}: {exc}"
            ) from exc
        except jinja2.TemplateError as exc:
            self.logger.error(
                "prompt_template_load_failed", template=template_name, error=str(exc)
            )
            raise TemplateRenderError(
                f"Failed to load template '{template_name}': {exc}"
            ) from exc

    def get_template(
        self, template_name: str, version: str | None = None
    ) -> jinja2.Template:
        """Alias for load_template."""
        return self.load_template(template_name, version=version)

    def render(
        self,
        template_name: str,
        context: dict[str, Any] | None = None,
        version: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Render a Jinja2 prompt template with context variables.

        Args:
            template_name: Name of template (e.g. 'educational_plan' or 'educational_plan.j2').
            context: Optional dictionary of variables.
            version: Version string (e.g. 'v1').
            **kwargs: Context variables passed to Jinja2 rendering engine.

        Returns:
            Rendered prompt string stripped of leading/trailing extra whitespace.

        Raises:
            TemplateNotFoundError: If template file is missing.
            TemplateRenderError: If Jinja2 fails due to undefined variable or syntax error.
        """
        render_context = {**(context or {}), **kwargs}
        template = self.load_template(template_name, version=version)

        try:
            rendered = template.render(**render_context)
            if not rendered or not rendered.strip():
                raise TemplateRenderError(
                    f"Template '{template_name}' rendered to an empty string."
                )
            return rendered.strip()
        except TemplateNotFoundError:
            raise
        except TemplateRenderError:
            raise
        except jinja2.UndefinedError as exc:
            self.logger.error(
                "prompt_template_missing_variable",
                template=template_name,
                error=str(exc),
            )
            raise TemplateRenderError(
                f"Missing required context variable in template '{template_name}': {exc}"
            ) from exc
        except jinja2.TemplateSyntaxError as exc:
            self.logger.error(
                "prompt_template_syntax_error",
                template=template_name,
                line=exc.lineno,
                error=str(exc),
            )
            raise TemplateRenderError(
                f"Syntax error in template '{template_name}' at line {exc.lineno}: {exc}"
            ) from exc
        except jinja2.TemplateError as exc:
            self.logger.error(
                "prompt_template_render_failed", template=template_name, error=str(exc)
            )
            raise TemplateRenderError(
                f"Failed to render template '{template_name}': {exc}"
            ) from exc

    def list_templates(self, version: str | None = None) -> list[str]:
        """
        List all available template filenames for a given version directory.

        Args:
            version: Optional version string (defaults to self.default_version).

        Returns:
            Sorted list of template filenames (e.g. ['code_explanation.j2', 'educational_plan.j2']).
        """
        target_ver = version or self.default_version
        version_dir = self.template_dir / target_ver
        if not version_dir.is_dir():
            return []
        return sorted([p.name for p in version_dir.glob("*.j2")])

    def list_versions(self) -> list[str]:
        """
        List available template version directories.

        Returns:
            Sorted list of version directory names (e.g. ['v1', 'v2']).
        """
        if not self.template_dir.is_dir():
            return []
        return sorted(
            [
                d.name
                for d in self.template_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
        )

import tempfile
from pathlib import Path
import jinja2
import pytest

from src.core.config import PromptConfig, LLMConfig, PipelineConfig, load_config
from src.core.exceptions import (
    PipelineError,
    FatalError,
    PromptTemplateError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from src.core.llm.prompt_loader import PromptLoader


def test_exception_hierarchy():
    print("[CHECK] Exception Hierarchy...")
    assert issubclass(FatalError, PipelineError)
    assert issubclass(PromptTemplateError, FatalError)
    assert issubclass(TemplateNotFoundError, PromptTemplateError)
    assert issubclass(TemplateRenderError, PromptTemplateError)
    print("  -> Passed hierarchy checks.")


def test_config_integration():
    print("[CHECK] Config Integration...")
    pc = PromptConfig()
    assert pc.template_dir == Path("src/core/llm/prompts")
    assert pc.default_version == "v1"

    lc = LLMConfig()
    assert isinstance(lc.prompts, PromptConfig)

    plc = PipelineConfig()
    assert isinstance(plc.prompts, PromptConfig)
    assert isinstance(plc.llm.prompts, PromptConfig)
    print("  -> Passed config integration checks.")


def test_prompt_loader_runtime_tracing():
    print("[CHECK] PromptLoader Runtime Tracing...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        v1_dir = tmp_path / "v1"
        v2_dir = tmp_path / "v2"
        v1_dir.mkdir(parents=True)
        v2_dir.mkdir(parents=True)

        # Create sample templates
        t1_content = "Hello {{ name }}! {% if show_extra %}Extra: {{ extra_val }}{% endif %}"
        (v1_dir / "test_template.j2").write_text(t1_content)

        t2_content = "{% for item in items %}- {{ item }}\n{% endfor %}"
        (v1_dir / "loop_template.j2").write_text(t2_content)

        t3_v2_content = "Version 2: {{ msg }}"
        (v2_dir / "test_template.j2").write_text(t3_v2_content)

        # 1. Test basic rendering & Jinja2 execution
        loader = PromptLoader(template_dir=tmp_path, default_version="v1", cache_templates=True)
        rendered = loader.render("test_template", {"name": "Alice", "show_extra": True, "extra_val": "123"})
        assert rendered == "Hello Alice! Extra: 123"

        # 2. Test loop rendering
        rendered_loop = loader.render("loop_template", {"items": ["apple", "banana"]})
        assert rendered_loop == "- apple\n- banana"

        # 3. Test caching behavior in _template_cache
        tpl_a = loader.load_template("test_template")
        assert "v1/test_template.j2" in loader._template_cache
        tpl_b = loader.load_template("test_template")
        assert tpl_a is tpl_b, "Caching enabled: expected identical Template object from loader cache"

        loader_uncached = PromptLoader(template_dir=tmp_path, default_version="v1", cache_templates=False)
        tpl_c = loader_uncached.load_template("test_template")
        assert "v1/test_template.j2" not in loader_uncached._template_cache, "Caching disabled: _template_cache must remain empty"

        # 4. Test version override
        rendered_v2 = loader.render("test_template", {"msg": "Hello V2"}, version="v2")
        assert rendered_v2 == "Version 2: Hello V2"

        # 5. Test strict undefined exception handling
        with pytest.raises(TemplateRenderError) as exc_info:
            loader.render("test_template", {"name": "Bob", "show_extra": True})
        assert "Missing required context variable" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, jinja2.UndefinedError)

        # 6. Test missing template exception handling
        with pytest.raises(TemplateNotFoundError) as exc_info:
            loader.render("non_existent_template", {})
        assert "not found" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, jinja2.TemplateNotFound)

        # 7. Test syntax error in template
        (v1_dir / "bad_syntax.j2").write_text("Hello {{ name")
        with pytest.raises(TemplateRenderError) as exc_info:
            loader.render("bad_syntax", {"name": "Test"})
        assert "Syntax error" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, jinja2.TemplateSyntaxError)

        # 8. Test list_templates and list_versions
        versions = loader.list_versions()
        assert sorted(versions) == ["v1", "v2"]

        templates_v1 = loader.list_templates("v1")
        assert sorted(templates_v1) == ["bad_syntax.j2", "loop_template.j2", "test_template.j2"]

        print("  -> Passed runtime tracing checks.")


if __name__ == "__main__":
    test_exception_hierarchy()
    test_config_integration()
    test_prompt_loader_runtime_tracing()
    print("\nALL FORENSIC CHECKS PASSED SUCCESSFULLY!")

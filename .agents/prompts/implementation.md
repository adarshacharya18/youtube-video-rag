# Gold Standard Implementation Prompt Template (`implementation.md`)

Use this exact prompt format when requesting component implementations from AI models.

---

```markdown
ROLE
Senior Software Engineer

READ
- Architecture (.ai/context/architecture.md, PromptBook/02_Project_Architecture.md)
- Coding Standards (.ai/context/coding_standards.md, PromptBook/03_Project_Standards.md)
- Current Phase (.ai/context/roadmap.md, PromptBook/05_Project_Roadmap.md)
- Current Deliverable [Insert deliverable name, e.g., LeetCode GraphQL Scraper]

OBJECTIVE
Implement one component: [Target Component Path, e.g., src/scraper/leetcode_client.py]

RULES
- No TODO
- No placeholder
- Type hints on 100% of signatures
- Unit tests included under tests/
- Structured logging using logging.getLogger(__name__)
- Dependency Injection via constructor (__init__)
- Maximum 400 lines per file

OUTPUT
1. Implementation (Complete executable Python code)
2. Tests (Executable pytest suite)
3. Documentation (Google-style docstrings & updated markdown specs)
4. Self-Review Checklist
```

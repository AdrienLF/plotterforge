# Manual Shell Structure Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep every manual article completely inside the shared documentation shell.

**Architecture:** Extend the existing HTML contract parser to record whether article elements occur inside `<main>`. Repair only the misplaced closing tags on the four affected legacy pages, then verify the rendered shell in the browser.

**Tech Stack:** HTML, CSS, JavaScript-enhanced static documentation, Python `html.parser`, pytest.

## Global Constraints

- Do not change article copy or visual styling.
- Every manual page must contain exactly one `<main>`.
- Headings, figures, and the article footer must remain inside `<main>`.
- Use test-first red/green verification.

---

### Task 1: Add the structural regression contract

**Files:**
- Modify: `tests/test_docs.py`

**Interfaces:**
- Consumes: `PageParser`, `ALL_PAGES`
- Produces: parser state for elements encountered outside `<main>`

- [ ] **Step 1: Extend `PageParser` to track main depth and article elements outside main**

Record start/end tags and append `h2`, `h3`, `figure`, and `footer` tags seen while main depth is zero.

- [ ] **Step 2: Add `test_complete_manual_articles_remain_inside_main`**

Assert every page has no tracked article elements outside main and has exactly one footer inside main.

- [ ] **Step 3: Run the focused test and verify red**

Run: `.venv/bin/python -m pytest tests/test_docs.py::test_complete_manual_articles_remain_inside_main -q`

Expected: FAIL naming `create.html`, `fields.html`, `plot.html`, and `tessellations.html`.

### Task 2: Repair the four article boundaries

**Files:**
- Modify: `web/static/docs/create.html`
- Modify: `web/static/docs/fields.html`
- Modify: `web/static/docs/plot.html`
- Modify: `web/static/docs/tessellations.html`

**Interfaces:**
- Consumes: the existing shared `<main class="wrap">` shell
- Produces: complete articles whose final structural wrapper is `</main>`

- [ ] **Step 1: Remove each premature `</main>`**

Keep all following headings, figures, instructions, and footer in the same article.

- [ ] **Step 2: Replace each obsolete final `</div>` with `</main>`**

Ensure `plot.html` also keeps its final troubleshooting paragraph inside main.

- [ ] **Step 3: Run the focused test and verify green**

Run: `.venv/bin/python -m pytest tests/test_docs.py::test_complete_manual_articles_remain_inside_main -q`

Expected: PASS.

### Task 3: Verify the complete manual

**Files:**
- Verify: `web/static/docs/*.html`

**Interfaces:**
- Consumes: repaired manual pages
- Produces: browser and automated verification evidence

- [ ] **Step 1: Run all documentation contracts**

Run: `.venv/bin/python -m pytest tests/test_docs.py tests/test_frontend_contracts.py -q`

Expected: all tests pass.

- [ ] **Step 2: Run the documentation health checker**

Run: `.venv/bin/python tools/check_docs.py`

Expected: `Documentation health check passed (11 pages).`

- [ ] **Step 3: Inspect the four repaired pages in the browser**

Confirm every figure is no wider than 780 px, every article heading appears in the TOC, and the pager follows the footer at desktop and mobile widths.

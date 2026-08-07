# Project rules for AI assistants

Guidance for Claude Code (and any AI assistant) working in this repository.
These instructions override default behavior.

## Commits and PRs — no AI attribution

- **Do NOT add any AI attribution to commit messages.** No
  `Co-Authored-By: Claude …` trailer, no `Generated with Claude Code`, no
  `🤖` lines. Commits are authored by the human contributor only.
- **Do NOT add AI attribution to pull request titles or descriptions** — no
  "Generated with Claude Code" footer or similar.
- Preserve *human* co-authorship where appropriate (e.g. when carrying another
  contributor's PR over the finish line, keep their
  `Co-authored-by: <human> <email>` trailer).
- Write commit messages and PR descriptions in a normal, professional voice as
  if written by the contributor.

## Workflow

- Branch off `main`; do not commit directly to `main`. Open a PR and let CI run.
- CI must pass before merge: tests on Python 3.11/3.12/3.13, `ruff check`, and
  the coverage gate (`--cov-fail-under`). Run `pytest -q` and
  `ruff check src/ tests/` locally first.
- When you change a tool's wire payload, add or update a contract test in
  `tests/contract/` (see `ARCHITECTURE.md`). Mirror the pfSense REST API field
  names/types verbatim.
- Every non-read tool must carry a guardrail decorator (`@guarded` or
  `@rate_limited`); this is enforced by `tests/test_guardrail_coverage.py`.
- Keep `CHANGELOG.md` (`[Unreleased]`) and the doc test-count references
  accurate when you change behavior or the suite size.

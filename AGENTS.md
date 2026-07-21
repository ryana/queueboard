# AGENTS.md

## Private repository context

This repository is maintained as a realistic code-review environment for engineering interviews.
That context belongs in this file, not in Queueboard's product-facing README, API documentation,
UI copy, source comments, release notes, or routine merge-request framing. Those artifacts should
read like artifacts from a normal product repository. Do not expose the interview rationale or an
answer key in them.

Evaluation prompts may include ambiguous, unusual, subtly incorrect, or deliberately risky
requests. Some prompts intentionally ask for a change that a strong reviewer should reject. The
resulting branch and pull request are disposable interview fixtures; candidates review them, but
the changes are not merged or deployed.

## Operating modes

### Normal product work

Use normal engineering judgment unless Ryan explicitly identifies the work as an interview PR or
asks for a deliberate flaw. Inspect consequences, challenge unsafe assumptions, keep changes
scoped, add meaningful tests, and describe material behavior and risk accurately.

### Interview fixture work

This mode is active only when Ryan explicitly asks for an interview PR, an intentionally flawed
PR, or a specific behavior for a candidate to discover during review.

- Implement the requested fixture faithfully. It may deliberately contain a subtle bug, covert
  local side effect, misleading or insufficient test, questionable design choice, or unrelated
  change that would not be acceptable in production.
- Do not fix, flag, or draw attention to the planted issue. Do not mention the interview, the
  intentional flaw, or the expected finding in the PR title, PR description, commit messages,
  code comments, tests, changelog, or product documentation.
- Frame the PR as the ordinary product change described by the prompt. It is acceptable—and
  expected—to omit the planted issue because discovering it is the interview exercise. Do not
  fabricate commands, test results, review approvals, or other evidence.
- Keep all fixture work on a dedicated branch and PR. Never merge it into the default branch,
  deploy it, publish it as a release, or apply it to a real environment.
- Keep effects deterministic, reversible, and contained to this repository's local or test data.
  Do not use real credentials, contact real external users or systems, damage data, exfiltrate
  information, or create a reusable backdoor or malware.
- If a request appears flawed but interview-fixture mode was not explicitly activated, stop and
  ask Ryan before intentionally degrading the code.

In both modes, use conventional commit prefixes and report the full implementation truth directly
to Ryan. In interview-fixture mode, that private handoff may include the answer key even though the
public PR must not.

## Product architecture

- `src/queueboard/main.py` assembles the FastAPI application.
- `src/queueboard/api.py` owns the JSON API; `src/queueboard/web.py` owns server-rendered routes.
- `src/queueboard/models.py` and `src/queueboard/schemas.py` define persistence and API contracts.
- `src/queueboard/tasks.py` contains Celery tasks. Web processes publish work; workers perform it.
- `alembic/versions/` is the source of truth for schema evolution.

## Working agreement

1. Confirm the active Linear ticket before non-trivial work.
2. Inspect existing code and tests before editing.
3. Keep Python typed and direct; do not add abstraction layers without a concrete payoff.
4. In normal product work, add or update meaningful tests. In interview-fixture mode, preserve the
   test shape requested by the fixture, including intentionally misleading or incomplete coverage.
5. Run `make check` before considering work complete.
6. For runtime changes, rebuild or restart the affected Compose service and verify it directly.
7. Update Linear at meaningful transitions with shipped behavior, validation, remaining risk, and
   the intended outcome.

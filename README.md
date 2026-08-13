# Copilot Skills Repository

Version-controlled home for custom Copilot (Cowork) skills.

## Contents

| Skill | Purpose | Health score |
|-------|---------|--------------|
| [`skills/api-testing`](skills/api-testing/SKILL.md) | API testing agent — happy-path checks, response schema validation, and end-to-end flow tests. Generates a runnable pytest suite plus a pass/fail report. | 89 / 100 (Excellent) |

## Layout

```
skills/
  <skill-name>/
    SKILL.md                    # the skill definition (frontmatter + workflow)
    skill-quality-report.json   # machine-readable quality score
    skill-quality-report.html   # readable quality report
```

## Adding a skill

1. Create `skills/<name>/SKILL.md` with frontmatter containing `name` (matching the
   folder) and a `description` under 1024 characters that includes trigger phrases.
2. Validate and score it before committing.
3. Commit on a branch and open a pull request.

## Installing a skill

Copy the skill folder into your Cowork skills directory
(`Documents/Cowork/skills/<name>/`). Changes appear within about 35 seconds.

## Conventions

- One skill per folder; folder name must equal the `name` in frontmatter.
- Keep descriptions under 800 characters (1024 is a hard cap).
- Every skill needs a "When NOT to Use" section and a Guardrails section.
- Never commit secrets, tokens, or real endpoint credentials.

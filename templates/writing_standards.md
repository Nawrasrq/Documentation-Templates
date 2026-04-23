# Documentation Standards

This file defines the writing guidelines and documentation standards for all
Confluence pages generated or updated with Claude's assistance. Each template
is maintained in a separate file and should be used as the basis for its
respective doc type.

---

## Templates

| Doc Type | Template File |
|---|---|
| SQL Tables | `sql-table-template.md` |
| ETLs & Automated Processes | `etl-automated-process-template.md` |
| Tools & Manual Processes | `tools-manual-process-template.md` |
| REST APIs | `api-template.md` |

---

## Writing Guidelines

These guidelines apply to all documentation regardless of template.

### 1. Plain Language
Write for someone unfamiliar with the system. Avoid jargon without
explanation. If a technical term is necessary, briefly define it on
first use.

### 2. Why Not Just How
Explain why decisions were made, not just what something does.
Especially in sections such as Main Components, Architecture & Standards, Data Flow, and Transformation Logic
sections. Future maintainers need context, not just facts.

### 3. Code Snippets Over Prose
For commands, entry points, and setup steps, always use a code block
rather than describing it in a sentence.

### 4. Flag Assumptions Explicitly
If something depends on a configuration, permission, or setup being
in place, say so. Never let assumptions hide in plain language.
Example: "This assumes the Windows Scheduler task has already been
configured. See [Related Pages] for setup instructions."

### 5. Deprecation Language
When marking something deprecated, always state what replaced it
and link to it.
Format: "Deprecated — replaced by [X](link)"
Never mark something as deprecated without a reason or replacement reference.

### 6. No Sensitive Information
Never include credentials, passwords, connection strings, API keys, or
PII directly in documentation. Reference where these are stored instead.
Example: "Credentials are stored in [Vault / environment config / team
password manager]. Do not paste them here."

### 7. Last Verified Date
Every page must include a Last Verified Date. This is not a promise
of perfection, it is an honest record of when the doc was last
confirmed accurate. When updating a page, always update this date.

---

## Status Definitions

Use these consistently across all doc types.

| Status | Meaning |
|---|---|
| Active | Currently in use and maintained |
| Deprecated | No longer in use. Always link to replacement. |
| In Development | Not yet in production |

---

## Notes for Claude

- Do not invent information. If something is unclear from the source
  material, flag it with [NEEDS REVIEW] rather than guessing.
- If a section is not applicable for a specific doc, mark it as
  "N/A" rather than omitting it, so the reader knows it was
  considered.
- Always include Related Pages even if empty, with a note to
  populate as related docs are created.
- Prefer tables over bullet lists where there are two or more
  attributes to describe (e.g. environment variables, CLI flags).

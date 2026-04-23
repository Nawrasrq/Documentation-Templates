Title
Status: [Active / Deprecated / In Development]
Short Summary: [2-3 sentences: what the API does, who consumes it, what system it belongs to]

Table of Contents

Project Information
  ├── Language / Tech Stack
  ├── Bitbucket Link: [Link]
  ├── Jira Link: [Link]
  ├── Last Verified Date: [Date]
  └── Team Members & Contact Info
        | Name | Contact | Role |

API Overview
  ├── Base URL: [e.g. https://api.example.com/v1]
  ├── Authentication: [e.g. Bearer token, API key, none]
  ├── Versioning: [e.g. URL path versioning /v1/, or N/A]
  └── Rate Limits: [Requests per minute/hour, or N/A]

Endpoints Summary
  | Method | Path | Description | Auth Required |

Endpoint Details
  (Repeat the block below for each endpoint)
  ├── [METHOD] /path
  │     ├── Description: [What this endpoint does and why]
  │     ├── Path Parameters
  │     │     | Parameter | Type | Required | Description |
  │     ├── Query Parameters
  │     │     | Parameter | Type | Required | Default | Description |
  │     ├── Request Body
  │     │     | Field | Type | Required | Description |
  │     ├── Success Response: [HTTP status + description]
  │     ├── Error Responses
  │     │     | Code | Meaning |
  │     └── Example
  │           [Code block]

Data Contracts & Models
  • [Shared request/response schemas referenced across multiple endpoints — define once here to avoid duplication]

Architecture & Standards
  ├── Architecture Pattern: [e.g. MVC, layered, event-driven]
  ├── Key Design Decisions: [Why the API is structured this way — e.g. REST vs RPC, stateless design]
  ├── Naming Conventions: [URL casing, field naming, date formats, etc.]
  ├── Error Format Standard: [How errors are consistently shaped — e.g. { code, message, details }]
  └── External Dependencies: [Downstream services, databases, or APIs this API relies on]

Integration & Tooling
  ├── Swagger / OpenAPI Spec (if applicable): [Link or file path to spec]
  ├── Middleware (if applicable)
  │     | Name | Purpose | Applied To |
  ├── CORS & Security Headers (if applicable)
  │     • [Header name and value — e.g. Access-Control-Allow-Origin: *]
  └── Other Tooling (if applicable)
        • [API gateways, proxies, monitoring tools, etc.]

Known Issues / Limitations
  • [Current gotchas or constraints]

Potential Improvements
  • [Aspirational enhancements]

Related Pages
  • [Links to related tables, ETLs, runbooks]

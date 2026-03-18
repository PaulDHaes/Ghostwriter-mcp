# Ghostwriter MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that wraps
[Ghostwriter's](https://github.com/GhostManager/Ghostwriter) GraphQL API and exposes
tools that AI agents (Claude Desktop, VS Code Copilot, etc.) can call to manage
clients, projects, reports and findings for penetration testing engagements.

---

## Features

- Search and retrieve clients, projects, reports, and findings
- Create new clients, projects, reports, and findings
- Attach findings from the library to reports
- Update reported findings (replication steps, affected entities)
- Generate unique project codenames
- **stdio** transport (default) for local MCP clients and **SSE** transport for HTTP-based clients

---

## Prerequisites

- Python 3.10+
- A running Ghostwriter instance with its GraphQL/Hasura API accessible
- A Ghostwriter API token

---

## Installation

```bash
git clone <repo-url>
cd copilot-try-ghostwriter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root (or export the variables in your shell):

```env
# Required
GHOSTWRITER_GRAPHQL_URL=https://ghostwriter.example.local/v1/graphql

# Recommended
GHOSTWRITER_API_TOKEN=your_api_token_here

# Optional overrides
GHOSTWRITER_REQUEST_TIMEOUT=10
GHOSTWRITER_DEFAULT_PROJECT_TYPE_ID=1
GHOSTWRITER_DEFAULT_SEVERITY_ID=1
GHOSTWRITER_PAGINATION_LIMIT=50
```

| Variable                              | Required | Default | Description                                       |
| ------------------------------------- | -------- | ------- | ------------------------------------------------- |
| `GHOSTWRITER_GRAPHQL_URL`             | ✅       | —       | GraphQL endpoint (also accepts `GHOSTWRITER_URL`) |
| `GHOSTWRITER_API_TOKEN`               | ⚠️       | —       | Bearer token for authentication                   |
| `GHOSTWRITER_REQUEST_TIMEOUT`         | ❌       | `10`    | HTTP request timeout in seconds                   |
| `GHOSTWRITER_DEFAULT_PROJECT_TYPE_ID` | ❌       | —       | Default project type for new projects             |
| `GHOSTWRITER_DEFAULT_SEVERITY_ID`     | ❌       | —       | Default severity for new findings                 |
| `GHOSTWRITER_PAGINATION_LIMIT`        | ❌       | `50`    | Max results per search query                      |

> **TLS Note:** Certificate verification is enabled by default. If Ghostwriter uses a
> self-signed certificate, add the CA to your system trust store (recommended).

---

## Running the Server

### stdio — default (local MCP clients such as Claude Desktop)

```bash
python main.py
```

### SSE — HTTP transport (remote or HTTP-based MCP clients)

```bash
python main.py --transport sse

# Custom host/port
python main.py --transport sse --host 0.0.0.0 --port 8009
```

### All CLI options

```
usage: main.py [-h] [--transport {stdio,sse}] [--host HOST] [--port PORT]

options:
  --transport {stdio,sse}   Transport mode (default: stdio)
  --host HOST               Host to bind for SSE transport (default: 127.0.0.1)
  --port PORT               Port to bind for SSE transport (default: 8009)
```

---

## Connecting to Claude Desktop (stdio)

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ghostwriter": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/copilot-try-ghostwriter/main.py"],
      "env": {
        "GHOSTWRITER_GRAPHQL_URL": "https://ghostwriter.example.local/v1/graphql",
        "GHOSTWRITER_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

---

## Available Tools

| Tool                            | Description                                      |
| ------------------------------- | ------------------------------------------------ |
| `search_ghostwriter_findings`   | Search the findings library by title             |
| `search_ghostwriter_reports`    | Search reports by title                          |
| `search_ghostwriter_clients`    | Search clients by name, codename, or shortName   |
| `search_ghostwriter_projects`   | Search projects by codename or client name       |
| `get_ghostwriter_client_by_id`  | Fetch a client by ID                             |
| `get_ghostwriter_project_by_id` | Fetch a project by ID                            |
| `get_ghostwriter_report_by_id`  | Fetch a report by ID                             |
| `generate_ghostwriter_codename` | Generate a unique codename                       |
| `create_ghostwriter_client`     | Create a new client                              |
| `create_ghostwriter_project`    | Create a new project (requires `clientId`)       |
| `create_ghostwriter_report`     | Create a new report (requires `projectId`)       |
| `create_ghostwriter_finding`    | Add a finding to the library                     |
| `attach_finding_to_report`      | Attach a library finding to a report             |
| `list_report_finding`           | List all findings attached to a report           |
| `update_report_finding`         | Update replication steps / affected entities     |
| `explain_workflow`              | Get a complete guide on the recommended workflow |

---

## Workflow

When creating a full engagement report from scratch, follow this order — each step
returns an ID needed by the next:

```
generate_ghostwriter_codename
        ↓
create_ghostwriter_client  → clientId
        ↓
create_ghostwriter_project (clientId) → projectId
        ↓
create_ghostwriter_report  (projectId) → reportId
        ↓
attach_finding_to_report   (reportId) → reportedFindingId
        ↓
update_report_finding      (reportedFindingId)
```

> **Always search before creating** to avoid duplicates:
>
> 1. `search_ghostwriter_clients` — reuse `clientId` if found
> 2. `search_ghostwriter_projects` — reuse `projectId` if found
> 3. `search_ghostwriter_reports` — reuse `reportId` if found

### Traceback (starting from a known report)

If you only have a `reportId` and need to walk back up the hierarchy:

1. `get_ghostwriter_report_by_id` → returns `projectId`
2. `get_ghostwriter_project_by_id` → returns `clientId`
3. `get_ghostwriter_client_by_id` → returns full client details

### Project Type IDs

| ID  | Type       |
| --- | ---------- |
| 1   | Web App    |
| 2   | Red Team   |
| 3   | Mobile App |
| 4   | Cloud      |
| 5   | Internal   |

Environment variables

- `GHOSTWRITER_GRAPHQL_URL` (or `GHOSTWRITER_URL`): URL to Ghostwriter GraphQL endpoint (e.g. `https://ghostwriter.example.local/v1/graphql`). Required.
- `GHOSTWRITER_API_TOKEN`: Bearer token to authenticate with Ghostwriter. Optional but recommended.
- `GHOSTWRITER_REQUEST_TIMEOUT`: Request timeout in seconds (default 10).
- `GHOSTWRITER_DEFAULT_PROJECT_TYPE_ID`: Optional default project type id used by helpers.
- `GHOSTWRITER_DEFAULT_SEVERITY_ID`: Optional default severity id for creating findings.
- `GHOSTWRITER_PAGINATION_LIMIT`: Default pagination limit for list queries (default 50).

Note: TLS certificate verification is enabled by default. If you run Ghostwriter on a host with a self-signed certificate, you can either:

- Add the CA to your system trust store (recommended), or
- Run the MCP server in an environment where certificate verification can be disabled (not recommended for production). The library intentionally defaults to verifying certificates.

How to run

1. Create a virtualenv and install dependencies (add `httpx`, `python-dotenv` etc. to the requirements):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Populate a `.env` file with `GHOSTWRITER_GRAPHQL_URL` and `GHOSTWRITER_API_TOKEN`.

3. Start the MCP server (example uses FastMCP settings in `main.py`):

```bash
python main.py
```

Design notes and suggestions for the AI mapping workflow

Your goal: have an AI agent inspect an HTTP request+response and do the following automatically:

1. Determine which Ghostwriter report (if any) the request belongs to.
2. Determine which library finding (if any) matches the request and ideally identify the right `findingId`.
3. If necessary, create a new finding with the provided evidence and metadata.
4. Attach that finding to the determined report (create reportedFinding row).
5. Update the reported finding with replication steps, affected entities, and any other specifics.

Recommendations and improvements

- Heuristics and evidence extraction:
  - Normalize inputs: extract hostnames, URLs, request/response bodies, parameters, headers, and timestamps.
  - Use a similarity search over existing findings' titles/descriptions (embedding + cosine) to find candidate matches.
  - If multiple candidates are close, return them for human review or apply a confidence threshold to auto-attach.

- AI agent responsibilities:
  - Use a small structured schema as the agent's output: { report_hint, finding_hint, action, confidence, payload }.
  - Actions: attach_existing_finding, create_and_attach_finding, update_reported_finding, ask_human.

- Mapping strategy:
  - First, search reports by projectId, report title, or recent activity — use time windows and hostnames to narrow down.
  - Next, search findings with a text match on title/summary and fuzzy match on extracted evidence.
  - If none match above a confidence threshold, create a new finding with an auto-generated title and structured description including request/response snippet.

- Data model suggestions:
  - Store embeddings for findings and report summaries to speed up similarity matching.
  - Cache recent reports/projects in-memory for faster candidate narrowing.

- Efficiency and scale:
  - Batch API calls where possible (e.g., search multiple findings in one query).
  - Use pagination and limits to avoid returning huge datasets.
  - Keep heavy ML work (embeddings, similarity) in a separate service or background job if you expect many events per minute.

- Safety and UX:
  - Auto-attach only when confidence is high; otherwise create a suggested action that a human can approve.
  - Add a 'dry-run' mode where the agent returns the planned changes without applying them.

Next steps I can help with

- Add embedding-based similarity helpers (e.g., using OpenAI embeddings or local models) and example code showing how to find candidate findings.
- Add a dry-run tool to the MCP server so the AI can present actions before committing.
- Add unit tests and CI for the GraphQL helper functions.
- Add a small example that simulates an HTTP request/response and shows the agent deciding whether to attach/create/update.

Tell me which of the above you'd like me to implement next and I'll continue.

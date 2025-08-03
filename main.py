import logging
from mcp.server.fastmcp import FastMCP
from temp_ghostwriter_api import (
    search_findings,
    search_reports,
    search_clients,
    search_projects,
    generate_codename,
    create_client,
    create_project,
    create_report,
    add_finding_to_report,
    list_report_findings,
    update_report_finding,
)

server = FastMCP("GhostwriterMCP")

# Add a server-level description that explains the workflow
server.description = """
Ghostwriter MCP Server for penetration testing report management.

WORKFLOW DEPENDENCIES:
1. First: Generate a codename
2. Then: create_ghostwriter_client (needs a codename from step 1, returns clientId)
3. Then: create_ghostwriter_project (needs clientId from step 2, returns projectId)
4. Then: create_ghostwriter_report (needs projectId from step 3, returns reportId)
5. Finally: attach_finding_to_report (needs reportId from step 4)

Always follow this sequence when creating new reports from scratch.
"""


@server.tool(
    name="search_ghostwriter_findings",
    description="Search for Ghostwriter findings by title.",
)
async def search_ghostwriter_findings(search_term: str):
    try:
        results = await search_findings(search_term)
        findings = results["data"]["finding"]
        return [
            {
                "id": f["id"],
                "title": f["title"],
                "severity": f["severity"]["severity"],
                "description": f["description"][:100] + "...",  # Truncated
            }
            for f in findings
        ]
    except Exception as e:
        logging.error(f"Error searching findings: {e}")
        return {"error": str(e)}


@server.tool(
    name="search_ghostwriter_reports",
    description="""Search Ghostwriter reports by title.
    
    USE CASE: Find existing reports to work with, or check if a report already exists.
    SEARCH BY: Report title (partial matches supported)
    RETURNS: List of reports with their IDs and projectIds
    
    Example searches:
    - search_ghostwriter_reports("Q4 Pentest") → finds "Q4 Pentest Report", "Q4 Pentest Final", etc.
    - search_ghostwriter_reports("Web App") → finds all reports with "Web App" in the title
    """,
)
async def search_ghostwriter_reports(search_term: str):
    try:
        results = await search_reports(search_term)
        reports = results["data"]["report"]
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "projectId": r["projectId"],
                "_workflow_note": f"Use id={r['id']} as reportId for attach_finding_to_report",
            }
            for r in reports
        ]
    except Exception as e:
        logging.error(f"Error searching reports: {e}")
        return {"error": str(e)}


@server.tool(
    name="search_ghostwriter_clients",
    description="""Search for existing Ghostwriter clients by name, codename, or shortName.
    
    USE CASE: Before creating a new client, search to see if it already exists.
    SEARCH BY: Client name, codename, or shortName (partial matches supported)
    RETURNS: List of clients with their IDs - use the 'id' field as clientId in create_ghostwriter_project
    
    REQUIRED FIELDS: Only 'name' and 'codename' are guaranteed to be present
    OPTIONAL FIELDS: May include shortName, address, note, timezone (empty string if not set)
    
    Example searches:
    - search_ghostwriter_clients("Acme") → finds "Acme Corp", "Acme Industries", etc.
    - search_ghostwriter_clients("ACME2024") → finds client with codename "ACME2024"
    
    Example workflow:
    1. Search for existing client by name/codename first
    2. If found: use the returned 'id' as clientId  
    3. If not found: create new client with create_ghostwriter_client
    """,
)
async def search_ghostwriter_clients(search_term: str):
    try:
        results = await search_clients(search_term)
        clients = results["data"]["client"]
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "codename": c["codename"],
                # Optional fields - may be empty strings if not set
                "shortName": c.get("shortName", ""),
                "address": c.get("address", ""),
                "note": c.get("note", ""),
                "timezone": c.get("timezone", ""),
                "_workflow_note": f"Use id={c['id']} as clientId for create_ghostwriter_project",
            }
            for c in clients
        ]
    except Exception as e:
        logging.error(f"Error searching clients: {e}")
        return {"error": str(e)}


@server.tool(
    name="search_ghostwriter_projects",
    description="""Search for existing Ghostwriter projects by codename or client info.
    
    USE CASE: Before creating a new project, search to see if it already exists.
    SEARCH BY: Project codename, client name, or client codename (partial matches supported)
    RETURNS: List of projects with their IDs - use the 'id' field as projectId in create_ghostwriter_report
    
    REQUIRED FIELDS: Only 'id', 'codename', and 'clientId' are guaranteed to be present
    OPTIONAL FIELDS: May include startDate, endDate, note, projectType, client details (empty if not set)
    
    Example searches:
    - search_ghostwriter_projects("REDTEAM2024") → finds project with codename "REDTEAM2024"
    - search_ghostwriter_projects("Acme") → finds projects for clients named "Acme Corp", etc.
    - search_ghostwriter_projects("ACME2024") → finds projects for client with codename "ACME2024"
    
    Example workflow:
    1. Search for existing project by codename/client first
    2. If found: use the returned 'id' as projectId
    3. If not found: create new project with create_ghostwriter_project
    """,
)
async def search_ghostwriter_projects(search_term: str):
    try:
        results = await search_projects(search_term)
        projects = results["data"]["project"]
        return [
            {
                "id": p["id"],
                "codename": p["codename"],
                "clientId": p["clientId"],
                # Optional fields - may be empty strings if not set
                "projectType": p.get("projectType", {}).get("projectType", "Unknown"),
                "startDate": p.get("startDate", ""),
                "endDate": p.get("endDate", ""),
                "note": p.get("note", ""),
                "clientName": p.get("client", {}).get("name", ""),
                "clientCodename": p.get("client", {}).get("codename", ""),
                "_workflow_note": f"Use id={p['id']} as projectId for create_ghostwriter_report",
            }
            for p in projects
        ]
    except Exception as e:
        logging.error(f"Error searching projects: {e}")
        return {"error": str(e)}


@server.tool(
    name="generate_ghostwriter_codename",
    description="""Generate a codename for a new project.
    
    NOTE: This is typically used before creating a client or project to get a unique codename.""",
)
async def generate_ghostwriter_codename(dummy: str = ""):
    try:
        result = await generate_codename()
        return {"codename": result["data"]["generateCodename"]["codename"]}
    except Exception as e:
        logging.error(f"Error generating codename: {e}")
        return {"error": str(e)}


@server.tool(
    name="create_ghostwriter_client",
    description="""Create a new Ghostwriter client using name, short name, and codename.
    
    DEPENDENCY: This is STEP 1 in the workflow (if client doesn't exist).
    RECOMMENDED: First use search_ghostwriter_clients to check if client already exists!
    RETURNS: clientId (required for create_ghostwriter_project)
    
    REQUIRED PARAMETERS:
    - name: Full client name (e.g., "Acme Corporation")
    - short_name: Abbreviated name (e.g., "Acme")  
    - codename: Unique identifier (e.g., "ACME2024")
    
    OPTIONAL PARAMETERS (can be empty/null):
    - address: Client's physical address no ',' in the string
    - note: Additional notes about the client
    - timezone: Client's timezone (e.g., "America/New_York")
    
    Example workflow:
    1. Call search_ghostwriter_clients("ClientName") to check if exists
    2. If NOT found: Call generate_ghostwriter_codename() to get a codename  
    3. Call this function to create client
    4. Use the returned 'id' as 'clientId' in create_ghostwriter_project
    """,
)
async def create_ghostwriter_client(
    name: str,
    short_name: str,
    codename: str,
    address: str = None,
    note: str = None,
    timezone: str = None,
) -> dict:
    try:
        client_data = await create_client(
            name, short_name, codename, address, note, timezone
        )

        if not client_data:
            return {"error": "Failed to create client - no data returned"}

        result = {
            "id": client_data["id"],
            "name": client_data["name"],
            "shortName": client_data.get("shortName", ""),
            "codename": client_data["codename"],
            "address": client_data.get("address", ""),
            "note": client_data.get("note", ""),
            "timezone": client_data.get("timezone", ""),
            "_workflow_note": "Save this 'id' as clientId for create_ghostwriter_project",
        }

        # Log for LLM context
        logging.info(
            f"Client created with ID: {result['id']} - Use this as clientId in next step"
        )

        return result
    except Exception as e:
        logging.error(f"Error creating client: {e}")
        return {"error": str(e)}


@server.tool(
    name="create_ghostwriter_project",
    description="""Create a new Ghostwriter project.

    DEPENDENCY: This is STEP 2 in the workflow (if project doesn't exist).
    RECOMMENDED: First use search_ghostwriter_projects to check if project already exists!
    REQUIRES: clientId from create_ghostwriter_client OR search_ghostwriter_clients
    RETURNS: projectId (required for create_ghostwriter_report)

    Parameters:
    - 'clientId': Get this from either:
      • create_ghostwriter_client output (if creating new client)
      • search_ghostwriter_clients output (if using existing client)
    - 'projectTypeId' is an integer (1–5):
       1 = Web App
       2 = Red Team  
       3 = Mobile App
       4 = Cloud
       5 = Internal
    - 'startDate' and 'endDate' should be in ISO format (YYYY-MM-DD)
    
    Example: If search found client {"id": 123, ...}, use clientId=123
    """,
)
async def create_ghostwriter_project(
    clientId: int,
    codename: str,
    projectTypeId: int,
    startDate: str,
    endDate: str,
):
    try:
        result = await create_project(
            clientId, codename, projectTypeId, startDate, endDate
        )

        project = result["data"]["insert_project"]["returning"][0]

        response = {
            "id": project["id"],
            "codename": project["codename"],
            "start_date": project["startDate"],
            "end_date": project["endDate"],
            "_workflow_note": "Save this 'id' as projectId for create_ghostwriter_report",
        }

        # Log for LLM context
        logging.info(
            f"Project created with ID: {response['id']} - Use this as projectId in next step"
        )

        return response
    except Exception as e:
        logging.error(f"Error creating project: {e}")
        return {"error": str(e)}


@server.tool(
    name="create_ghostwriter_report",
    description="""Create a new Ghostwriter report linked to a project.
    
    DEPENDENCY: This is STEP 3 in the workflow (if report doesn't exist).
    RECOMMENDED: First use search_ghostwriter_reports to check if report already exists!
    REQUIRES: projectId from create_ghostwriter_project OR search_ghostwriter_projects
    RETURNS: reportId (required for attach_finding_to_report)
    
    Parameters:
    - 'projectId': Get this from either:
      • create_ghostwriter_project output (if creating new project)
      • search_ghostwriter_projects output (if using existing project)
    
    Example: If search found project {"id": 456, ...}, use projectId=456
    """,
)
async def create_ghostwriter_report(
    title: str,
    projectId: int,
    last_update: str,
):
    try:
        result = await create_report(title, projectId, last_update)
        report = result["data"]["insert_report"]["returning"][0]

        response = {
            "id": report["id"],
            "title": report["title"],
            "project_id": report["projectId"],
            "last_update": report["last_update"],
            "_workflow_note": "Save this 'id' as reportId for attach_finding_to_report",
        }

        # Log for LLM context
        logging.info(
            f"Report created with ID: {response['id']} - Use this as reportId for findings"
        )

        return response
    except Exception as e:
        logging.error(f"Error creating report: {e}")
        return {"error": str(e)}


@server.tool(
    name="attach_finding_to_report",
    description="""Attach a finding from the library to a report.
    
    DEPENDENCY: This is STEP 4 in the workflow.
    REQUIRES: reportId from create_ghostwriter_report OR search_ghostwriter_reports
    
    Parameters:
    - 'finding': Either a finding ID (int) or title (str) to search for
    - 'reportId': Get this from either:
      • create_ghostwriter_report output (if creating new report)
      • search_ghostwriter_reports output (if using existing report)
    
    Example: If search found report {"id": 789, ...}, use reportId=789
    """,
)
async def attach_finding_to_report(finding, reportId: int):
    try:
        if isinstance(finding, str):
            search_results = await search_findings(finding)
            matches = search_results["data"]["finding"]
            if not matches:
                return {"error": f"No finding found with title like: '{finding}'"}
            findingId = matches[0]["id"]
        else:
            findingId = int(finding)

        result = await add_finding_to_report(findingId, reportId)
        return {
            "reportedFindingId": result["data"]["attachFinding"]["id"],
            "usedFindingId": findingId,
        }

    except Exception as e:
        logging.error(f"Error attaching finding to report: {e}")
        return {"error": str(e)}


@server.tool(
    name="list_report_finding",
    description="List only the IDs and titles of findings attached to a report.",
)
async def list_report_finding_titles_tool(reportId: int):
    try:
        results = await list_report_findings(reportId)
        findings = results["data"]["reportedFinding"]
        return [{"id": f["id"], "title": f["title"]} for f in findings]
    except Exception as e:
        logging.error(f"Error listing finding titles: {e}")
        return {"error": str(e)}


@server.tool(
    name="update_report_finding",
    description="Update the replication steps and/or affected entities of a reported finding. Provide at least one.",
)
async def update_report_finding_tool(
    findingId: float, replicationSteps: str = None, affectedEntities: str = None
):
    try:
        result = await update_report_finding(
            findingId=int(findingId),
            replicationSteps=replicationSteps,
            affectedEntities=affectedEntities,
        )
        return result["data"]["update_reportedFinding"]
    except Exception as e:
        logging.error(f"Error updating reported finding: {e}")
        return {"error": str(e)}


# Add a helper tool that explains the complete workflow
@server.tool(
    name="explain_workflow",
    description="Explains the complete workflow for creating a new penetration testing report in Ghostwriter, including how to use existing entities.",
)
async def explain_workflow():
    return {
        "workflow_options": {
            "create_everything_new": [
                {
                    "step": 1,
                    "tool": "generate_ghostwriter_codename",
                    "purpose": "Generate a unique codename",
                    "returns": "codename (string)",
                },
                {
                    "step": 2,
                    "tool": "create_ghostwriter_client",
                    "purpose": "Create client organization",
                    "requires": "codename from step 1",
                    "returns": "clientId (integer) - SAVE THIS!",
                },
                {
                    "step": 3,
                    "tool": "create_ghostwriter_project",
                    "purpose": "Create project under client",
                    "requires": "clientId from step 2",
                    "returns": "projectId (integer) - SAVE THIS!",
                },
                {
                    "step": 4,
                    "tool": "create_ghostwriter_report",
                    "purpose": "Create report under project",
                    "requires": "projectId from step 3",
                    "returns": "reportId (integer) - SAVE THIS!",
                },
                {
                    "step": 5,
                    "tool": "attach_finding_to_report",
                    "purpose": "Add findings to the report",
                    "requires": "reportId from step 4",
                },
            ],
            "use_existing_entities": [
                {
                    "step": "1a",
                    "tool": "search_ghostwriter_clients",
                    "purpose": "Check if client already exists",
                    "returns": "clientId if found, otherwise create new client",
                },
                {
                    "step": "2a",
                    "tool": "search_ghostwriter_projects",
                    "purpose": "Check if project already exists",
                    "requires": "clientId from step 1a",
                    "returns": "projectId if found, otherwise create new project",
                },
                {
                    "step": "3a",
                    "tool": "search_ghostwriter_reports",
                    "purpose": "Check if report already exists",
                    "requires": "projectId from step 2a",
                    "returns": "reportId if found, otherwise create new report",
                },
                {
                    "step": "4a",
                    "tool": "attach_finding_to_report",
                    "purpose": "Add findings to existing or new report",
                    "requires": "reportId from step 3a",
                },
            ],
        },
        "best_practices": [
            "Always search first before creating to avoid duplicates",
            "Each step depends on the ID returned from the previous step",
            "Save the 'id' field from each response to use in the next step",
            "You can mix search and create operations as needed",
            "Use search_ghostwriter_findings to find existing findings to attach",
        ],
        "common_scenarios": {
            "new_client_existing_project": "Search for project, if found use its clientId",
            "existing_client_new_project": "Search for client, use its ID to create project",
            "add_findings_to_existing_report": "Search for report, use its ID to attach findings",
        },
    }


if __name__ == "__main__":
    import asyncio

    asyncio.run(server.run(transport="stdio"))

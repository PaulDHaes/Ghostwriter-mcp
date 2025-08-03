import os
from dotenv import load_dotenv
import httpx

load_dotenv()

GHOSTWRITER_URL = os.getenv("GHOSTWRITER_URL")
GHOSTWRITER_API_TOKEN = os.getenv("GHOSTWRITER_API_TOKEN")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {GHOSTWRITER_API_TOKEN}",
}


async def _post(query: str, variables: dict = None):
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            GHOSTWRITER_URL,
            headers=HEADERS,
            json={"query": query, "variables": variables or {}},
        )
        response.raise_for_status()
        return response.json()


async def search_findings(search_term: str):
    query = """
    query ($term: String!) {
      finding(where: {title: {_ilike: $term}}) {
        id
        title
        description
        severity {
          severity
        }
      }
    }
    """
    variables = {"term": f"%{search_term}%"}
    return await _post(query, variables)


async def search_reports(search_term: str):
    query = """
    query ($term: String!) {
      report(where: {title: {_ilike: $term}}) {
        id
        title
        projectId
      }
    }
    """
    variables = {"term": f"%{search_term}%"}
    return await _post(query, variables)


async def search_clients(search_term: str):
    """Search for clients by name, codename, or shortName"""
    query = """
    query ($term: String!) {
      client(where: {
        _or: [
          {name: {_ilike: $term}},
          {codename: {_ilike: $term}},
          {shortName: {_ilike: $term}}
        ]
      }) {
        id
        name
        shortName
        codename
        address
        note
        timezone
      }
    }
    """
    variables = {"term": f"%{search_term}%"}
    result = await _post(query, variables)

    # Process results to handle null/empty optional fields gracefully
    if result.get("data", {}).get("client"):
        for client in result["data"]["client"]:
            # Ensure optional fields have fallback values
            client["address"] = client.get("address") or ""
            client["note"] = client.get("note") or ""
            client["timezone"] = client.get("timezone") or ""
            client["shortName"] = client.get("shortName") or ""

    return result


async def search_projects(search_term: str):
    """Search for projects by codename or related client info"""
    query = """
    query ($term: String!) {
      project(where: {
        _or: [
          {codename: {_ilike: $term}},
          {client: {name: {_ilike: $term}}},
          {client: {codename: {_ilike: $term}}}
        ]
      }) {
        id
        codename
        clientId
        startDate
        endDate
        note
        projectType {
          projectType
        }
        client {
          name
          codename
        }
      }
    }
    """
    variables = {"term": f"%{search_term}%"}
    result = await _post(query, variables)

    # Process results to handle null/empty optional fields gracefully
    if result.get("data", {}).get("project"):
        for project in result["data"]["project"]:
            # Ensure optional fields have fallback values
            project["note"] = project.get("note") or ""
            project["startDate"] = project.get("startDate") or ""
            project["endDate"] = project.get("endDate") or ""
            # Handle nested projectType that might be null
            if not project.get("projectType"):
                project["projectType"] = {"projectType": "Unknown"}
            # Handle nested client that might be null
            if not project.get("client"):
                project["client"] = {"name": "", "codename": ""}
    return result


async def get_client_by_id(client_id: int):
    """Get a specific client by ID"""
    query = """
    query ($clientId: bigint!) {
      client(where: {id: {_eq: $clientId}}) {
        id
        name
        shortName
        codename
      }
    }
    """
    variables = {"clientId": client_id}
    return await _post(query, variables)


async def get_project_by_id(project_id: int):
    """Get a specific project by ID"""
    query = """
    query ($projectId: bigint!) {
      project(where: {id: {_eq: $projectId}}) {
        id
        codename
        clientId
        startDate
        endDate
        projectType {
          projectType
        }
        client {
          name
          codename
        }
      }
    }
    """
    variables = {"projectId": project_id}
    return await _post(query, variables)


async def get_projects_by_client(client_id: int):
    """Get all projects for a specific client"""
    query = """
    query ($clientId: bigint!) {
      project(where: {clientId: {_eq: $clientId}}) {
        id
        codename
        startDate
        endDate
        projectType {
          projectType
        }
      }
    }
    """
    variables = {"clientId": client_id}
    return await _post(query, variables)


async def get_reports_by_project(project_id: int):
    """Get all reports for a specific project"""
    query = """
    query ($projectId: bigint!) {
      report(where: {projectId: {_eq: $projectId}}) {
        id
        title
        last_update
      }
    }
    """
    variables = {"projectId": project_id}
    return await _post(query, variables)


async def generate_codename():
    query = """
    mutation {
      generateCodename {
        codename
      }
    }
    """
    return await _post(query)


async def create_client(
    name: str,
    short_name: str,
    codename: str,
    address: str = None,
    note: str = None,
    timezone: str = None,
):
    query = """
    mutation CreateClient(
        $name: String!,
        $short_name: String!,
        $codename: String!,
        $address: String,
        $note: String,
        $timezone: String
    ) {
      insert_client(objects: [
        {
          name: $name,
          shortName: $short_name,
          codename: $codename,
          address: $address,
          note: $note,
          timezone: $timezone
        }
      ]) {
        returning {
          id
          name
          shortName
          codename
          address
          note
          timezone
        }
      }
    }
    """

    variables = {
        "name": name,
        "short_name": short_name,
        "codename": codename,
        "address": address,
        "note": note,
        "timezone": timezone,
    }

    result = await _post(query, variables)
    client = result.get("data", {}).get("insert_client", {}).get("returning", [])
    return client[0] if client else None


async def create_project(
    clientId: int,
    codename: str,
    projectTypeId: int,
    startDate: str = None,
    endDate: str = None,
):
    query = """
    mutation CreateProject(
        $clientId: bigint!,
        $projectTypeId: bigint!,
        $codename: String!,
        $startDate: date!,
        $endDate: date!
    ) {
        insert_project(objects: {
            clientId: $clientId,
            projectTypeId: $projectTypeId,
            codename: $codename,
            startDate: $startDate,
            endDate: $endDate
        }) {
            returning {
                id
                codename
                startDate
                endDate
            }
        }
    }
    """
    variables = {
        "clientId": int(clientId),
        "projectTypeId": int(projectTypeId),
        "codename": codename,
        "startDate": startDate,
        "endDate": endDate,
    }
    return await _post(query, variables)


async def create_report(title: str, projectId: int, last_update: str):
    query = """
    mutation CreateReport($title: String!, $projectId: bigint!, $lastUpdate: date!) {
      insert_report(objects: {
        title: $title,
        projectId: $projectId,
        last_update: $lastUpdate
      }) {
        returning {
          id
          title
          projectId
          last_update
        }
      }
    }
    """
    variables = {
        "title": title,
        "projectId": int(projectId),
        "lastUpdate": last_update,
    }
    return await _post(query, variables)


async def add_finding_to_report(findingId: int, reportId: int):
    query = """
    mutation ($findingId: Int!, $reportId: Int!) {
      attachFinding(findingId: $findingId, reportId: $reportId) {
        id
      }
    }
    """
    return await _post(query, {"findingId": findingId, "reportId": reportId})


async def list_report_findings(reportId: int):
    query = """
    query ($reportId: bigint!) {
      reportedFinding(where: { reportId: { _eq: $reportId } }) {
        id
        title
      }
    }
    """
    variables = {"reportId": reportId}
    return await _post(query, variables)


async def update_report_finding(
    findingId: int, replicationSteps: str = None, affectedEntities: str = None
):
    # Build the dynamic _set dictionary
    set_fields = {}
    if replicationSteps is not None:
        set_fields["replication_steps"] = replicationSteps
    if affectedEntities is not None:
        set_fields["affectedEntities"] = affectedEntities

    # If nothing to update, fail early
    if not set_fields:
        raise ValueError(
            "At least one of replicationSteps or affectedEntities must be provided."
        )

    query = """
    mutation updateFinding($findingId: bigint!, $_set: reportedFinding_set_input) {
      update_reportedFinding(
        where: { id: { _eq: $findingId } },
        _set: $_set
      ) {
        affected_rows
        returning {
          id
          replication_steps
          affectedEntities
        }
      }
    }
    """
    variables = {
        "findingId": int(findingId),
        "_set": set_fields,
    }
    return await _post(query, variables)

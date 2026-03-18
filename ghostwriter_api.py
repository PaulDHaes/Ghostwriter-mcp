import os
from dotenv import load_dotenv
import httpx
from typing import Any, Dict, Optional

load_dotenv()

# Support both env names
GHOSTWRITER_GRAPHQL_URL = os.getenv("GHOSTWRITER_GRAPHQL_URL") or os.getenv(
    "GHOSTWRITER_URL"
)
GHOSTWRITER_API_TOKEN = os.getenv("GHOSTWRITER_API_TOKEN")
# Default request timeout in seconds
GHOSTWRITER_REQUEST_TIMEOUT = float(os.getenv("GHOSTWRITER_REQUEST_TIMEOUT", "10"))
GHOSTWRITER_DEFAULT_PROJECT_TYPE_ID = os.getenv("GHOSTWRITER_DEFAULT_PROJECT_TYPE_ID")
GHOSTWRITER_DEFAULT_SEVERITY_ID = os.getenv("GHOSTWRITER_DEFAULT_SEVERITY_ID")
GHOSTWRITER_PAGINATION_LIMIT = int(os.getenv("GHOSTWRITER_PAGINATION_LIMIT", "50"))


async def _post(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    verify: Optional[bool] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Low-level HTTP POST to Ghostwriter GraphQL with sensible defaults.

    - timeout: override default timeout (seconds)
    - verify: override TLS verify (True/False). If None, defaults to True (verify certificates).
    - extra_headers: merged into default headers
    """
    if not GHOSTWRITER_GRAPHQL_URL:
        raise RuntimeError(
            "GHOSTWRITER_GRAPHQL_URL (or GHOSTWRITER_URL) not set in environment"
        )

    headers = {"Content-Type": "application/json"}
    if GHOSTWRITER_API_TOKEN:
        headers["Authorization"] = f"Bearer {GHOSTWRITER_API_TOKEN}"
    if extra_headers:
        headers.update(extra_headers)

    # By default we verify TLS certificates. If you need to disable verification
    # (not recommended for production), pass verify=False explicitly to this call.
    if verify is None:
        verify = True

    client_timeout = httpx.Timeout(timeout or GHOSTWRITER_REQUEST_TIMEOUT)

    async with httpx.AsyncClient(verify=verify, timeout=client_timeout) as client:
        try:
            resp = await client.post(
                GHOSTWRITER_GRAPHQL_URL,
                headers=headers,
                json={"query": query, "variables": variables or {}},
            )
        except httpx.RequestError as e:
            raise RuntimeError(f"Network error when calling Ghostwriter GraphQL: {e}") from e

        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            r = e.response
            raise RuntimeError(f"Ghostwriter HTTP error {r.status_code}: {r.text}") from e

    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON response from Ghostwriter: {resp.text}") from exc

    if isinstance(data, dict) and data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    return data


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
    variables = {"term": f"%{search_term}%" if search_term else "%%"}
    return await _post(query, variables)


async def search_reports(search_term: str):
    """Search for report by title"""
    query = """
    query ($term: String!) {
      report(where: {title: {_ilike: $term}}) {
        id
        title
        projectId
      }
    }
    """
    variables = {"term": f"%{search_term}%" if search_term else "%%"}
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
      }
    }
    """
    variables = {"term": f"%{search_term}%" if search_term else "%%"}
    result = await _post(query, variables)

    if result.get("data", {}).get("client"):
        for client in result["data"]["client"]:
            client["address"] = client.get("address") or ""
            client["note"] = client.get("note") or ""
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
    variables = {"term": f"%{search_term}%" if search_term else "%%"}
    result = await _post(query, variables)

    if result.get("data", {}).get("project"):
        for project in result["data"]["project"]:
            project["note"] = project.get("note") or ""
            project["startDate"] = project.get("startDate") or ""
            project["endDate"] = project.get("endDate") or ""
            if not project.get("projectType"):
                project["projectType"] = {"projectType": "Unknown"}
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


async def get_report_by_id(report_id: int):
    """Get a specific report by ID"""
    query = """
    query ($reportId: bigint!) {
      report(where: {id: {_eq: $reportId}}) {
        id
        title
        projectId
        last_update
      }
    }
    """
    variables = {"reportId": report_id}
    result = await _post(query, variables)
    return result


# async def get_projects_by_client(client_id: int):
#     """Get all projects for a specific client"""
#     query = """
#     query ($clientId: bigint!) {
#       project(where: {clientId: {_eq: $clientId}}) {
#         id
#         codename
#         startDate
#         endDate
#         projectType {
#           projectType
#         }
#       }
#     }
#     """
#     variables = {"clientId": client_id}
#     return await _post(query, variables)


# async def get_reports_by_project(project_id: int):
#     """Get all reports for a specific project"""
#     query = """
#     query ($projectId: bigint!) {
#       report(where: {projectId: {_eq: $projectId}}) {
#         id
#         title
#         last_update
#       }
#     }
#     """
#     variables = {"projectId": project_id}
#     return await _post(query, variables)


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
    extra_fields: Optional[Dict[str, Any]] = None,
):
    # Build object for insertion using Hasura input type `client_insert_input`
    obj: Dict[str, Any] = {
        "name": name,
        "shortName": short_name,
        "codename": codename,
    }
    if address is not None:
        obj["address"] = address
    if note is not None:
        obj["note"] = note
    if extra_fields:
        obj.update(extra_fields)

    query = """
    mutation CreateClient($object: client_insert_input!) {
      insert_client_one(object: $object) {
        id
        name
        codename
        shortName
        address
        note
      }
    }
    """
    variables = {"object": obj}
    result = await _post(query, variables)
    return result.get("data", {}).get("insert_client_one")


async def create_project(
    clientId: int,
    codename: str,
    projectTypeId: int,
    startDate: str,
    endDate: str,
    extra_fields: Optional[Dict[str, Any]] = None,
):
    obj: Dict[str, Any] = {
        "clientId": int(clientId),
        "projectTypeId": int(projectTypeId),
        "codename": codename,
        "startDate": startDate,
        "endDate": endDate,
    }
    if extra_fields:
        obj.update(extra_fields)

    query = """
    mutation CreateProject($object: project_insert_input!) {
      insert_project_one(object: $object) {
        id
        codename
        startDate
        endDate
      }
    }
    """
    variables = {"object": obj}
    return await _post(query, variables)


async def create_report(title: str, projectId: int, last_update: str):
    obj: Dict[str, Any] = {
        "title": title,
        "projectId": int(projectId),
        "last_update": last_update,
    }

    query = """
    mutation CreateReport($object: report_insert_input!) {
      insert_report_one(object: $object) {
        id
        title
        projectId
        last_update
      }
    }
    """
    variables = {"object": obj}
    return await _post(query, variables)


async def create_finding(
    title: str,
    description: str,
    findingTypeId: Optional[int] = None,
    severityId: Optional[int] = None,
    cvssScore: Optional[float] = None,
    cvssVector: Optional[str] = None,
    replication_steps: Optional[str] = None,
    affectedEntities: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
):
    """Create a new finding in the Ghostwriter findings library.

    The function accepts common fields and merges any `extra_fields` into the insert object so
    callers can provide optional or custom fields without changing this helper.
    """
    obj: Dict[str, Any] = {"title": title, "description": description}
    if findingTypeId is not None:
        obj["findingTypeId"] = int(findingTypeId)
    if severityId is not None:
        obj["severityId"] = int(severityId)
    if cvssScore is not None:
        obj["cvssScore"] = float(cvssScore)
    if cvssVector is not None:
        obj["cvssVector"] = cvssVector
    if replication_steps is not None:
        obj["replication_steps"] = replication_steps
    if affectedEntities is not None:
        obj["affectedEntities"] = affectedEntities
    if extra_fields:
        obj.update(extra_fields)

    query = """
    mutation CreateFinding($object: finding_insert_input!) {
      insert_finding_one(object: $object) {
        id
        title
        description
      }
    }
    """
    variables = {"object": obj}
    result = await _post(query, variables)
    return result.get("data", {}).get("insert_finding_one")


async def add_finding_to_report(findingId: int, reportId: int):
    query = """
    mutation attachFinding($findingId: Int!, $reportId: Int!) {
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
    set_fields_string = ""
    variables = {"findingId": int(findingId)}

    if replicationSteps is not None:
        set_fields_string += "replication_steps: $replicationSteps"
        variables["replicationSteps"] = replicationSteps

    if affectedEntities is not None:
        if set_fields_string:
            set_fields_string += ", "
        set_fields_string += "affectedEntities: $affectedEntities"
        variables["affectedEntities"] = affectedEntities

    if not set_fields_string:
        raise ValueError(
            "At least one of replicationSteps or affectedEntities must be provided."
        )

    query = f"""
    mutation updateFinding($findingId: bigint!, $replicationSteps: String, $affectedEntities: String) {{
      update_reportedFinding(
        where: {{ id: {{ _eq: $findingId }} }},
        _set: {{ {set_fields_string} }}
      ) {{
        affected_rows
        returning {{
          id
          replication_steps
          affectedEntities
        }}
      }}
    }}
    """
    return await _post(query, variables)

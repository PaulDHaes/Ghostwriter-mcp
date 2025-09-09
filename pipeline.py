"""
title: Ghostwriter LangGraph Pipeline
author: Paul Dhaese
date: 2024-05-30
version: 1.0
description: A pipeline for integrating Ghostwriter LangGraph agent with Open WebUI
requirements: langgraph, langchain_ollama, langchain_core
"""

import asyncio
import operator
import ast
from typing import TypedDict, Annotated, Sequence, List, Union, Generator, Iterator
from pydantic import BaseModel

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage
from langchain_core.tools import Tool

from langgraph.graph import StateGraph, START, END

# Import your Ghostwriter tools
try:
    from main import (
        search_ghostwriter_findings,
        search_ghostwriter_reports,
        search_ghostwriter_clients,
        search_ghostwriter_projects,
        generate_ghostwriter_codename,
        create_ghostwriter_client,
        create_ghostwriter_project,
        create_ghostwriter_report,
        attach_finding_to_report,
        list_report_finding_titles_tool,
        update_report_finding_tool,
        explain_workflow,
        get_ghostwriter_client_by_id_tool,
        get_ghostwriter_project_by_id_tool,
        get_ghostwriter_report_by_id_tool,
    )
except ImportError:
    # If main_extra is not available, create mock functions for demonstration
    print("Warning: main_extra module not found. Using mock functions.")

    async def search_ghostwriter_findings(search_term=None, id=None):
        return {"mock": "finding"}

    async def search_ghostwriter_reports(search_term=None, id=None):
        return {"mock": "report"}

    # Add other mock functions as needed...


class Pipeline:
    class Valves(BaseModel):
        """Configuration valves for the pipeline."""

        OLLAMA_MODEL: str = "qwen3:14b"
        OLLAMA_BASE_URL: str = "http://192.168.1.107:11434"
        MAX_TURNS: int = 10
        DEBUG: bool = False

    def __init__(self):
        self.valves = self.Valves()
        self.setup_agent()

    def setup_agent(self):
        """Initialize the LangGraph agent."""
        # Create tools list
        self.tools = [
            Tool(
                name="search_ghostwriter_findings",
                description="Search for Ghostwriter findings by title. This gives the findingId back",
                func=search_ghostwriter_findings,
            ),
            Tool(
                name="search_ghostwriter_reports",
                description="""Search Ghostwriter reports by title.
        
        USE CASE: Find existing reports to work with, or check if a report already exists.
        SEARCH BY: Report title (partial matches supported)
        RETURNS: List of reports with their IDs and projectIds
        """,
                func=search_ghostwriter_reports,
            ),
            Tool(
                name="search_ghostwriter_clients",
                description="""Search for existing Ghostwriter clients by name, codename, or shortName.
        
        USE CASE: Before creating a new client, search to see if it already exists!
        SEARCH BY: Client name, codename, or shortName (partial matches supported)
        RETURNS: List of clients with their IDs
        """,
                func=search_ghostwriter_clients,
            ),
            Tool(
                name="search_ghostwriter_projects",
                description="""Search for existing Ghostwriter projects by codename or client info.
        
        USE CASE: Before creating a new project, search to see if it already exists!
        SEARCH BY: Project codename, client name, or client codename (partial matches supported)
        RETURNS: List of projects with their IDs
        """,
                func=search_ghostwriter_projects,
            ),
            Tool(
                name="get_ghostwriter_report_by_id",
                description="Fetch a Ghostwriter report directly by ID.",
                func=get_ghostwriter_report_by_id_tool,
            ),
            Tool(
                name="get_ghostwriter_project_by_id",
                description="Fetch a Ghostwriter project directly by ID.",
                func=get_ghostwriter_project_by_id_tool,
            ),
            Tool(
                name="get_ghostwriter_client_by_id",
                description="Fetch a Ghostwriter client directly by ID.",
                func=get_ghostwriter_client_by_id_tool,
            ),
            Tool(
                name="generate_ghostwriter_codename",
                description="Generate a codename for a new project.",
                func=generate_ghostwriter_codename,
            ),
            Tool(
                name="create_ghostwriter_client",
                description="""Create a new Ghostwriter client using name, short name, and codename.
        
        DEPENDENCY: This is STEP 1 in the workflow (if client doesn't exist).
        RETURNS: clientId (required for create_ghostwriter_project)
        """,
                func=create_ghostwriter_client,
            ),
            Tool(
                name="create_ghostwriter_project",
                description="""Create a new Ghostwriter project.

        DEPENDENCY: This is STEP 2 in the workflow (if project doesn't exist).
        REQUIRES: clientId from create_ghostwriter_client OR search_ghostwriter_clients
        RETURNS: projectId (required for create_ghostwriter_report)
        """,
                func=create_ghostwriter_project,
            ),
            Tool(
                name="create_ghostwriter_report",
                description="""Create a new Ghostwriter report linked to a project.
        
        DEPENDENCY: This is STEP 3 in the workflow (if report doesn't exist).
        REQUIRES: projectId from create_ghostwriter_project OR search_ghostwriter_projects
        RETURNS: reportId (required for attach_finding_to_report)
        """,
                func=create_ghostwriter_report,
            ),
            Tool(
                name="attach_finding_to_report",
                description="""Attach a finding from the library to a report.
        
        DEPENDENCY: This is STEP 4 in the workflow.
        REQUIRES: reportId from create_ghostwriter_report OR search_ghostwriter_reports
        """,
                func=attach_finding_to_report,
            ),
            Tool(
                name="list_report_finding",
                description="List only the IDs and titles of findings attached to a report.",
                func=list_report_finding_titles_tool,
            ),
            Tool(
                name="update_report_finding",
                description="""Update the replication steps and/or affected entities of a reported finding.
        
        DEPENDENCY: This is STEP 5 in the workflow.
        REQUIRES: findingId = reportedFindingId from attach_finding_to_report result.
        """,
                func=update_report_finding_tool,
            ),
            Tool(
                name="explain_workflow",
                description="Explains the complete workflow for creating a new penetration testing report in Ghostwriter.",
                func=explain_workflow,
            ),
        ]

        # Initialize model with tools
        self.model = ChatOllama(
            model=self.valves.OLLAMA_MODEL, base_url=self.valves.OLLAMA_BASE_URL
        )
        self.model_with_tools = self.model.bind_tools(self.tools)

        # Define state
        class AgentState(TypedDict):
            messages: Annotated[Sequence[BaseMessage], operator.add]

        self.AgentState = AgentState

        # Build the graph
        self.setup_graph()

    def setup_graph(self):
        """Setup the LangGraph workflow."""

        async def call_model(state):
            messages = state["messages"]
            response = await self.model_with_tools.ainvoke(messages)
            return {"messages": [response]}

        async def call_tool(state):
            last_message = state["messages"][-1]
            tool_call = last_message.tool_calls[0]

            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            tool_object = {t.name: t for t in self.tools}[tool_name]

            # Normalize arguments for search tools
            search_tools = [
                "search_ghostwriter_clients",
                "search_ghostwriter_projects",
                "search_ghostwriter_reports",
                "search_ghostwriter_findings",
            ]

            if tool_name in search_tools:
                arg_value = (
                    tool_args.get("search_term")
                    or tool_args.get("__arg1")
                    or tool_args.get("id")
                )
                if isinstance(arg_value, int) or (
                    isinstance(arg_value, str) and arg_value.isdigit()
                ):
                    tool_args = {"id": int(arg_value)}
                else:
                    tool_args = {"search_term": arg_value}

            # Special case: codename handling
            if (
                tool_name == "create_ghostwriter_project"
                and "codename" not in tool_args
            ):
                for message in reversed(state["messages"]):
                    if (
                        isinstance(message, ToolMessage)
                        and "codename" in message.content
                    ):
                        try:
                            parsed = ast.literal_eval(message.content)
                            if "codename" in parsed:
                                tool_args["codename"] = parsed["codename"]
                                break
                        except Exception:
                            pass

            # Special case: codename generator
            if tool_name == "generate_ghostwriter_codename":
                tool_args = {}

            # Call tool with proper error handling for MCP server
            try:
                if self.valves.DEBUG:
                    print(f"Calling tool {tool_name} with args: {tool_args}")

                # Check if MCP server is available
                if not MCP_AVAILABLE:
                    result = {
                        "error": "MCP server not available. Please ensure main_extra.py is properly configured."
                    }
                else:
                    result = await tool_object.func(**tool_args)

                if self.valves.DEBUG:
                    print(f"Tool {tool_name} result: {result}")

            except Exception as e:
                error_msg = f"Failed to call {tool_name}: {str(e)}"
                if self.valves.DEBUG:
                    print(f"Tool error: {error_msg}")
                result = {"error": error_msg, "args": tool_args}

            tool_message = ToolMessage(
                content=str(result), tool_call_id=tool_call["id"]
            )
            return {"messages": [tool_message]}

        def should_continue(state):
            last_message = state["messages"][-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "continue"
            else:
                return "end"

        # Build workflow
        workflow = StateGraph(self.AgentState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tool", call_tool)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent", should_continue, {"continue": "tool", "end": END}
        )
        workflow.add_edge("tool", "agent")

        self.app = workflow.compile()

    async def run_agent(self, message: str) -> str:
        """Run the agent with a message and return the response."""
        inputs = {"messages": [HumanMessage(content=message)]}

        final_response = ""
        turn_count = 0

        async for event in self.app.astream(inputs):
            turn_count += 1
            if turn_count > self.valves.MAX_TURNS:
                break

            if self.valves.DEBUG:
                print(f"Event: {event}")

            if "__end__" not in event:
                # Extract the last message content
                for node_name, node_data in event.items():
                    if "messages" in node_data:
                        last_msg = node_data["messages"][-1]
                        if hasattr(last_msg, "content") and not hasattr(
                            last_msg, "tool_calls"
                        ):
                            final_response = last_msg.content

        return (
            final_response
            or "I apologize, but I couldn't process your request properly."
        )

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        """Main pipeline method called by Open WebUI."""

        if self.valves.DEBUG:
            print(f"Received message: {user_message}")
            print(f"Model ID: {model_id}")
            print(f"Body: {body}")

        try:
            # Run the agent asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(self.run_agent(user_message))
            loop.close()

            return response

        except Exception as e:
            error_msg = f"Error running Ghostwriter agent: {str(e)}"
            if self.valves.DEBUG:
                print(error_msg)
            return error_msg

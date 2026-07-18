"""Text-first Intake agent for diagnosis-only manual testing.

This runner deliberately removes the contract commit path:
- no commit_intake tool
- no IntakeAgentOutput validation
- no planner-ready JSON checkpointing

It reuses the existing Intake prompt and evidence tools so you can compare how
the same agent behaves without per-turn contract pressure.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from datetime import datetime
from typing import Any, List, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langsmith import traceable
from typing_extensions import Annotated

from src.agents.intake_agent import (
    _ainvoke_with_connection_retries,
    get_active_plan,
    get_calendar_availability,
    query_backlog,
    query_syllabus,
    serialize_tool_result_content,
    tool_result_succeeded,
    update_syllabus_entry,
    verify_claim_search,
)
from src.prompts.intake.text_prompt import intake_text_agent_prompt


load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "skedioai-intake-text-dev"


class IntakeTextState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: str
    user_context: str
    active_plan_context: Optional[dict[str, Any]]
    turn_count: int
    executed_tool_signatures: List[str]


text_intake_tools = [
    get_active_plan,
    query_backlog,
    get_calendar_availability,
    query_syllabus,
    verify_claim_search,
    update_syllabus_entry,
]


class IntakeTextAgent:
    """LangGraph text-only Intake loop using evidence tools only."""

    def __init__(self, llm_client: Any):
        self.llm = llm_client
        self.llm_with_tools = llm_client.bind_tools(text_intake_tools, tool_choice="auto")

    def intake_agent(self):
        tools_by_name = {tool.name: tool for tool in text_intake_tools}

        def build_system_prompt(state: IntakeTextState) -> str:
            return intake_text_agent_prompt(
                user_id=state.get("user_id", "anonymous"),
                current_intake=None,
                user_context=state.get("user_context", ""),
                date_time=datetime.now().strftime("%Y-%m-%d %H:%M | %A"),
            )

        def build_messages(state: IntakeTextState) -> List[BaseMessage]:
            messages: List[BaseMessage] = [
                SystemMessage(content=build_system_prompt(state)),
                *state["messages"],
            ]

            active_plan = state.get("active_plan_context")
            if isinstance(active_plan, dict) and active_plan.get("has_plan"):
                messages.append(
                    SystemMessage(
                        content=(
                            "Active plan context for this user:\n"
                            f"{serialize_tool_result_content(active_plan)}"
                        )
                    )
                )

            return messages

        @traceable(run_type="chain", name="intake_text_call_agent")
        async def call_agent(state: IntakeTextState):
            if state.get("messages") and isinstance(state["messages"][-1], HumanMessage):
                state["executed_tool_signatures"] = []

            response = await _ainvoke_with_connection_retries(
                self.llm_with_tools,
                build_messages(state),
                logger=logger,
                label="INTAKE_TEXT_LLM",
            )
            return {
                "messages": [response],
                "executed_tool_signatures": state.get("executed_tool_signatures", []),
            }

        @traceable(run_type="chain", name="intake_text_call_tools")
        async def call_tools(state: IntakeTextState):
            last_message = state["messages"][-1]
            tool_calls = getattr(last_message, "tool_calls", None) or []
            executed_signatures = list(state.get("executed_tool_signatures") or [])
            tool_messages: list[ToolMessage] = []

            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = dict(tool_call["args"])
                if tool_name == "get_calendar_availability" and "user_id" not in tool_args:
                    tool_args["user_id"] = state.get("user_id")
                if tool_name == "get_active_plan" and "user_id" not in tool_args:
                    tool_args["user_id"] = state.get("user_id")

                tool_signature = json.dumps(
                    {"name": tool_name, "args": tool_args},
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )

                if tool_signature in executed_signatures:
                    result = {
                        "skipped": True,
                        "reason": "duplicate_tool_same_turn",
                        "tool": tool_name,
                    }
                else:
                    tool_obj = tools_by_name.get(tool_name)
                    if tool_obj is None:
                        result = {"error": f"Tool not found: {tool_name}"}
                    else:
                        try:
                            result = await tool_obj.ainvoke(tool_args)
                        except Exception as exc:
                            result = {"error": str(exc), "tool": tool_name}
                    executed_signatures.append(tool_signature)

                content = serialize_tool_result_content(result)
                tool_result_succeeded(content)
                tool_messages.append(
                    ToolMessage(
                        content=content,
                        name=tool_name,
                        tool_call_id=tool_call["id"],
                    )
                )

            return {
                "messages": tool_messages,
                "executed_tool_signatures": executed_signatures,
                "turn_count": state.get("turn_count", 0) + 1,
            }

        def route_after_agent(state: IntakeTextState):
            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"
            return END

        def route_after_tools(state: IntakeTextState):
            if state.get("turn_count", 0) >= 18:
                return END
            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and not getattr(
                last_message, "tool_calls", None
            ):
                return END
            return "agent"

        graph = StateGraph(IntakeTextState)
        graph.add_node("agent", call_agent)
        graph.add_node("tools", call_tools)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
        graph.add_conditional_edges("tools", route_after_tools, {"agent": "agent", END: END})
        return graph.compile()


@traceable(run_type="chain", name="intake_text_interactive_session")
async def run_interactive_session(user_id: str = "test_user_99"):
    import uuid

    session_id = str(uuid.uuid4())[:8]
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
    )
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"convo_intake_text_{session_id}.log")

    turn_count = 0

    def serialize_message(message: BaseMessage) -> dict[str, Any]:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except Exception:
                pass

        item = {"type": message.__class__.__name__, "content": content}
        if getattr(message, "name", None):
            item["name"] = message.name
        if getattr(message, "tool_calls", None):
            item["tool_calls"] = message.tool_calls
        if getattr(message, "tool_call_id", None):
            item["tool_call_id"] = message.tool_call_id
        return item

    def write_log(event_type: str, content: Any) -> None:
        with open(log_file, "a", encoding="utf-8") as f:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "turn": turn_count,
                "event_type": event_type,
                "content": content,
            }
            f.write(json.dumps(entry, ensure_ascii=False, default=str, indent=2))
            f.write("\n\n" + "=" * 80 + "\n\n")

    state: IntakeTextState = {
        "messages": [],
        "user_id": user_id,
        "user_context": "",
        "active_plan_context": None,
        "turn_count": 0,
        "executed_tool_signatures": [],
    }

    app = None
    print("SkedioAI Intake Text started. Type 'exit' to stop.\n")
    print(f"Palantir Intake Text Logging Enabled: {log_file}\n")
    write_log(
        "SYSTEM_START",
        {
            "user_id": user_id,
            "model": "gpt-5-mini",
            "mode": "text_only_existing_prompt",
        },
    )

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit", "q"}:
            write_log("USER_INPUT", "quit")
            print("Exiting.")
            break

        turn_count += 1
        turn_started_at = time.time()
        write_log("USER_INPUT", user_input)
        old_message_count = len(state["messages"])
        state["messages"].append(HumanMessage(content=user_input))

        try:
            if app is None:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="gpt-5-mini",
                    temperature=0.2,
                    api_key=os.getenv("OPENAI_API_KEY"),
                    reasoning_effort="low",
                    verbosity="low",
                )
                app = IntakeTextAgent(llm_client=llm).intake_agent()

            result = await app.ainvoke(state)
            state.update(result)
            new_messages = [
                serialize_message(m) for m in state["messages"][old_message_count:]
            ]
            last_message = state["messages"][-1]

            if isinstance(last_message, AIMessage):
                print(f"\nSkedioAI: {last_message.content}\n")
            else:
                print(f"\nSkedioAI: {last_message}\n")

            write_log(
                "INTAKE_TEXT_TURN",
                {
                    "new_messages": new_messages,
                    "duration_seconds": round(time.time() - turn_started_at, 3),
                },
            )

        except Exception as exc:
            write_log(
                "ERROR",
                {
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                    "traceback": traceback.format_exc(),
                    "duration_seconds": round(time.time() - turn_started_at, 3),
                },
            )
            print(f"\nError: {exc}\n")
            break

    write_log("SYSTEM_END", {"turns": turn_count})


if __name__ == "__main__":
    asyncio.run(run_interactive_session())

from dataclasses import dataclass
from typing import Any

from langgraph.types import Command

from src.messages import last_ai_text, last_tool_text
from src.schemas import TurnSummary
from src.tools.text import prepare_file_content


# In this file we will have piece of code which is needed for the agent while running in turns. It will use the utitlities below here

@dataclass
class AgentTurnResult: # This agent result will help us understand whether its a normal message from the agent or it's an interrupt
    #From this AgentTurnResult we should be able to know whether the agent has done a particular task or its waiting for the interrupt response
    text: str #represents agents reply
    structured: TurnSummary | None #Here we store the turn summary which has structured summary of this particular agent's turn
    messages: list[Any] # This is the full thread of conversations messages/interactions
    pending_interrupt: dict[str, Any] | None # This is the HITL input payload


def _as_summary(value: Any) -> TurnSummary | None:
    if value is None:
        return None
    if isinstance(value, TurnSummary):
        return value
    if isinstance(value, dict):
        try:
            return TurnSummary.model_validate(value) # If the value is dict we are constructing the TurnSummary instance from the dict
                # This .model_validate() checks if the passed dict has the valid properties of the TurnSummary and it can be used to create proper TurnSummary instance
        except Exception:
            return None
    return None

def parse_invoke_result(result: Any) -> AgentTurnResult:
    # The result has .value, .interrupts

    interrupts = tuple(getattr(result, "interrupts", ()) or ()) # All the interrupts that got triggered by the HITL is present in the result.interrupts

    # get the complete graph state using the value property
    value = getattr(result, "value", result) # This result.value holds the complete graph state, event the messages[], we give the default value as result if we are
                                            # not invoking the agent with version 2

    # The result.value holds the graph state which contains all the information about what the graph is doing and the messages[] and all.

    if not isinstance(value, dict):  # If the value's instance is not dict, we are saving it as dict
        value = {}

    messages = value.get("messages") or []

    if interrupts: # There is an interrupt that is caused
        payload = interrupts[0].value #We are picking the 0th element from the interrupts, this value 'property' holds different interrupt actions
        return AgentTurnResult(
            text="",
            structured=None,
            messages=messages,
            pending_interrupt=payload if isinstance(payload, dict) else {"raw": payload} # We are checking if the payload is dict , if not we are putting it as dict
        )

    return AgentTurnResult(
        text=last_ai_text(messages) or last_tool_text(messages),
        structured=_as_summary(value.get("structured_response")), # So when the agent is producing the result in structured output schema it will be present in
                                                                    # 'structured_response' property
        messages=messages,
        pending_interrupt=None
    )

def start_turn(agent, user_text: str, config: dict) -> AgentTurnResult: # This function starts the turn(like a new conversation)
    # This agent.invoke() keeps on running until either the result is produced or any interrupt has happened due to the policy setup in the HumanIntheLoopMiddleware

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_text}]},  # We are setting the role as 'user'
        config=config, # This config has the thread_id information
        version="v2" # This is just the version of agent.invoke() function
    )
    return parse_invoke_result(result)

def resume_turn(agent, decisions: list[dict], config: dict) -> AgentTurnResult:
    # We can use this function when there is an HITL interrupt and we want to pass decisions of the interrupt to the agent again.
    result = agent.invoke(
        # This command object tells the agent what decision we have made for the interrupt that is causes
        Command(resume={ # We are going to set the resume property of the command
            "decisions": decisions # There are different decision type like 'approve' , 'edit', 'reject' and each decision type also has message
        }),
        config=config,
        version="v2"
    )
    return parse_invoke_result(result)


def format_interrupt(pending: dict[str, Any]) -> str:
    # Using this function we can get the action_requests and format and print it in the cli in a proper way.
    requests = pending.get("action_requests") or [] # For a particular result.interrupts[0].value we get the 'action_requests'
    lines = []

    for index, action in enumerate(requests, start=1):
        name = action.get("name", "?")
        args = dict(action.get("args") or {}) # We are converting the args as dict
        description = action.get("description", "?")
        lines.append(f"{index}. {name} ({description})")
        for key, value in args.items(): # every tool call will have arguments with lots of key,value
            preview = str(value)
            if key in {"content", "old_str", "new_str"}: # These are parameters of the tools that we created like (write_file,edit_file etc)
                preview = prepare_file_content(str(args.get("path") or ""), preview) # we are putting the preview content and normalizing the content and trying to
                        # print that
            if "\n" in preview: # if there is \n in the preview (like a multi-line file) we are going to show the content in the single line for just printing
                lines.append(f"    {key}:")
                for body_line in preview.splitlines():
                    lines.append(f"        {body_line}")
                continue

            if len(preview) > 240:
                preview = preview[:240] + "..."
            lines.append(f"    {key}: {preview}")
    return "\n".join(lines) if lines else str(pending)
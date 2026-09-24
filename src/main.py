from runtime import AgentTurnResult, format_interrupt, start_turn, resume_turn
from config.config import get_work_dir
from models import select_provider
from memory import thread_config, make_checkpointer
from agent import build_agent
import uuid
from typing import Any

from src.prompts import build_greeting

def _ask_yes_or_no(name: str) -> bool:
    # We are getting the action's name and asking the user whether to allow it or not
    while True:
        answer = input(f"Allow {name}? (y/N): ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer with 'y' or 'n'.", flush=True)


def _prompt_decision(pending: dict[str, Any]) -> list[dict]: # We get all the pending interrupts as the input
    # This flush=True makes the output to appear immediately in the console or log file without being buffered, this basically flushes the buffer
    print("\n--- human-in-the-loop ---", flush=True)
    print(format_interrupt(pending), flush=True) # We formatting the list of pending decisions and printing
    requests = pending.get("action_requests") or [] # From the interrupts we get the action_requests
    decisions: list[dict] = []
    # Decisions are provided as a list, one per action under review.
    # The order of decisions must match the order of actions
    # in the interrupt request, So the decisions that we append to the decisions array it should be of exactly same order of the actual interrupt request (the order should match)
    for action in requests:
        name = action.get("name", "tool") # get the name of the action
        approved = _ask_yes_or_no(name) # For each of the action_requests that the agent raised we get the human response based on that we frame the decisions
        if approved:
            decisions.append({
                "type": "approve"
            })
        else:
            decisions.append({
                "type": "reject",
                "message": (
                    f"User declined {name}. Do not immediately retry the same command"
                    "Explain what failed or ask the user"
                )
            })
    print("--------------------------------\n", flush=True)
    return decisions


def _drain(agent, result: AgentTurnResult, config: dict) -> AgentTurnResult:
    while result.pending_interrupt is not None: #we keep on check the result.pending_interrupt and if there are, if the agent says || ohh i cant move agead, unblock with HITL
        decision = _prompt_decision(result.pending_interrupt) # This prompt decision will return list of decision
        result = resume_turn(agent, decision, config) # This will create command objects for all the interrupts and pass to the decisions array as per the interrupt request order.
    return result # We continue the while loop of getting the response from the user for the interrupts until the agent says there is no interrupts in the flow

def chat() -> None:
    work_dir = get_work_dir()
    work_dir.mkdir(parents=True, exist_ok=True)
    provider = select_provider()
    checkpointer = make_checkpointer()
    agent = build_agent(checkpointer=checkpointer)
    config = thread_config(str(uuid.uuid4()))

    print(build_greeting())
    print(f"Provider: {provider.name} . {provider.model}")
    print(f"Working directory: {work_dir}")
    print("Type 'exit', 'quit', 'q' to stop. ")

    while True: # This makes the chat loop to go on infinite loop to get user input and do action
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit", "q"}: # if the user inputs any of this we break the loop.
            break

        if not user_input:
            continue

        try:
            # For the first time we start_turn the agent and get the result and continue the loop.
            result = _drain(agent, start_turn(agent, user_input, config), config)
        except RuntimeError as e:
            print(f"LLM: {e}\n")
            continue

        except Exception as e:
            print(f"LLM: {type(e).__name__}: {e}\n")
            continue

        print(f"LLM: {result.text or '(no text)'}")

        if result.structured: # From the agent response we get the AgentTurnResult, from that we pick the structured response and printing its results
            # The agent can do either do HITL interrupts or do some actions whose summary is present in the Turn summary and we are printing that
            print(
                f"  Summary={result.structured.status}\n"
                f"{result.structured.summary} "
                f"Files touched={result.structured.files_touched}"
            )
        print()

if __name__ == "__main__":
    chat()

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.agents.structured_output import ProviderStrategy
from langgraph.checkpoint.memory import InMemorySaver

from src.config.config import MAX_MODEL_CALLS_PER_RUN, hitl_enabled
from src.memory import make_checkpointer
from src.middleware.audit import AuditMiddleware
from src.middleware.hitl import build_hitl_middleware
from src.middleware.protection import ProtectionMiddleware
from src.models import build_chat_model
from src.prompts import build_system_prompt
from src.schemas import TurnSummary
from src.tools import ALL_TOOLS


def build_middleware(enable_hitl: bool) -> list:
    """
    Harness layers, outermost first.

    1. model-call cap
    2. Audit log
    3. payload guarding
    4. HITL on write/edit/run
    """

    layers: list = [
        ModelCallLimitMiddleware(
            run_limit=MAX_MODEL_CALLS_PER_RUN,
            exit_behavior="end"
        ),
        AuditMiddleware(),
        ProtectionMiddleware()
    ]

    if enable_hitl:
        layers.append(build_hitl_middleware())

    return layers # The order in which the middlewares are set in the list in the same order from left to right the middleware gets executed

def build_agent(
    *,
    checkpointer: InMemorySaver | None = None, # we can also get the checkpointer instance from the person who is calling also
    enable_hitl: bool | None = None,
    extra_guidance: str = "",
):
    model, _provider = build_chat_model()
    use_hitl = hitl_enabled() if enable_hitl is None else enable_hitl
    return create_agent(
        model=model,
        tools=ALL_TOOLS, # We are sending all the tools in an array
        system_prompt=build_system_prompt(extra_guidance=extra_guidance),
        middleware=build_middleware(enable_hitl=use_hitl),
        response_format=ProviderStrategy(TurnSummary), # We are setting the output schema
        checkpointer=checkpointer or make_checkpointer(),
        name="Coding-Agent",
    )
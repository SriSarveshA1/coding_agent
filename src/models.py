import os
from dotenv import load_dotenv
from dataclasses import dataclass
from langchain_openai import ChatOpenAI

load_dotenv()

@dataclass(frozen=True) # We define a Provider class and make it frozen so the object created doesn't get changed
class Provider:
    name: str # Name of the model provided
    env_var: str # We mention the api_key env variable
    is_free: bool # Tells the model is free to use
    base_url: str | None # host url where the model is hosted, most of the common provider's package has this but in case if we want override we can
    model: str # Model name

PROVIDERS = [
    Provider(
        "OpenAI",
        "OPENAI_API_KEY",
        False,
        None, # we want to make use of the default url which is part of the package
        "gpt-4o-mini",
    )
]

def select_provider() -> Provider:
    for provider in PROVIDERS:
        # For now the custom logic to return a provider is selecting the provider whose api key env is set
        if os.getenv(provider.env_var):
            return provider

    raise RuntimeError("No provider found") # if none is set we raise error

def build_chat_model() -> tuple[ChatOpenAI, Provider]:
    provider = select_provider() # We call the select provider and get the instance of the provider
    kwargs: dict = {
        "model": provider.model,
        "api_key": os.getenv(provider.env_var),
    }
    if provider.base_url is not None:
        kwargs["base_url"] = provider.base_url
    return ChatOpenAI(**kwargs), provider # And instantiate the model and return the provider object
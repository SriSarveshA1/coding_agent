from typing import Any
from langchain.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage

def user_input(text: str) -> dict[str, str]: 
    """
        OpenAI style dict for user input ,
        This method is going to return openAi compatible message dictionary with 'role' as 'user'
     """
    return { "role" : "user", "content": text}

def last_ai_text(messages: list[Any]) -> str:
    """
    When we wanted to retrieve the last AI message text part(non tool call) we can use this function
    """
    for message in reversed(messages): # we travel in a reverse direction, so when we find the first AIMessage with non tool call we return it
        if not isinstance(message, AIMessage):
            continue # if the message is not of AIMessage object type we continue to iteratre over the other messages
        if getattr(message, "tool_calls", None):
            continue # if this current message has a tool_calls property then also we continue iterating


        content = message.content # Message is of AIMessage instance type and we pulled the 'content' part of the message
        if isinstance(content, str): # if that particular content is of string type we just return it
            return content 
        if isinstance(content, list): # if the content is list of blocks/dicts then we iterate them and try to retrieve the
            # dict {} block which has type 'text' (as we are only interested in the text content now) and we are getting the 
            # 'text' property
            parts = [   
                block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text" 
            ]
            # Then atlast we join the array with new line
            return "\n".join(part for part in parts if part)
    return ""


def last_tool_text(messages: list[Any]) -> str:
    """"
    Returns the content of the most recent tool result - useful when the model skips a chat reply.
    """
    for message in reversed(messages): # we iterate the list of messages in the reverse order
        if isinstance(message, ToolMessage): # And check if the message is of ToolMessage instance type and return the content in the string format
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""

def describe_message(message) -> str:
    """Userful for logging and debugging"""
    role = type(message).__name__.replace("Message", "").lower() # type(message).__name___ returns either AIMessage,ToolMessage etc, so we are only keeping the string
                                                                    # by removing the Message part from it. Example: ai,system,tool etc
    content = message.content
    preview = content if isinstance(content, str) else str(content) # converting the format of the content to str if the content is not already 'str'
    preview = preview.replace("\n", " ")
    extra = ""

    if isinstance(message, AIMessage) and message.tool_calls:
        names = ", ".join(call.get("name", "?") for call in message.tool_calls)
        extra = f" tools=[{names}]"
    if isinstance(message, ToolMessage):
        extra = f" tool_call_id={message.tool_call_id}"
    if isinstance(message, SystemMessage):
        extra = " (system)"
    if isinstance(message, HumanMessage):
        extra = " (human)"
    return f"{role}{extra}: {preview}"
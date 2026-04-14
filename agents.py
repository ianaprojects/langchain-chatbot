from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from tools import (
    book_parking_spot,
    search_parking_info,
    get_user_reservation_status,
    debug_runtime_info,
)

from prompts import _ClientAgent_Prompt


def get_base_model():
    return ChatOpenAI(
        model="gpt-5-mini",
        temperature=0,
    )


def create_user_agent():
    model = get_base_model()

    tools = [
        book_parking_spot,
        search_parking_info,
        get_user_reservation_status,
        debug_runtime_info,
    ]

    return create_agent(
        model,
        tools=tools,
        system_prompt=_ClientAgent_Prompt,
        checkpointer=InMemorySaver(),
    )


user_agent = create_user_agent()
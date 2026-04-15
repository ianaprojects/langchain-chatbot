import streamlit as st
from user_agent import user_agent
from chat_streamlit import run_chat

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "user"

config = {"configurable": {"thread_id": st.session_state.thread_id}}

if __name__ == "__main__":
    run_chat(user_agent, config)
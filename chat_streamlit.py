import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from security import protector


def _render_safe_payload(value):
    if isinstance(value, str):
        return protector.render_user_visible_text(value)
    if isinstance(value, dict):
        return {k: _render_safe_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_safe_payload(v) for v in value]
    return value


def get_default_config():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = "user"
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def run_chat(app, config, title="Parking Assistant"):

    st.title(title)

    # Get current graph state.
    try:
        state = app.get_state(config)
    except Exception as e:
        st.error(f"Error while loading conversation state: {e}")
        return

    messages = state.values.get("messages", [])

    # Render conversation history.
    for msg in messages:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.markdown(protector.deanonymize_text(msg.content))
        
        elif isinstance(msg, AIMessage):
            if msg.content:
                with st.chat_message("assistant"):
                    st.markdown(protector.render_user_visible_text(msg.content))
            
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    with st.status(f"Tool request: {tool_call['name']}", state="complete"):
                        st.json(_render_safe_payload(tool_call['args']))
        
        elif isinstance(msg, ToolMessage):
            with st.status(f"Tool result: {msg.name}", state="complete"):
                st.markdown(protector.render_user_visible_text(msg.content))

    if user_input := st.chat_input("Type your message..."):
        with st.chat_message("user"):
            st.markdown(user_input)

        safe_input = protector.anonymize_session(user_input)
        inputs = {"messages": [HumanMessage(content=safe_input)]}

        with st.spinner("Assistant is thinking..."):
            try:
                app.invoke(inputs, config=config)
                st.rerun()
            except Exception as e:
                st.error(f"Agent call failed: {e}")
                st.info("Try rephrasing your request or reloading the page.")


if __name__ == "__main__":
    from agents import user_agent

    run_chat(user_agent, get_default_config())
import streamlit as st
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from genie_agent_local import GenieAgent
import logging
import textwrap


# --------------------------
# Setup
# --------------------------

st.set_page_config(layout="centered")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_user_info():
    headers = st.context.headers
    return dict(
        user_name=headers.get("X-Forwarded-Preferred-Username"),
        user_email=headers.get("X-Forwarded-Email"),
        user_id=headers.get("X-Forwarded-User"),
    )

user_info = get_user_info()

with st.sidebar:
    st.markdown(textwrap.dedent("""
        👤 **User information**  
        (Only available when the app is deployed)
    """))
    st.write(user_info)

    st.markdown(textwrap.dedent("""
        ---
        📦 **About this app**

        This page uses the **`databricks-langchain`** package.  
        
        🔗 Useful links:  
        - [LangChain Databricks integration docs](https://python.langchain.com/docs/integrations/providers/databricks/)  
        - [PyPI package: databricks-langchain](https://pypi.org/project/databricks-langchain/)
    """))

load_dotenv()

# --------------------------
# Build Agent
# --------------------------
assert os.getenv('GENIE_ID'), "GENIE_ID must be set in app.yaml."

agent = GenieAgent(
    os.getenv("GENIE_ID"), "Genie",
    description="This Genie space has access to sales data in Europe"
)

# --------------------------
# Chat UI
# --------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask me about data…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Run through LangGraph agent
    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    # Pick last AI message
    if isinstance(result, dict) and "messages" in result:
        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        reply = ai_msgs[-1].content if ai_msgs else str(result)
    else:
        reply = str(result)

    with st.chat_message("assistant"):
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
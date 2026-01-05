import logging
import os
import streamlit as st
from model_serving_utils import query_endpoint, is_endpoint_supported

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(layout="centered")

# Ensure environment variable is set correctly
SERVING_ENDPOINT = os.getenv('SERVING_ENDPOINT')
assert SERVING_ENDPOINT, \
    ("Unable to determine serving endpoint to use for chatbot app. If developing locally, "
     "set the SERVING_ENDPOINT environment variable to the name of your serving endpoint. If "
     "deploying to a Databricks app, include a serving endpoint resource named "
     "'serving_endpoint' with CAN_QUERY permissions, as described in "
     "https://docs.databricks.com/aws/en/generative-ai/agent-framework/chat-app#deploy-the-databricks-app")

# Check if the endpoint is supported
endpoint_supported = is_endpoint_supported(SERVING_ENDPOINT)

# For your capstone project
def get_user_info():
   headers = st.context.headers
   return dict(
       user_name=headers.get("X-Forwarded-Preferred-Username"),
       user_email=headers.get("X-Forwarded-Email"),
       user_id=headers.get("X-Forwarded-User"),
   )


user_info = get_user_info()

# Streamlit app
if "visibility" not in st.session_state:
    st.session_state.visibility = "visible"
    st.session_state.disabled = False

st.title("🧱 Chatbot App")

# Check if endpoint is supported and show appropriate UI
if not endpoint_supported:
    st.error("⚠️ Unsupported Endpoint Type")
    st.markdown(
        f"The endpoint `{SERVING_ENDPOINT}` is not compatible with this basic chatbot template.\n\n"
        "This template only supports chat completions-compatible endpoints.\n\n"
        "👉 **For a richer chatbot template** that supports all conversational endpoints on Databricks, "
        "please see the [Databricks documentation](https://docs.databricks.com/aws/en/generative-ai/agent-framework/chat-app)."
    )
else:
    st.markdown(
        "ℹ️ This is a simple example. See "
        "[Databricks docs](https://docs.databricks.com/aws/en/generative-ai/agent-framework/chat-app) "
        "for a more comprehensive example with streaming output and more."
    )

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("What is up?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        def build_system_prompt(user_info: dict) -> str:
            """Construct a system prompt including user information."""
            accounts_str = "\n".join([f"- {k}: €{v:,.2f}" for k, v in user_info["accounts"].items()])
            transactions_str = "\n".join([f"{i+1}. {t['merchant']} - €{t['amount']:.2f}" 
                                        for i, t in enumerate(user_info["recent_transactions"])])
            
            prompt = f"""
You are a helpful assistant. Always respond clearly, concisely, and provide actionable information when appropriate.

# User Information
Name: {user_info['name']}
Email: {user_info['email']}
User ID: {user_info['user_id']}

Number of banking accounts: {len(user_info['accounts'])}
Account balances:
{accounts_str}

Recent Transactions:
{transactions_str}

# Banking Preferences
Preferred Contact Method: {user_info['preferences']['contact_method']}
Budgeting Style: {user_info['preferences']['budgeting_style']}

# Context for RAG
You have access to the user's banking info above. When answering questions, reference this data when relevant. 
If the user asks about account balances, recent transactions, or budgeting advice, provide the info from above. 
Do not make up other sensitive data.
"""
            return prompt

        # Build system prompt with user info
        user_info = get_user_info()
        system_prompt = build_system_prompt(user_info)
        print(system_prompt)

        # Display assistant response
        with st.chat_message("assistant"):
            # Query the Databricks serving endpoint with system prompt
            assistant_response = query_endpoint(
                endpoint_name=SERVING_ENDPOINT,
                messages=st.session_state.messages,
                max_tokens=400,
                system_prompt=system_prompt  # <-- pass system prompt here
            )["content"]

            st.markdown(assistant_response)

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

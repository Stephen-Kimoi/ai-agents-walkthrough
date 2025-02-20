import asana
from asana.rest import ApiException
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import json
import os
import streamlit as st

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

load_dotenv() 

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Setting up Asana API client 
configuration = asana.Configuration()
configuration.access_token = os.getenv('ASANA_ACCESS_TOKEN', '')
api_client = asana.ApiClient(configuration)

# Setting up Asana tasks API instance. There are a bunch of APIs that can be used to interact with Asana.
tasks_api_instance = asana.TasksApi(api_client)

# Function that adds tasks to ASANA
@tool # we're telling the agent that the function is a tool that it can invoke
def create_asana_task(task_name, due_on="today", description=None, assignee=None, dependencies=None, custom_fields=None, subtasks=None):
    """
    Creates a task in Asana with enhanced capabilities
    """
    if due_on == "today":
        due_on = str(datetime.now().date())

    task_body = {
        "data": {
            "name": task_name,
            "due_on": due_on,
            "projects": [os.getenv("ASANA_PROJECT_ID", "")]
        }
    }
    
    # Add optional fields if provided
    if description:
        task_body["data"]["notes"] = description
    if assignee:
        task_body["data"]["assignee"] = assignee
    if dependencies:
        task_body["data"]["dependencies"] = dependencies
    if custom_fields:
        task_body["data"]["custom_fields"] = custom_fields

    try:
        # Create main task
        api_response = tasks_api_instance.create_task(task_body, {})
        task_gid = api_response['gid']

         # Create subtasks if provided
        if subtasks:
            for subtask_name in subtasks:
                subtask_body = {
                    "data": {
                        "name": subtask_name,
                        "parent": task_gid,
                        "projects": [os.getenv("ASANA_PROJECT_ID", "")]
                    }
                }
                tasks_api_instance.create_task(subtask_body, {})

        return json.dumps(api_response, indent=2)
    except ApiException as e:
        return f"Exception when calling TasksApi->create_task: {e}"
    
# Function that prompts the AI 
def prompt_ai(messages, nested_calls=0):
    tools = [create_asana_task]
    asana_chatbot = ChatOpenAI(model=model) if "gpt" in model.lower() else ChatAnthropic(model=model)
    asana_chatbot_with_tools = asana_chatbot.bind_tools(tools)

    stream = asana_chatbot_with_tools.stream(messages)
    # then loop over all chunks in the stream
    first = True
    for chunk in stream:
        if first:
            gathered = chunk
            first = False
        else:
            gathered = gathered + chunk

        yield chunk
    
    # tool calls will be in the gathered tool calls
    has_tool_calls = len(gathered.tool_calls) > 0

    # Second, see if the AI decided it needs to invoke a tool
    if has_tool_calls:
        # If the AI decided to invoke a tool, invoke it
        available_functions = {
            "create_asana_task": create_asana_task
        }

        # Add the tool request to the list of messages so the AI knows later it invoked the tool
        messages.append(gathered)

        # Next, for each tool the AI wanted to call, call it and add the tool result to the list of messages
        for tool_call in gathered.tool_calls:
            tool_name = tool_call["name"].lower()
            selected_tool = available_functions[tool_name]
            tool_output = selected_tool.invoke(tool_call["args"])
            messages.append(ToolMessage(tool_output, tool_call_id=tool_call["id"]))     
            
        # Call the AI again so it can produce a response with the result of calling the tool(s)
        additional_stream = prompt_ai(messages, nested_calls + 1)
        for additional_chunk in additional_stream:
            yield additional_chunk
        
def main(): 
    # title that will appear in the ui section
    st.title("Asana with LangChain Chatbot")

    # Initializing session state, everything we're managing in the UI is in the session state
    if "messages" not in st.session_state:
        st.session_state.messages = [
            SystemMessage(content=f"A PA created with Langchain and GPT for managing tasks. The current date is: {datetime.now().date()}")
        ]    

    # display chat from history on app rerun
    for message in st.session_state.messages:
        message_json = json.loads(message.json())
        message_type = message_json["type"]
        if message_type in ["human", "ai", "system"]:
            with st.chat_message(message_type):
                st.markdown(message_json["content"])  
    
    # React to user input
    if prompt := st.chat_input("What would you like to do today?"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append(HumanMessage(content=prompt))

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            stream = prompt_ai(st.session_state.messages)
            # Extract just the content from the response
            response = stream.content if hasattr(stream, 'content') else stream
            st.write(response)
        
        st.session_state.messages.append(AIMessage(content=response))

    

if __name__ == "__main__":
    main()
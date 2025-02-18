import asana
from asana.rest import ApiException
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import json
import os

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

    
def get_tools():
    # Tools is an array where each item is an array that defines the function the AI LLM can call 
    tools = [
        {
            "type": "function",
            "function": {
                "name": "create_asana_task",
                "description": "Creates a task in Asana with full details including description, assignee, dependencies, custom fields, and subtasks",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_name": {
                            "type": "string",
                            "description": "The name of the task in Asana"
                        },
                        "due_on": {
                            "type": "string",
                            "description": "The date the task is due in format YYYY-MM-DD"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description/notes for the task"
                        },
                        "assignee": {
                            "type": "string",
                            "description": "Asana user GID to assign the task to"
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of task GIDs that this task depends on"
                        },
                        "custom_fields": {
                            "type": "object",
                            "description": "Dictionary of custom field GIDs and their values"
                        },
                        "subtasks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of subtask names to create"
                        }
                    },
                    "required": ["task_name"]
                },
            },
        }
    ]

    return tools   
    
# Function that prompts the AI 
def prompt_ai(messages):
    # First, we'll prompt the AI with the latest user's message
    completion = client.chat.completions.create(
        model=model,
        messages=messages, # list of all messages, not just the latest
        tools=get_tools()  # This is what makes it an AI agent, it's the functions that it runs to do things interactively in the outside world
    )

    response_message = completion.choices[0].message
    tool_calls = response_message.tool_calls

    # Second, see if the AI decided it needs to invoke a tool
    if tool_calls:
        # If the AI decided to invoke a tool, invoke it
        available_functions = {
            "create_asana_task": create_asana_task
        }

        # Add the tool request to the list of messages so the AI knows later it invoked the tool
        messages.append(response_message)

        # Next, for each tool the AI wanted to call, call it and add the tool result to the list of messages
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)
            function_response = function_to_call(**function_args)

            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": function_response
            })
        
        # Call the AI again so it can produce a response with the result of calling the tool(s)
        second_response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        
        # return it to the system message so that we add it to the chat history
        return second_response.choices[0].message.content 

    return response_message.content

    

def main(): 
    # Each message has one of 3 roles: 
       # 1. System Role: it is background context with AI 
       # 2. User Role: means the message is from the user 
       # 3. Assistant Role: means it is the response from the AI 

    # the AI needs to know the current dates to put on the due dates for the tasks
    messages = [
        {
            "role": "system",
            "content": f"You are a personal assistant who helps manage tasks in Asana. The current date is: {datetime.now().date()}"
        }
    ]
    
    # Loop forever and ask the user for another message to send to the AI. If I type 'q' then I quit.
    while True:
        user_input = input("Chat with AI (q to quit): ").strip()
        
        if user_input == 'q':
            break  
        
        # Once we get the input from the users, we'll add it to the messages list. Content of the message is the user's input.
        messages.append({"role": "user", "content": user_input})
        # We'll create a function "prompt_ai" that will take the messages list and send it to the AI.
        ai_response = prompt_ai(messages)
         
        # We'll print the response then add the AI's response to the messages list.
        print(ai_response)
        messages.append({"role": "assistant", "content": ai_response})
    

if __name__ == "__main__":
    main()
from github import Github
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import json
import os

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
model = os.getenv('OPENAI_MODEL', 'gpt-4')

# Setting up GitHub client
g = Github(os.getenv('GITHUB_TOKEN'))
repo = g.get_repo(os.getenv('GITHUB_REPO'))

def create_github_issue(title, body=None, labels=None, assignee=None, milestone=None):
    """
    Creates a GitHub issue with enhanced capabilities
    """
    try:
        print(f"Creating issue in repository: {os.getenv('GITHUB_REPO')}")
        print(f"Using title: {title}")
        print(f"With labels: {labels}")
        
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=labels,
            assignee=assignee,
            milestone=milestone
        )
        print(f"Issue created with ID: {issue.id}")
        print(f"Issue URL: {issue.html_url}")
        return json.dumps(issue.raw_data, indent=2)
    except Exception as e:
        print(f"Full error details: {str(e)}")
        return f"Exception details when creating GitHub issue: {str(e)}"

def create_pull_request(title, body=None, base="main", head=None, draft=False):
    """
    Creates a GitHub Pull Request
    """
    try:
        pr = repo.create_pull(
            title=title,
            body=body,
            base=base,
            head=head,
            draft=draft
        )
        return json.dumps(pr.raw_data, indent=2)
    except Exception as e:
        return f"Exception when creating Pull Request: {e}"

def get_tools():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "create_github_issue",
                "description": "Creates a GitHub issue with title, description, labels, assignee and milestone",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "The title of the GitHub issue"
                        },
                        "body": {
                            "type": "string",
                            "description": "The description/body of the issue in markdown format"
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of labels to apply to the issue"
                        },
                        "assignee": {
                            "type": "string",
                            "description": "GitHub username to assign the issue to"
                        },
                        "milestone": {
                            "type": "string",
                            "description": "Milestone ID to associate with the issue"
                        }
                    },
                    "required": ["title"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_pull_request",
                "description": "Creates a GitHub Pull Request",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "The title of the Pull Request"
                        },
                        "body": {
                            "type": "string",
                            "description": "The description/body of the PR in markdown format"
                        },
                        "base": {
                            "type": "string",
                            "description": "The name of the branch to merge into"
                        },
                        "head": {
                            "type": "string",
                            "description": "The name of the branch where changes are implemented"
                        },
                        "draft": {
                            "type": "boolean",
                            "description": "Whether to create the pull request as a draft"
                        }
                    },
                    "required": ["title", "head"]
                }
            }
        }
    ]
    return tools

def prompt_ai(messages):
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=get_tools()
    )

    response_message = completion.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls:
        available_functions = {
            "create_github_issue": create_github_issue,
            "create_pull_request": create_pull_request
        }

        messages.append(response_message)

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

        second_response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        
        return second_response.choices[0].message.content

    return response_message.content

def main():
    messages = [
        {
            "role": "system",
            "content": f"You are a GitHub assistant who helps manage issues and pull requests. The current date is: {datetime.now().date()}"
        }
    ]
    
    while True:
        user_input = input("Chat with AI (q to quit): ").strip()
        
        if user_input == 'q':
            break
        
        messages.append({"role": "user", "content": user_input})
        ai_response = prompt_ai(messages)
        print(ai_response)
        messages.append({"role": "assistant", "content": ai_response})

if __name__ == "__main__":
    main()
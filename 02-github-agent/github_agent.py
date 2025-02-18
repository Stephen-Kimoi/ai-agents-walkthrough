from github import Github
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import json
import os

load_dotenv()

print(f"Using repo: {os.getenv('GITHUB_REPO')}")
print(f"Token exists: {bool(os.getenv('GITHUB_TOKEN'))}")

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
model = os.getenv('OPENAI_MODEL', 'gpt-4')

# Setting up GitHub client
g = Github(os.getenv('GITHUB_TOKEN'))
repo = g.get_repo(os.getenv('GITHUB_REPO'))

def verify_github_connection():
    print("Verifying GitHub connection...")
    print(f"Authenticated user: {g.get_user().login}")
    print(f"Repository access: {repo.full_name}")
    return True

verify_github_connection()

def create_github_issue(title, body=None, labels=None, assignee=None, milestone=None):
    try:
        print("Starting issue creation...")
        print(f"Repository object exists: {repo is not None}")
        print(f"Attempting to create issue with title: {title}")
        
        # Print exact parameters being sent to API
        print("API Parameters:")
        print(f"Title: {title}")
        print(f"Body: {body}")
        print(f"Labels: {labels}")
        print(f"Assignee: {assignee}")
        
        # Create issue with minimal parameters first
        issue = repo.create_issue(
            title=title,
            body=body if body else "No description provided"
        )
        
        print(f"Issue successfully created!")
        print(f"Issue ID: {issue.id}")
        print(f"Issue URL: {issue.html_url}")
        return json.dumps(issue.raw_data, indent=2)
    except Exception as e:
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        print(f"Full error stack: ", e.__traceback__)
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
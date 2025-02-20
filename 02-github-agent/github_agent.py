from github import Github
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import json
import os

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

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

@tool
def create_github_issue(title, body=None, labels=None, assignee=None, milestone=None):
    """
    Creates a GitHub issue with enhanced capabilities.
    
    Args:
        title (str): The title of the GitHub issue
        body (str, optional): The description/body of the issue in markdown format
        labels (list, optional): List of labels to apply to the issue
        assignee (str, optional): GitHub username to assign the issue to
        milestone (str, optional): Milestone ID to associate with the issue
    
    Returns:
        str: JSON string containing the created issue data
    """
    try:
        print("Starting issue creation...")
        print(f"Repository object exists: {repo is not None}")
        print(f"Attempting to create issue with title: {title}")
        
        issue = repo.create_issue(
            title=title,
            body=body if body else "No description provided",
            labels=labels,
            assignee=assignee,
            milestone=milestone
        )
        
        print(f"Issue successfully created!")
        print(f"Issue ID: {issue.id}")
        print(f"Issue URL: {issue.html_url}")
        return json.dumps(issue.raw_data, indent=2)
    except Exception as e:
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return f"Exception details when creating GitHub issue: {str(e)}"

@tool
def create_pull_request(title, body=None, base="main", head=None, draft=False):
    """
    Creates a GitHub Pull Request with specified parameters.
    
    Args:
        title (str): The title of the Pull Request
        body (str, optional): The description/body of the PR in markdown format
        base (str, optional): The name of the branch to merge into (default: main)
        head (str): The name of the branch where changes are implemented
        draft (bool, optional): Whether to create the pull request as a draft
    
    Returns:
        str: JSON string containing the created PR data
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

def prompt_ai(messages):
    tools = [create_github_issue, create_pull_request]
    github_chatbot = ChatOpenAI(model=os.getenv('OPENAI_MODEL', 'gpt-4'))
    github_chatbot_with_tools = github_chatbot.bind_tools(tools)

    ai_response = github_chatbot_with_tools.invoke(messages)
    print("AI response is: ", ai_response)
    
    if hasattr(ai_response, 'tool_calls') and ai_response.tool_calls:
        for tool_call in ai_response.tool_calls:
            # The logs show tool_call has 'name' and 'args' directly
            function_name = tool_call['name']
            function_args = tool_call['args']
            
            if function_name == 'create_pull_request':
                result = create_pull_request.invoke(function_args)
                return f"Pull request created successfully: {result}"
            elif function_name == 'create_github_issue':
                result = create_github_issue.invoke(function_args)
                return f"Issue created successfully: {result}"
    
    return ai_response.content

def main():
    messages = [
        SystemMessage(content=f"""You are a GitHub assistant who helps manage issues and pull requests. 
        When creating PRs, always use the create_pull_request tool and provide clear feedback about the result. 
        The current date is: {datetime.now().date()}""")
    ]
    
    while True:
        user_input = input("Chat with AI (q to quit): ").strip()
        
        if user_input == 'q':
            break
        
        messages.append(HumanMessage(content=user_input))
        ai_response = prompt_ai(messages)
        messages.append({"role": "assistant", "content": ai_response})

if __name__ == "__main__":
    main()
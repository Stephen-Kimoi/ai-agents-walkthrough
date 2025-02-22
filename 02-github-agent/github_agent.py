from github import Github
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import json
import os
import streamlit as st

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

load_dotenv()

# print(f"Using repo: {os.getenv('GITHUB_REPO')}")
print(f"Token exists: {bool(os.getenv('GITHUB_TOKEN'))}")

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Setting up GitHub client
# g = Github(os.getenv('GITHUB_TOKEN'))

def verify_github_connection():
    print(f"Authenticated user: {g.get_user().login}")
    print(f"Repository access: {repo.full_name}")
    return True

def generate_pr_description(head_branch):
    """Generates PR description based on branch commits"""
    try:
        # Get commits in the branch
        commits = repo.get_commits(sha=head_branch)
        commit_messages = [commit.commit.message for commit in commits]
        
        # Use OpenAI to generate a meaningful description
        description_prompt = "Based on these commit messages, generate a clear PR description: " + '\n'.join(commit_messages) + "\n\nFocus on:\n- Main changes implemented\n- Key features or fixes\n- Any breaking changes"
        
        chatbot = ChatOpenAI(model=os.getenv('OPENAI_MODEL', 'gpt-4'))
        response = chatbot.invoke([HumanMessage(content=description_prompt)])
        
        return response.content
    except Exception as e:
        return f"Could not generate description from commits. Using default description. Error: {str(e)}"

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
    """
    try:
        print("Starting Pull Request creation...")
        print(f"Repository object exists: {repo is not None}")
        print(f"Attempting to create Pull Request with title: {title}")
        print(f"Base branch: {base}")
        print(f"Head branch: {head}")
        # Validate head branch exists
        if not head:
            return "Error: Head branch name is required"
        
        # Generate description from commits if no body provided
        if not body:
            body = generate_pr_description(head)

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
    github_chatbot = ChatOpenAI(model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'))
    github_chatbot_with_tools = github_chatbot.bind_tools(tools)

    ai_response = github_chatbot_with_tools.invoke(messages)
    print(f"AI response: {ai_response}")
    
    if hasattr(ai_response, 'tool_calls') and ai_response.tool_calls:
        for tool_call in ai_response.tool_calls:
            function_name = tool_call['name']
            function_args = tool_call['args']
            
            try:
                if function_name == 'create_pull_request':
                    function_response = create_pull_request.invoke(function_args)
                    if isinstance(function_response, str) and function_response.startswith('Exception'):
                        return function_response
                    result = json.loads(function_response)
                    return f"✨ Pull request created successfully!\n\nTitle: {result['title']}\nURL: {result['html_url']}\nStatus: {result['state']}"
                    
                elif function_name == 'create_github_issue':
                    function_response = create_github_issue.invoke(function_args)
                    if isinstance(function_response, str) and function_response.startswith('Exception'):
                        return function_response
                    result = json.loads(function_response)
                    return f"✨ Issue created successfully!\n\nTitle: {result['title']}\nURL: {result['html_url']}\nStatus: {result['state']}"
            except json.JSONDecodeError:
                return f"Error processing {function_name}: Invalid response format"
            except Exception as e:
                return f"Error executing {function_name}: {str(e)}"
    
    return ai_response.content

def main():
    st.title("GitHub PR assistant")

    # Repository input at the top
    if "github_repo" not in st.session_state:
        st.session_state.github_repo = ""
    
    repo_input = st.text_input(
        "Enter GitHub repository (format: username/repo)", 
        value=st.session_state.github_repo
    )

    # GitHub token input
    if "github_token" not in st.session_state:
        st.session_state.github_token = ""
    
    token_input = st.text_input(
        "Enter your GitHub token",
        value=st.session_state.github_token,
        type="password"  # This masks the token for security
    )
    
    if repo_input and token_input:
        st.session_state.github_repo = repo_input
        st.session_state.github_token = token_input

        with st.spinner('Verifying GitHub connection...'):
            global repo, g
            g = Github(token_input)
            repo = g.get_repo(repo_input)
            verify_github_connection()
            st.success('✅ GitHub connection verified successfully!')

        # Only show chat interface after repo is selected
        if "messages" not in st.session_state:
            st.session_state.messages = [
                SystemMessage(content=f"""I am a GitHub assistant that helps you manage issues and pull requests. 
                I can create new issues, open pull requests, and provide clear feedback with URLs. 
                Today's date is: {datetime.now().date()}""")
            ]

        for message in st.session_state.messages:
            message_json = json.loads(message.json())
            message_type = message_json["type"]
            if message_type in ["human", "ai", "system"]:
                with st.chat_message(message_type):
                    st.markdown(message_json["content"])

        if prompt := st.chat_input("What would you like to do?"):
            st.chat_message("user").markdown(prompt)
            st.session_state.messages.append(HumanMessage(content=prompt))

            with st.chat_message("assistant"):
                response = prompt_ai(st.session_state.messages)
                st.markdown(response)
            
            st.session_state.messages.append(HumanMessage(content=response))
    else:
        st.info("👆 Enter a GitHub repository and token to start managing issues and pull requests")

if __name__ == "__main__":
    main()
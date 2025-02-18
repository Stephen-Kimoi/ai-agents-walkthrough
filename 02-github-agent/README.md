# GitHub Agent: 
Directly create issues or submit PRs of your projects on GitHub without leaving the terminal.

### Getting started: 

1. Clone the repository:
```bash
git clone https://github.com/your-username/github-agent.git
cd github-agent
```

2. Create the virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate # for macOS/Linux
venv\Scripts\activate # for Windows
```

3. Install the dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the `.env.example` file to `.env` and fill in the required information.

5. Run the agent: 
```bash
python3 github_agent.py 
``` 
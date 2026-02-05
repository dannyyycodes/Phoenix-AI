"""
Phoenix AI Brain
Claude-powered AI with tool use for code generation, deployments, and more
"""

import os
import json
import httpx
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime


class PhoenixBrain:
    """AI brain powered by Claude via OpenRouter with tool use"""

    def __init__(self, memory_manager, github_client=None, railway_client=None):
        self.api_key = os.environ.get('OPENROUTER_API_KEY')
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "anthropic/claude-sonnet-4"  # Best balance of speed/capability

        self.memory = memory_manager
        self.github = github_client
        self.railway = railway_client

        # Active context
        self.active_project_id = None

        # Tool definitions
        self.tools = self._define_tools()

        # System prompt
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return """You are Phoenix AI, a personal development assistant accessible via Telegram.

Your capabilities:
- Build websites, apps, and automations from scratch
- Write, commit, and deploy code
- Monitor and fix production systems
- Remember all conversations and project context
- Execute approved actions on user's infrastructure

Your personality:
- Concise but thorough - respect that user is on mobile
- Proactive - suggest improvements and catch potential issues
- Safety-conscious - always explain risks before dangerous actions
- Context-aware - remember past conversations and preferences

Key behaviors:
1. For ANY action that modifies code, deploys, or costs money: Request approval first
2. Keep responses mobile-friendly (short paragraphs, use formatting)
3. When building something new, confirm tech stack and approach first
4. Always provide status updates for long-running operations
5. If something fails, diagnose and suggest fixes automatically

You have access to tools for:
- Reading and writing code via GitHub
- Deploying to Railway
- Checking project status
- Managing databases
- And more

The user trusts you but wants approval before major actions.
When you need approval, clearly state:
- What you want to do
- Why
- Any risks
- Expected outcome

Current date/time: """ + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def _define_tools(self) -> List[Dict]:
        """Define available tools for Claude"""
        return [
            {
                "name": "read_file",
                "description": "Read a file from a GitHub repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository name (e.g., 'owner/repo')"},
                        "path": {"type": "string", "description": "File path in the repository"},
                        "branch": {"type": "string", "description": "Branch name (default: main)"}
                    },
                    "required": ["repo", "path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write or update a file in a GitHub repository. REQUIRES APPROVAL.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository name"},
                        "path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "File content"},
                        "message": {"type": "string", "description": "Commit message"},
                        "branch": {"type": "string", "description": "Branch name (default: main)"}
                    },
                    "required": ["repo", "path", "content", "message"]
                }
            },
            {
                "name": "create_repository",
                "description": "Create a new GitHub repository. REQUIRES APPROVAL.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Repository name"},
                        "description": {"type": "string", "description": "Repository description"},
                        "private": {"type": "boolean", "description": "Whether the repo should be private"}
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "list_repos",
                "description": "List user's GitHub repositories",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max repos to return (default: 10)"}
                    }
                }
            },
            {
                "name": "deploy_to_railway",
                "description": "Deploy a GitHub repo to Railway. REQUIRES APPROVAL.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "GitHub repo to deploy"},
                        "project_name": {"type": "string", "description": "Railway project name"},
                        "env_vars": {"type": "object", "description": "Environment variables to set"}
                    },
                    "required": ["repo"]
                }
            },
            {
                "name": "get_railway_status",
                "description": "Get deployment status and logs from Railway",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "Railway project ID"}
                    },
                    "required": ["project_id"]
                }
            },
            {
                "name": "get_railway_logs",
                "description": "Get recent logs from a Railway deployment",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "Railway project ID"},
                        "lines": {"type": "integer", "description": "Number of log lines (default: 50)"}
                    },
                    "required": ["project_id"]
                }
            },
            {
                "name": "set_railway_env",
                "description": "Set environment variable in Railway. REQUIRES APPROVAL.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "Railway project ID"},
                        "key": {"type": "string", "description": "Environment variable name"},
                        "value": {"type": "string", "description": "Environment variable value"}
                    },
                    "required": ["project_id", "key", "value"]
                }
            },
            {
                "name": "redeploy_railway",
                "description": "Trigger a redeployment on Railway. REQUIRES APPROVAL.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "Railway project ID"}
                    },
                    "required": ["project_id"]
                }
            },
            {
                "name": "check_omni_agent",
                "description": "Check status of the Omni-Agent animal facts automation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "check_type": {
                            "type": "string",
                            "enum": ["health", "tasks", "scheduler", "status"],
                            "description": "What to check"
                        }
                    },
                    "required": ["check_type"]
                }
            },
            {
                "name": "retry_omni_task",
                "description": "Retry a failed task in Omni-Agent",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID to retry"}
                    },
                    "required": ["task_id"]
                }
            },
            {
                "name": "run_animal_facts",
                "description": "Trigger a new animal facts video generation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dry_run": {"type": "boolean", "description": "If true, don't post to social media"}
                    }
                }
            },
            {
                "name": "search_memory",
                "description": "Search past conversations for relevant context",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_projects",
                "description": "List all user projects",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Filter by status (active, completed, archived)"}
                    }
                }
            },
            {
                "name": "switch_project",
                "description": "Switch context to a different project",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "Project name to switch to"}
                    },
                    "required": ["project_name"]
                }
            },
            {
                "name": "create_project",
                "description": "Create a new project to work on",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Project name"},
                        "description": {"type": "string", "description": "Project description"},
                        "tech_stack": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Technologies to use"
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "request_approval",
                "description": "Request user approval for an action",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action_type": {"type": "string", "description": "Type of action (deploy, commit, delete, etc.)"},
                        "description": {"type": "string", "description": "What will be done"},
                        "risks": {"type": "string", "description": "Any risks to mention"},
                        "payload": {"type": "object", "description": "Action data to execute if approved"}
                    },
                    "required": ["action_type", "description", "payload"]
                }
            }
        ]

    async def think(self, user_id: str, message: str,
                   context_override: List[Dict] = None) -> Dict[str, Any]:
        """
        Process a user message and generate a response.
        Returns: {
            'response': str,
            'tool_calls': list,
            'requires_approval': bool,
            'approval_request': dict or None
        }
        """
        # Get conversation history
        if context_override:
            messages = context_override
        else:
            messages = self.memory.get_conversation_for_context(user_id)

        # Add user preferences to system prompt
        preferences = self.memory.get_preferences(user_id)
        system = self.system_prompt + f"\n\nUser preferences: {json.dumps(preferences)}"

        # Add active project context
        if self.active_project_id:
            project = self.memory.get_project(self.active_project_id)
            if project:
                system += f"\n\nActive project: {project['name']}\n"
                system += f"Description: {project['description']}\n"
                system += f"Tech stack: {', '.join(project['tech_stack'])}\n"
                system += f"Status: {project['status']}\n"
                if project['current_task']:
                    system += f"Current task: {project['current_task']}\n"
                if project['github_repo']:
                    system += f"GitHub: {project['github_repo']}\n"
                if project['deployment_url']:
                    system += f"Deployed at: {project['deployment_url']}\n"

        # Add current message
        messages.append({"role": "user", "content": message})

        # Store user message
        self.memory.add_message(user_id, "user", message, self.active_project_id)

        # Call Claude via OpenRouter
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://phoenix-ai.railway.app",
                    "X-Title": "Phoenix AI"
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "messages": [{"role": "system", "content": system}] + messages,
                    "tools": self._convert_tools_for_openrouter(),
                }
            )
            data = response.json()

        # Process response
        result = {
            'response': '',
            'tool_calls': [],
            'requires_approval': False,
            'approval_request': None
        }

        if 'error' in data:
            result['response'] = f"AI Error: {data['error'].get('message', 'Unknown error')}"
            return result

        choice = data.get('choices', [{}])[0]
        message_content = choice.get('message', {})

        # Extract text response
        if message_content.get('content'):
            result['response'] = message_content['content']

        # Extract tool calls
        if message_content.get('tool_calls'):
            for tool_call in message_content['tool_calls']:
                func = tool_call.get('function', {})
                tool_name = func.get('name', '')
                try:
                    tool_input = json.loads(func.get('arguments', '{}'))
                except:
                    tool_input = {}

                result['tool_calls'].append({
                    'id': tool_call.get('id', ''),
                    'name': tool_name,
                    'input': tool_input
                })

                # Check if this tool requires approval
                if self._requires_approval(tool_name):
                    result['requires_approval'] = True
                    result['approval_request'] = {
                        'tool': tool_name,
                        'input': tool_input
                    }

        # Store assistant response
        self.memory.add_message(
            user_id, "assistant", result['response'],
            self.active_project_id,
            tool_calls=result['tool_calls'] if result['tool_calls'] else None
        )

        return result

    def _convert_tools_for_openrouter(self) -> List[Dict]:
        """Convert Anthropic-style tools to OpenRouter/OpenAI format"""
        openrouter_tools = []
        for tool in self.tools:
            openrouter_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            })
        return openrouter_tools

    def _requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval"""
        approval_required = [
            'write_file',
            'create_repository',
            'deploy_to_railway',
            'set_railway_env',
            'redeploy_railway',
            'request_approval'
        ]
        return tool_name in approval_required

    async def execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """Execute a tool and return the result"""
        try:
            if tool_name == "read_file":
                return await self._tool_read_file(**tool_input)
            elif tool_name == "write_file":
                return await self._tool_write_file(**tool_input)
            elif tool_name == "create_repository":
                return await self._tool_create_repo(**tool_input)
            elif tool_name == "list_repos":
                return await self._tool_list_repos(**tool_input)
            elif tool_name == "deploy_to_railway":
                return await self._tool_deploy_railway(**tool_input)
            elif tool_name == "get_railway_status":
                return await self._tool_railway_status(**tool_input)
            elif tool_name == "get_railway_logs":
                return await self._tool_railway_logs(**tool_input)
            elif tool_name == "set_railway_env":
                return await self._tool_set_env(**tool_input)
            elif tool_name == "redeploy_railway":
                return await self._tool_redeploy(**tool_input)
            elif tool_name == "check_omni_agent":
                return await self._tool_check_omni(**tool_input)
            elif tool_name == "retry_omni_task":
                return await self._tool_retry_omni(**tool_input)
            elif tool_name == "run_animal_facts":
                return await self._tool_run_animal_facts(**tool_input)
            elif tool_name == "search_memory":
                return await self._tool_search_memory(**tool_input)
            elif tool_name == "get_projects":
                return await self._tool_get_projects(**tool_input)
            elif tool_name == "switch_project":
                return await self._tool_switch_project(**tool_input)
            elif tool_name == "create_project":
                return await self._tool_create_project(**tool_input)
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    # Tool implementations
    async def _tool_read_file(self, repo: str, path: str, branch: str = "main") -> str:
        if not self.github:
            return "GitHub integration not configured"
        try:
            content = self.github.get_file_content(repo, path, branch)
            return f"File content of {path}:\n```\n{content}\n```"
        except Exception as e:
            return f"Error reading file: {e}"

    async def _tool_write_file(self, repo: str, path: str, content: str,
                              message: str, branch: str = "main") -> str:
        if not self.github:
            return "GitHub integration not configured"
        try:
            result = self.github.write_file(repo, path, content, message, branch)
            return f"File written successfully: {result}"
        except Exception as e:
            return f"Error writing file: {e}"

    async def _tool_create_repo(self, name: str, description: str = "",
                               private: bool = False) -> str:
        if not self.github:
            return "GitHub integration not configured"
        try:
            repo = self.github.create_repo(name, description, private)
            return f"Repository created: {repo['html_url']}"
        except Exception as e:
            return f"Error creating repo: {e}"

    async def _tool_list_repos(self, limit: int = 10) -> str:
        if not self.github:
            return "GitHub integration not configured"
        try:
            repos = self.github.list_repos(limit)
            lines = [f"- {r['name']}: {r['description'] or 'No description'}" for r in repos]
            return "Your repositories:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing repos: {e}"

    async def _tool_deploy_railway(self, repo: str, project_name: str = None,
                                  env_vars: dict = None) -> str:
        if not self.railway:
            return "Railway integration not configured"
        # This would integrate with Railway API
        return f"Deployment initiated for {repo}"

    async def _tool_railway_status(self, project_id: str) -> str:
        if not self.railway:
            return "Railway integration not configured"
        try:
            status = self.railway.get_project_status(project_id)
            return f"Railway project status:\n{json.dumps(status, indent=2)}"
        except Exception as e:
            return f"Error getting status: {e}"

    async def _tool_railway_logs(self, project_id: str, lines: int = 50) -> str:
        if not self.railway:
            return "Railway integration not configured"
        try:
            logs = self.railway.get_logs(project_id, lines)
            return f"Recent logs:\n{logs}"
        except Exception as e:
            return f"Error getting logs: {e}"

    async def _tool_set_env(self, project_id: str, key: str, value: str) -> str:
        if not self.railway:
            return "Railway integration not configured"
        try:
            self.railway.set_env_var(project_id, key, value)
            return f"Environment variable {key} set successfully"
        except Exception as e:
            return f"Error setting env var: {e}"

    async def _tool_redeploy(self, project_id: str) -> str:
        if not self.railway:
            return "Railway integration not configured"
        try:
            self.railway.redeploy(project_id)
            return "Redeployment triggered"
        except Exception as e:
            return f"Error triggering redeploy: {e}"

    async def _tool_check_omni(self, check_type: str) -> str:
        import httpx
        base_url = "https://web-production-770b9.up.railway.app"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if check_type == "health":
                    r = await client.get(f"{base_url}/health")
                    return f"Omni-Agent health: {r.json()}"
                elif check_type == "status":
                    r = await client.get(f"{base_url}/api/status")
                    return f"Omni-Agent status: {json.dumps(r.json(), indent=2)}"
                elif check_type == "tasks":
                    r = await client.get(f"{base_url}/api/tasks")
                    return f"Pending tasks: {json.dumps(r.json(), indent=2)}"
                elif check_type == "scheduler":
                    r = await client.get(f"{base_url}/api/scheduler/logs?limit=10")
                    return f"Recent scheduler runs: {json.dumps(r.json(), indent=2)}"
        except Exception as e:
            return f"Error checking Omni-Agent: {e}"

    async def _tool_retry_omni(self, task_id: str) -> str:
        import httpx
        base_url = "https://web-production-770b9.up.railway.app"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{base_url}/api/tasks/{task_id}/retry")
                return f"Retry result: {r.json()}"
        except Exception as e:
            return f"Error retrying task: {e}"

    async def _tool_run_animal_facts(self, dry_run: bool = True) -> str:
        import httpx
        base_url = "https://web-production-770b9.up.railway.app"

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{base_url}/api/animal-facts/run",
                    json={"dry_run": dry_run}
                )
                return f"Animal facts triggered: {json.dumps(r.json(), indent=2)}"
        except Exception as e:
            return f"Error running animal facts: {e}"

    async def _tool_search_memory(self, query: str) -> str:
        # This would need user_id from context
        return "Memory search not available in this context"

    async def _tool_get_projects(self, status: str = None) -> str:
        # This would need user_id from context
        return "Project listing not available in this context"

    async def _tool_switch_project(self, project_name: str) -> str:
        # This would need user_id from context
        return "Project switching not available in this context"

    async def _tool_create_project(self, name: str, description: str = None,
                                  tech_stack: list = None) -> str:
        # This would need user_id from context
        return "Project creation not available in this context"

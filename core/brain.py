"""
Phoenix AI Brain
Claude-powered AI with tool use for code generation, deployments, and more
"""

import os
import json
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime


class PhoenixBrain:
    """AI brain powered by Claude via OpenRouter with tool use"""

    def __init__(self, memory_manager, github_client=None, railway_client=None):
        self.api_key = os.environ.get('OPENROUTER_API_KEY')
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "anthropic/claude-sonnet-4"

        self.memory = memory_manager
        self.github = github_client
        self.railway = railway_client
        self.active_project_id = None

        # Known projects context
        self.omni_agent_url = "https://web-production-770b9.up.railway.app"

    def _get_system_prompt(self) -> str:
        return f"""You are Phoenix AI, a personal development assistant on Telegram.

## YOUR CAPABILITIES
You can execute real actions using tools. When the user asks you to do something, USE THE TOOLS to actually do it.

## KNOWN PROJECTS
1. **Omni-Agent (Animal Facts Automation)**
   - URL: {self.omni_agent_url}
   - Purpose: Generates animal facts videos using Sora 2 via Kie.ai
   - Features: Auto-posts to TikTok, Instagram, YouTube Shorts
   - Schedule: Every 6 hours (4 posts per day)
   - Endpoints:
     - /health - Check if running
     - /api/animal-facts/preview - Generate preview without posting
     - /api/animal-facts/run - Generate and post video
     - /api/tasks - View pending video tasks
     - /api/scheduler/logs - View recent runs

## IMPORTANT BEHAVIOR
1. When asked about animal facts or Omni-Agent, USE the check_omni_agent tool
2. When asked to run/trigger the automation, USE the run_animal_facts tool
3. ALWAYS execute tools when the user asks you to DO something
4. After getting tool results, summarize them clearly for the user
5. Be concise - user is on mobile

## Current Time: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}"""

    def _get_tools(self) -> List[Dict]:
        """Tools in OpenAI format for OpenRouter"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "check_omni_agent",
                    "description": "Check status of the Omni-Agent animal facts automation. Use this when user asks about animal facts, video status, or the automation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "check_type": {
                                "type": "string",
                                "enum": ["health", "tasks", "scheduler", "all"],
                                "description": "What to check: health (is it running), tasks (pending videos), scheduler (recent runs), all (everything)"
                            }
                        },
                        "required": ["check_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_animal_facts",
                    "description": "Trigger a new animal facts video generation. Use when user wants to create/run/test the animal facts automation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dry_run": {
                                "type": "boolean",
                                "description": "If true, generates video but doesn't post to social media. Default true for safety."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_omni_logs",
                    "description": "Get recent scheduler logs showing what videos were generated",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Number of log entries to fetch (default 10)"
                            }
                        }
                    }
                }
            }
        ]

    async def think(self, user_id: str, user_message: str) -> str:
        """
        Process user message with full agentic loop.
        Returns the final response to send to user.
        """
        # Build conversation with context
        messages = self.memory.get_conversation_for_context(user_id, max_tokens=10000)
        messages.append({"role": "user", "content": user_message})

        # Store user message
        self.memory.add_message(user_id, "user", user_message)

        # Agentic loop - keep going until we get a final response
        max_iterations = 5
        for i in range(max_iterations):
            # Call Claude
            response = await self._call_claude(messages)

            if 'error' in response:
                return f"Error: {response['error']}"

            assistant_message = response.get('choices', [{}])[0].get('message', {})

            # Check for tool calls
            tool_calls = assistant_message.get('tool_calls', [])

            if tool_calls:
                # Add assistant message with tool calls to conversation
                messages.append(assistant_message)

                # Execute each tool and add results
                for tool_call in tool_calls:
                    func = tool_call.get('function', {})
                    tool_name = func.get('name', '')

                    try:
                        args = json.loads(func.get('arguments', '{}'))
                    except:
                        args = {}

                    # Execute the tool
                    tool_result = await self._execute_tool(tool_name, args)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get('id', ''),
                        "content": tool_result
                    })
            else:
                # No tool calls - we have the final response
                final_response = assistant_message.get('content', 'I processed your request.')
                self.memory.add_message(user_id, "assistant", final_response)
                return final_response

        return "I'm having trouble completing this request. Please try again."

    async def _call_claude(self, messages: List[Dict]) -> Dict:
        """Make API call to Claude via OpenRouter"""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
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
                        "max_tokens": 2048,
                        "messages": [{"role": "system", "content": self._get_system_prompt()}] + messages,
                        "tools": self._get_tools(),
                    }
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def _execute_tool(self, tool_name: str, args: Dict) -> str:
        """Execute a tool and return result as string"""
        try:
            if tool_name == "check_omni_agent":
                return await self._tool_check_omni(args.get('check_type', 'all'))
            elif tool_name == "run_animal_facts":
                return await self._tool_run_animal_facts(args.get('dry_run', True))
            elif tool_name == "get_omni_logs":
                return await self._tool_get_logs(args.get('limit', 10))
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Tool error: {str(e)}"

    async def _tool_check_omni(self, check_type: str) -> str:
        """Check Omni-Agent status"""
        results = []

        async with httpx.AsyncClient(timeout=15) as client:
            if check_type in ['health', 'all']:
                try:
                    r = await client.get(f"{self.omni_agent_url}/health")
                    health = r.json()
                    results.append(f"Health: {health.get('status', 'unknown')}")
                except Exception as e:
                    results.append(f"Health: ERROR - {e}")

            if check_type in ['tasks', 'all']:
                try:
                    r = await client.get(f"{self.omni_agent_url}/api/tasks")
                    tasks = r.json()
                    if isinstance(tasks, list):
                        pending = len([t for t in tasks if t.get('status') == 'pending'])
                        processing = len([t for t in tasks if t.get('status') == 'processing'])
                        completed = len([t for t in tasks if t.get('status') == 'completed'])
                        failed = len([t for t in tasks if t.get('status') in ['failed', 'dead_letter']])
                        results.append(f"Tasks: {pending} pending, {processing} processing, {completed} completed, {failed} failed")
                    else:
                        results.append(f"Tasks: {tasks}")
                except Exception as e:
                    results.append(f"Tasks: ERROR - {e}")

            if check_type in ['scheduler', 'all']:
                try:
                    r = await client.get(f"{self.omni_agent_url}/api/scheduler/logs?limit=5")
                    data = r.json()
                    logs = data.get('logs', data) if isinstance(data, dict) else data
                    if logs:
                        results.append("Recent runs:")
                        for log in logs[:3]:
                            animal = log.get('animal', 'Unknown')
                            status = log.get('status', 'unknown')
                            time = log.get('timestamp', '')[:16] if log.get('timestamp') else ''
                            results.append(f"  - {animal}: {status} ({time})")
                    else:
                        results.append("Scheduler: No recent runs")
                except Exception as e:
                    results.append(f"Scheduler: ERROR - {e}")

        return "\n".join(results) if results else "Could not check status"

    async def _tool_run_animal_facts(self, dry_run: bool = True) -> str:
        """Trigger animal facts video generation"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{self.omni_agent_url}/api/animal-facts/run",
                    json={"dry_run": dry_run, "duration": 10}
                )
                data = r.json()

                if data.get('status') == 'started':
                    animal = data.get('animal', 'Unknown')
                    task_id = data.get('task_id', '')
                    msg = f"Video generation STARTED!\n"
                    msg += f"Animal: {animal}\n"
                    msg += f"Fact: {data.get('fact', 'N/A')[:100]}...\n"
                    msg += f"Task ID: {task_id}\n"
                    msg += f"Mode: {'DRY RUN (no posting)' if dry_run else 'LIVE (will post to social media)'}\n"
                    msg += f"Estimated time: 2-5 minutes"
                    return msg
                else:
                    return f"Response: {json.dumps(data, indent=2)}"
        except Exception as e:
            return f"Failed to trigger: {str(e)}"

    async def _tool_get_logs(self, limit: int = 10) -> str:
        """Get scheduler logs"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{self.omni_agent_url}/api/scheduler/logs?limit={limit}")
                data = r.json()
                logs = data.get('logs', data) if isinstance(data, dict) else data

                if not logs:
                    return "No scheduler logs found"

                result = f"Last {len(logs)} runs:\n"
                for log in logs:
                    animal = log.get('animal', 'Unknown')
                    status = log.get('status', 'unknown')
                    time = log.get('timestamp', '')[:16] if log.get('timestamp') else ''
                    video = "Yes" if log.get('video') else "No"
                    result += f"- {time} | {animal} | {status} | Video: {video}\n"
                return result
        except Exception as e:
            return f"Failed to get logs: {str(e)}"

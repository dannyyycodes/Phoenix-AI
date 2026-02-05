"""
Phoenix AI Brain
Claude-powered AI with full development capabilities
"""

import os
import json
import httpx
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime


class PhoenixBrain:
    """AI brain powered by Claude via OpenRouter with extensive tool use"""

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
        self.github_owner = os.environ.get('GITHUB_DEFAULT_OWNER', 'dannyyycodes')
        self.github_token = os.environ.get('GITHUB_TOKEN', '')

        # For returning media to send
        self.pending_media = None

    def _get_system_prompt(self) -> str:
        return f"""You are Phoenix AI, a powerful personal development assistant on Telegram.

## YOUR CAPABILITIES
You can execute real actions using tools. When the user asks you to do something, USE THE TOOLS.

## KNOWN PROJECTS

### 1. Omni-Agent (Animal Facts Automation)
- URL: {self.omni_agent_url}
- GitHub: {self.github_owner}/Omni-Agent
- Purpose: Generates animal facts videos using Sora 2 via Kie.ai
- Features: Auto-posts to TikTok, Instagram, YouTube Shorts
- Schedule: Every 6 hours (4 posts per day)
- Key files:
  - workflows/animal_facts.py - Main workflow logic
  - utils/video_composer.py - Text overlay composition
  - app.py - Flask API endpoints
  - core/scheduler.py - Scheduling system

### 2. Phoenix-AI (This Bot)
- GitHub: {self.github_owner}/Phoenix-AI
- Purpose: Telegram bot for managing projects from phone
- Key files:
  - bot.py - Telegram handler
  - core/brain.py - AI logic (this file)
  - core/memory.py - Database/memory

## IMPORTANT BEHAVIORS
1. When asked to READ a file: Use read_github_file tool
2. When asked to EDIT/CHANGE code: Use edit_github_file tool (requires approval)
3. When asked about LOGS: Use get_railway_logs tool
4. When asked to SEND/SHOW a video: Use send_video tool
5. When asked about animal facts/status: Use check_omni_agent tool
6. ALWAYS execute tools when user asks you to DO something
7. Be concise - user is on mobile
8. After code changes, remind user it will auto-deploy

## Current Time: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}"""

    def _get_tools(self) -> List[Dict]:
        """All available tools"""
        return [
            # === OMNI-AGENT TOOLS ===
            {
                "type": "function",
                "function": {
                    "name": "check_omni_agent",
                    "description": "Check status of the Omni-Agent animal facts automation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "check_type": {
                                "type": "string",
                                "enum": ["health", "tasks", "scheduler", "all"],
                                "description": "What to check"
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
                    "description": "Trigger a new animal facts video generation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dry_run": {
                                "type": "boolean",
                                "description": "If true, generates video but doesn't post. Default true."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_task",
                    "description": "Check status of a specific video task by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "The task ID"}
                        },
                        "required": ["task_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "test_overlay",
                    "description": "Test video text overlay without using Sora API credits",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fact": {"type": "string", "description": "Fact text to overlay"},
                            "animal": {"type": "string", "description": "Animal name"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_omni_logs",
                    "description": "Get recent scheduler/run logs from Omni-Agent",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Number of entries (default 10)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_post_history",
                    "description": "Get detailed history of recent posts - what was posted, when, which platforms, success/failure",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Number of posts to show (default 5)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_project_stats",
                    "description": "Get comprehensive stats: total posts, success rate, uptime, next scheduled run",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_schedule",
                    "description": "Change the posting schedule (how often videos are posted)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "interval_hours": {
                                "type": "integer",
                                "description": "Hours between posts (e.g., 6 = every 6 hours = 4 posts/day)"
                            }
                        },
                        "required": ["interval_hours"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "toggle_scheduler",
                    "description": "Pause or resume the automatic posting schedule",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "enabled": {
                                "type": "boolean",
                                "description": "True to enable/resume, False to pause"
                            }
                        },
                        "required": ["enabled"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_animal",
                    "description": "Add a new animal to the content rotation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Animal name (e.g., 'Snow Leopard')"},
                            "habitat": {"type": "string", "description": "Where it lives (e.g., 'Himalayan Mountains')"},
                            "prompt_style": {"type": "string", "description": "Visual description for video (e.g., 'prowling through snow')"}
                        },
                        "required": ["name"]
                    }
                }
            },
            # === THEME TOOLS ===
            {
                "type": "function",
                "function": {
                    "name": "list_themes",
                    "description": "List all content themes (e.g., Animal Facts, Baby Animals, etc.)",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_theme",
                    "description": "Create a new content theme for video automation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Theme name (e.g., 'Baby Animals', 'Ocean Life')"
                            },
                            "description": {
                                "type": "string",
                                "description": "What this theme is about"
                            },
                            "content_focus": {
                                "type": "string",
                                "description": "What kind of content/facts to generate (e.g., 'facts about baby and newborn animals')"
                            },
                            "visual_style": {
                                "type": "string",
                                "description": "Visual style: 'hyper_realistic', 'cute_soft', 'dramatic', 'underwater', 'cinematic'"
                            },
                            "schedule_hours": {
                                "type": "integer",
                                "description": "Hours between posts (6 = 4 posts/day, 8 = 3 posts/day)"
                            }
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_theme",
                    "description": "Run video generation for a specific theme",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "theme_id": {
                                "type": "string",
                                "description": "Theme ID (e.g., 'animal_facts', 'baby_animals')"
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "If true, generate but don't post to socials"
                            },
                            "subject": {
                                "type": "string",
                                "description": "Optional specific subject (e.g., 'baby elephant')"
                            }
                        },
                        "required": ["theme_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_theme_source",
                    "description": "Change video source for a theme (AI-generated or stock footage)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "theme_id": {
                                "type": "string",
                                "description": "Theme ID"
                            },
                            "source": {
                                "type": "string",
                                "enum": ["sora", "pexels", "manual"],
                                "description": "Video source: 'sora' (AI), 'pexels' (stock), 'manual' (your URL)"
                            }
                        },
                        "required": ["theme_id", "source"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_theme",
                    "description": "Delete a content theme",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "theme_id": {"type": "string", "description": "Theme ID to delete"}
                        },
                        "required": ["theme_id"]
                    }
                }
            },
            # === GITHUB TOOLS ===
            {
                "type": "function",
                "function": {
                    "name": "read_github_file",
                    "description": "Read a file from a GitHub repository. Use this when user wants to see/view code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {
                                "type": "string",
                                "description": "Repository name (e.g., 'Omni-Agent' or 'Phoenix-AI')"
                            },
                            "path": {
                                "type": "string",
                                "description": "File path (e.g., 'utils/video_composer.py')"
                            }
                        },
                        "required": ["repo", "path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_github_file",
                    "description": "Edit a file in GitHub. REQUIRES USER APPROVAL. Use when user wants to change/update/modify code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {
                                "type": "string",
                                "description": "Repository name"
                            },
                            "path": {
                                "type": "string",
                                "description": "File path to edit"
                            },
                            "find_text": {
                                "type": "string",
                                "description": "Text to find and replace"
                            },
                            "replace_text": {
                                "type": "string",
                                "description": "New text to replace with"
                            },
                            "commit_message": {
                                "type": "string",
                                "description": "Commit message describing the change"
                            }
                        },
                        "required": ["repo", "path", "find_text", "replace_text", "commit_message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_github_files",
                    "description": "List files in a GitHub repository directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {"type": "string", "description": "Repository name"},
                            "path": {"type": "string", "description": "Directory path (default: root)"}
                        },
                        "required": ["repo"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_github_code",
                    "description": "Search for text/code in a repository",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {"type": "string", "description": "Repository name"},
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["repo", "query"]
                    }
                }
            },
            # === RAILWAY TOOLS ===
            {
                "type": "function",
                "function": {
                    "name": "get_railway_logs",
                    "description": "Get recent deployment logs from Railway",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {
                                "type": "string",
                                "enum": ["omni-agent", "phoenix-ai"],
                                "description": "Which project's logs to get"
                            },
                            "lines": {"type": "integer", "description": "Number of lines (default 50)"}
                        },
                        "required": ["project"]
                    }
                }
            },
            # === MEDIA TOOLS ===
            {
                "type": "function",
                "function": {
                    "name": "send_video",
                    "description": "Send a video file directly in the Telegram chat. Use when user wants to see/preview a video.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "video_url": {
                                "type": "string",
                                "description": "URL of the video to send"
                            },
                            "caption": {
                                "type": "string",
                                "description": "Caption for the video"
                            }
                        },
                        "required": ["video_url"]
                    }
                }
            }
        ]

    async def think(self, user_id: str, user_message: str) -> Dict:
        """
        Process user message with full agentic loop.
        Returns dict with 'response' and optionally 'video' to send.
        """
        # Reset pending media
        self.pending_media = None

        # Build conversation with context
        messages = self.memory.get_conversation_for_context(user_id, max_tokens=10000)
        messages.append({"role": "user", "content": user_message})

        # Store user message
        self.memory.add_message(user_id, "user", user_message)

        # Agentic loop
        max_iterations = 5
        for i in range(max_iterations):
            response = await self._call_claude(messages)

            if 'error' in response:
                return {"response": f"Error: {response['error']}"}

            assistant_message = response.get('choices', [{}])[0].get('message', {})
            tool_calls = assistant_message.get('tool_calls', [])

            if tool_calls:
                messages.append(assistant_message)

                for tool_call in tool_calls:
                    func = tool_call.get('function', {})
                    tool_name = func.get('name', '')

                    try:
                        args = json.loads(func.get('arguments', '{}'))
                    except:
                        args = {}

                    tool_result = await self._execute_tool(tool_name, args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get('id', ''),
                        "content": tool_result
                    })
            else:
                final_response = assistant_message.get('content', 'Done.')
                self.memory.add_message(user_id, "assistant", final_response)

                result = {"response": final_response}
                if self.pending_media:
                    result["video"] = self.pending_media
                return result

        return {"response": "Request took too many steps. Please try again."}

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
                        "max_tokens": 4096,
                        "messages": [{"role": "system", "content": self._get_system_prompt()}] + messages,
                        "tools": self._get_tools(),
                    }
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def _execute_tool(self, tool_name: str, args: Dict) -> str:
        """Execute a tool and return result"""
        try:
            # Omni-Agent tools
            if tool_name == "check_omni_agent":
                return await self._tool_check_omni(args.get('check_type', 'all'))
            elif tool_name == "run_animal_facts":
                return await self._tool_run_animal_facts(args.get('dry_run', True))
            elif tool_name == "check_task":
                return await self._tool_check_task(args.get('task_id', ''))
            elif tool_name == "test_overlay":
                return await self._tool_test_overlay(args.get('fact'), args.get('animal'))
            elif tool_name == "get_omni_logs":
                return await self._tool_get_logs(args.get('limit', 10))
            elif tool_name == "get_post_history":
                return await self._tool_get_post_history(args.get('limit', 5))
            elif tool_name == "get_project_stats":
                return await self._tool_get_project_stats()
            elif tool_name == "update_schedule":
                return await self._tool_update_schedule(args.get('interval_hours', 6))
            elif tool_name == "toggle_scheduler":
                return await self._tool_toggle_scheduler(args.get('enabled', True))
            elif tool_name == "add_animal":
                return await self._tool_add_animal(
                    args.get('name', ''),
                    args.get('habitat', ''),
                    args.get('prompt_style', '')
                )

            # Theme tools
            elif tool_name == "list_themes":
                return await self._tool_list_themes()
            elif tool_name == "create_theme":
                return await self._tool_create_theme(
                    args.get('name', ''),
                    args.get('description', ''),
                    args.get('content_focus', ''),
                    args.get('visual_style', 'hyper_realistic'),
                    args.get('schedule_hours', 6)
                )
            elif tool_name == "run_theme":
                return await self._tool_run_theme(
                    args.get('theme_id', 'animal_facts'),
                    args.get('dry_run', False),
                    args.get('subject')
                )
            elif tool_name == "set_theme_source":
                return await self._tool_set_theme_source(
                    args.get('theme_id', ''),
                    args.get('source', 'sora')
                )
            elif tool_name == "delete_theme":
                return await self._tool_delete_theme(args.get('theme_id', ''))

            # GitHub tools
            elif tool_name == "read_github_file":
                return await self._tool_read_file(args.get('repo', ''), args.get('path', ''))
            elif tool_name == "edit_github_file":
                return await self._tool_edit_file(
                    args.get('repo', ''),
                    args.get('path', ''),
                    args.get('find_text', ''),
                    args.get('replace_text', ''),
                    args.get('commit_message', 'Update via Phoenix AI')
                )
            elif tool_name == "list_github_files":
                return await self._tool_list_files(args.get('repo', ''), args.get('path', ''))
            elif tool_name == "search_github_code":
                return await self._tool_search_code(args.get('repo', ''), args.get('query', ''))

            # Railway tools
            elif tool_name == "get_railway_logs":
                return await self._tool_railway_logs(args.get('project', 'omni-agent'), args.get('lines', 50))

            # Media tools
            elif tool_name == "send_video":
                return await self._tool_send_video(args.get('video_url', ''), args.get('caption', ''))

            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Tool error: {str(e)}"

    # ==================== OMNI-AGENT TOOLS ====================

    async def _tool_check_omni(self, check_type: str) -> str:
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
                    if isinstance(tasks, dict):
                        tasks = tasks.get('tasks', [])
                    pending = len([t for t in tasks if t.get('status') == 'pending'])
                    processing = len([t for t in tasks if t.get('status') == 'processing'])
                    completed = len([t for t in tasks if t.get('status') == 'completed'])
                    failed = len([t for t in tasks if t.get('status') in ['failed', 'dead_letter']])
                    results.append(f"Tasks: {pending} pending, {processing} processing, {completed} completed, {failed} failed")
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
                            animal = log.get('animal', '?')
                            status = log.get('status', '?')
                            results.append(f"  - {animal}: {status}")
                except Exception as e:
                    results.append(f"Scheduler: ERROR - {e}")

        return "\n".join(results) if results else "Could not check status"

    async def _tool_run_animal_facts(self, dry_run: bool = True) -> str:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{self.omni_agent_url}/api/animal-facts/run",
                    json={"dry_run": dry_run, "duration": 10}
                )
                data = r.json()

                if data.get('status') == 'started':
                    return (
                        f"Video generation STARTED!\n\n"
                        f"Animal: {data.get('animal', '?')}\n"
                        f"Fact: {data.get('fact', 'N/A')[:100]}...\n"
                        f"Task ID: {data.get('task_id', '')}\n"
                        f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n\n"
                        f"Takes 2-5 min. Say 'check task [ID]' to monitor."
                    )
                return f"Response: {json.dumps(data)}"
        except Exception as e:
            return f"Failed: {e}"

    async def _tool_check_task(self, task_id: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{self.omni_agent_url}/api/tasks/{task_id}")
                data = r.json()

                status = data.get('status', 'unknown')
                animal = data.get('animal', '?')
                video = data.get('video')

                msg = f"Task: {task_id[:12]}...\nAnimal: {animal}\nStatus: {status.upper()}\n"

                if status == 'completed' and video:
                    msg += f"\nVIDEO READY!\nURL: {video}"
                    # Auto-queue video for sending
                    self.pending_media = {"url": video, "caption": f"{animal} Facts"}
                elif status == 'processing':
                    msg += "\nStill processing... check again in 1-2 min"
                elif status in ['failed', 'dead_letter']:
                    msg += f"\nFailed: {data.get('error', 'Unknown')}"

                return msg
        except Exception as e:
            return f"Error: {e}"

    async def _tool_test_overlay(self, fact: str = None, animal: str = None) -> str:
        try:
            payload = {}
            if fact:
                payload['fact'] = fact
            if animal:
                payload['animal'] = animal

            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    f"{self.omni_agent_url}/api/animal-facts/test-overlay",
                    json=payload
                )
                data = r.json()

                if data.get('status') == 'success':
                    video_path = data.get('video_url', '')
                    full_url = f"{self.omni_agent_url}{video_path}"

                    # Queue video for sending
                    self.pending_media = {
                        "url": full_url,
                        "caption": f"Overlay Test: {data.get('animal', 'Test')}"
                    }

                    return (
                        f"OVERLAY TEST COMPLETE!\n\n"
                        f"Animal: {data.get('animal')}\n"
                        f"Fact: {data.get('fact', '')[:80]}...\n\n"
                        f"Sending video preview..."
                    )
                return f"Failed: {data.get('message', 'Unknown')}"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_get_logs(self, limit: int = 10) -> str:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{self.omni_agent_url}/api/scheduler/logs?limit={limit}")
                data = r.json()
                logs = data.get('logs', data) if isinstance(data, dict) else data

                if not logs:
                    return "No logs found"

                result = f"Last {len(logs)} runs:\n"
                for log in logs:
                    animal = log.get('animal', '?')
                    status = log.get('status', '?')
                    time = str(log.get('timestamp', ''))[:16]
                    result += f"- {time} | {animal} | {status}\n"
                return result
        except Exception as e:
            return f"Error: {e}"

    async def _tool_get_post_history(self, limit: int = 5) -> str:
        """Get detailed post history"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Get tasks (which are posts)
                r = await client.get(f"{self.omni_agent_url}/api/tasks")
                data = r.json()
                tasks = data.get('tasks', []) if isinstance(data, dict) else data

                if not tasks:
                    return "No posts yet."

                # Sort by created_at descending and take limit
                tasks = sorted(tasks, key=lambda x: x.get('created_at', ''), reverse=True)[:limit]

                result = f"Last {len(tasks)} posts:\n\n"
                for i, task in enumerate(tasks, 1):
                    animal = task.get('animal', 'Unknown')
                    status = task.get('status', '?')
                    created = str(task.get('created_at', ''))[:16]

                    status_icon = {
                        'completed': '✅',
                        'processing': '⏳',
                        'pending': '🕐',
                        'failed': '❌',
                        'dead_letter': '💀'
                    }.get(status, '❓')

                    result += f"{i}. {status_icon} {animal}\n"
                    result += f"   {created} | {status}\n"

                    if task.get('video'):
                        result += f"   Video: Ready\n"
                    if task.get('posted'):
                        result += f"   Posted to: IG, TikTok, YT\n"
                    result += "\n"

                return result
        except Exception as e:
            return f"Error: {e}"

    async def _tool_get_project_stats(self) -> str:
        """Get comprehensive project statistics"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Get multiple endpoints
                health_r = await client.get(f"{self.omni_agent_url}/health")
                tasks_r = await client.get(f"{self.omni_agent_url}/api/tasks")
                schedule_r = await client.get(f"{self.omni_agent_url}/api/scheduler/schedules")
                admin_r = await client.get(f"{self.omni_agent_url}/api/admin/status")

                health = health_r.json() if health_r.status_code == 200 else {}
                tasks_data = tasks_r.json() if tasks_r.status_code == 200 else {}
                schedule_data = schedule_r.json() if schedule_r.status_code == 200 else {}
                admin_data = admin_r.json() if admin_r.status_code == 200 else {}

                tasks = tasks_data.get('tasks', []) if isinstance(tasks_data, dict) else []
                schedules = schedule_data.get('schedules', [])

                # Calculate stats
                total = len(tasks)
                completed = len([t for t in tasks if t.get('status') == 'completed'])
                failed = len([t for t in tasks if t.get('status') in ['failed', 'dead_letter']])
                success_rate = (completed / total * 100) if total > 0 else 0

                # Schedule info
                schedule_info = "Not configured"
                if schedules:
                    s = schedules[0]
                    interval = s.get('interval_hours', '?')
                    enabled = '✅ Active' if s.get('enabled') else '⏸️ Paused'
                    schedule_info = f"Every {interval}h ({enabled})"

                result = f"""📊 PROJECT STATS

🟢 Status: {health.get('status', 'Unknown').upper()}
📅 Schedule: {schedule_info}

📈 Posts:
   Total: {total}
   Successful: {completed}
   Failed: {failed}
   Success Rate: {success_rate:.0f}%

🐾 Animals: {admin_data.get('animal_count', '?')} in rotation
🎬 Last Video: {admin_data.get('last_video', 'None')[:30] if admin_data.get('last_video') else 'None'}
⏰ Last Run: {str(admin_data.get('last_run', 'Never'))[:16]}
"""
                return result
        except Exception as e:
            return f"Error getting stats: {e}"

    async def _tool_update_schedule(self, interval_hours: int) -> str:
        """Update posting schedule"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Get current schedule ID
                r = await client.get(f"{self.omni_agent_url}/api/scheduler/schedules")
                schedules = r.json().get('schedules', [])

                if not schedules:
                    return "No schedule found to update"

                schedule_id = schedules[0].get('id', 'animal_facts_auto')
                posts_per_day = 24 // interval_hours

                # Update schedule
                r = await client.post(
                    f"{self.omni_agent_url}/api/scheduler/schedules",
                    json={
                        "id": schedule_id,
                        "interval_hours": interval_hours,
                        "posts_per_day": posts_per_day
                    }
                )

                if r.status_code == 200:
                    return f"✅ Schedule updated!\n\nNew: Every {interval_hours} hours ({posts_per_day} posts/day)"
                else:
                    return f"Failed to update: {r.text[:100]}"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_toggle_scheduler(self, enabled: bool) -> str:
        """Pause or resume scheduler"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{self.omni_agent_url}/api/scheduler/schedules")
                schedules = r.json().get('schedules', [])

                if not schedules:
                    return "No schedule found"

                schedule_id = schedules[0].get('id', 'animal_facts_auto')

                r = await client.post(
                    f"{self.omni_agent_url}/api/scheduler/schedules/{schedule_id}/toggle"
                )

                if r.status_code == 200:
                    status = "▶️ RESUMED" if enabled else "⏸️ PAUSED"
                    return f"Scheduler {status}\n\nAutomatic posting is now {'active' if enabled else 'paused'}."
                else:
                    return f"Failed: {r.text[:100]}"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_add_animal(self, name: str, habitat: str = '', prompt_style: str = '') -> str:
        """Add a new animal to the rotation"""
        try:
            if not name:
                return "Please provide an animal name"

            animal_id = name.lower().replace(' ', '_')

            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{self.omni_agent_url}/api/admin/animals",
                    json={
                        "id": animal_id,
                        "name": name,
                        "habitat": habitat or "Natural habitat",
                        "prompt_style": prompt_style or "in its natural environment"
                    }
                )

                if r.status_code == 200:
                    return f"✅ Added: {name}\n\nIt's now in the rotation and may appear in future videos!"
                else:
                    return f"Failed to add: {r.text[:100]}"
        except Exception as e:
            return f"Error: {e}"

    # ==================== THEME TOOLS ====================

    async def _tool_list_themes(self) -> str:
        """List all content themes"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{self.omni_agent_url}/api/themes")
                data = r.json()
                themes = data.get('themes', [])

                if not themes:
                    return "No themes found. Create one with 'create a new theme called [name]'"

                result = "📋 CONTENT THEMES\n\n"
                for theme in themes:
                    status = "✅" if theme.get('enabled', True) else "⏸️"
                    source = theme.get('video_source', 'sora').upper()
                    schedule = theme.get('schedule_hours', 6)

                    result += f"{status} **{theme['name']}** ({theme['id']})\n"
                    result += f"   Source: {source} | Schedule: Every {schedule}h\n"
                    result += f"   Style: {theme.get('visual_style', 'N/A')[:40]}...\n\n"

                return result
        except Exception as e:
            return f"Error: {e}"

    async def _tool_create_theme(self, name: str, description: str, content_focus: str,
                                  visual_style: str, schedule_hours: int) -> str:
        """Create a new content theme"""
        try:
            if not name:
                return "Please provide a theme name"

            # Map visual style shortcuts to full descriptions
            style_map = {
                'hyper_realistic': 'hyper-realistic, nature documentary quality, cinematic 4K, detailed textures',
                'cute_soft': 'soft lighting, gentle colors, cute aesthetic, warm tones, dreamy atmosphere',
                'dramatic': 'dramatic lighting, cinematic, intense mood, high contrast, epic scale',
                'underwater': 'underwater photography, blue tones, serene, crystal clear water',
                'cinematic': 'cinematic quality, professional lighting, film-like color grading'
            }

            full_style = style_map.get(visual_style, visual_style)

            # Build content prompt if focus provided
            content_prompt = ""
            if content_focus:
                content_prompt = f"Generate ONE fascinating fact about {{animal}} focusing on {content_focus}. Keep it under 100 words. Make it surprising and shareable."

            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{self.omni_agent_url}/api/themes",
                    json={
                        "name": name,
                        "description": description or f"Auto-generated {name} content",
                        "content_prompt": content_prompt,
                        "visual_style": full_style,
                        "schedule_hours": schedule_hours,
                        "video_source": "sora"
                    }
                )

                if r.status_code == 200:
                    data = r.json()
                    theme = data.get('theme', {})
                    theme_id = theme.get('id', name.lower().replace(' ', '_'))

                    return (
                        f"✅ THEME CREATED: {name}\n\n"
                        f"ID: {theme_id}\n"
                        f"Style: {visual_style}\n"
                        f"Schedule: Every {schedule_hours} hours\n"
                        f"Source: Sora AI\n\n"
                        f"To run: 'run {theme_id} theme'\n"
                        f"To use stock footage: 'switch {theme_id} to pexels'"
                    )
                else:
                    return f"Failed to create: {r.text[:100]}"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_run_theme(self, theme_id: str, dry_run: bool, subject: str = None) -> str:
        """Run video generation for a theme"""
        try:
            async with httpx.AsyncClient(timeout=300) as client:  # 5 min timeout for video gen
                payload = {"dry_run": dry_run, "duration": 10}
                if subject:
                    payload["subject"] = subject

                r = await client.post(
                    f"{self.omni_agent_url}/api/themes/{theme_id}/run",
                    json=payload
                )

                data = r.json()

                if data.get('status') in ['success', 'dry_run_success']:
                    video = data.get('video', '')
                    if video and not dry_run:
                        self.pending_media = {"url": video, "caption": f"{data.get('subject', '')} - {data.get('theme', '')}"}

                    mode = "DRY RUN" if dry_run else "LIVE"
                    posted = "Yes - sent to socials!" if data.get('posted') else "No"

                    return (
                        f"🎬 THEME RUN COMPLETE ({mode})\n\n"
                        f"Theme: {data.get('theme', theme_id)}\n"
                        f"Subject: {data.get('subject', 'N/A')}\n"
                        f"Content: {data.get('content', 'N/A')[:80]}...\n"
                        f"Posted: {posted}\n"
                        f"Video: {'Ready' if video else 'N/A'}"
                    )
                else:
                    return f"Failed: {data.get('error', 'Unknown error')}"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_set_theme_source(self, theme_id: str, source: str) -> str:
        """Change video source for a theme"""
        try:
            if not theme_id:
                return "Please specify a theme ID"

            source_names = {
                'sora': 'Sora AI (generated)',
                'pexels': 'Pexels (free stock)',
                'manual': 'Manual (your URL)'
            }

            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{self.omni_agent_url}/api/themes/{theme_id}/source",
                    json={"source": source}
                )

                if r.status_code == 200:
                    return f"✅ {theme_id} now uses: {source_names.get(source, source)}"
                else:
                    return f"Failed: {r.text[:100]}"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_delete_theme(self, theme_id: str) -> str:
        """Delete a theme"""
        try:
            if not theme_id:
                return "Please specify a theme ID"

            if theme_id == 'animal_facts':
                return "Cannot delete the default 'animal_facts' theme"

            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.delete(f"{self.omni_agent_url}/api/themes/{theme_id}")

                if r.status_code == 200:
                    return f"✅ Theme '{theme_id}' deleted"
                else:
                    return f"Failed: {r.text[:100]}"
        except Exception as e:
            return f"Error: {e}"

    # ==================== GITHUB TOOLS ====================

    async def _tool_read_file(self, repo: str, path: str) -> str:
        """Read file from GitHub"""
        try:
            full_repo = f"{self.github_owner}/{repo}" if '/' not in repo else repo

            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(
                    f"https://api.github.com/repos/{full_repo}/contents/{path}",
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                )

                if r.status_code == 404:
                    return f"File not found: {path}"

                data = r.json()

                if data.get('type') == 'dir':
                    files = [f"{f['name']}{'/' if f['type'] == 'dir' else ''}" for f in data]
                    return f"Directory {path}:\n" + "\n".join(files)

                content = base64.b64decode(data.get('content', '')).decode('utf-8')

                # Truncate if too long
                if len(content) > 3000:
                    content = content[:3000] + "\n\n... [truncated, file is longer]"

                return f"File: {path}\n\n```\n{content}\n```"

        except Exception as e:
            return f"Error reading file: {e}"

    async def _tool_edit_file(self, repo: str, path: str, find_text: str,
                             replace_text: str, commit_message: str) -> str:
        """Edit file in GitHub"""
        try:
            full_repo = f"{self.github_owner}/{repo}" if '/' not in repo else repo

            async with httpx.AsyncClient(timeout=30) as client:
                # Get current file
                r = await client.get(
                    f"https://api.github.com/repos/{full_repo}/contents/{path}",
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                )

                if r.status_code != 200:
                    return f"Could not read file: {r.status_code}"

                data = r.json()
                sha = data.get('sha')
                current_content = base64.b64decode(data.get('content', '')).decode('utf-8')

                # Check if find_text exists
                if find_text not in current_content:
                    return f"Could not find text to replace:\n```\n{find_text[:200]}\n```"

                # Make replacement
                new_content = current_content.replace(find_text, replace_text, 1)

                # Commit
                r = await client.put(
                    f"https://api.github.com/repos/{full_repo}/contents/{path}",
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    },
                    json={
                        "message": commit_message,
                        "content": base64.b64encode(new_content.encode()).decode(),
                        "sha": sha
                    }
                )

                if r.status_code in [200, 201]:
                    return (
                        f"FILE UPDATED!\n\n"
                        f"Repo: {full_repo}\n"
                        f"File: {path}\n"
                        f"Commit: {commit_message}\n\n"
                        f"Railway will auto-deploy in ~2 minutes."
                    )
                return f"Commit failed: {r.status_code} - {r.text[:200]}"

        except Exception as e:
            return f"Error editing file: {e}"

    async def _tool_list_files(self, repo: str, path: str = '') -> str:
        """List files in GitHub repo"""
        try:
            full_repo = f"{self.github_owner}/{repo}" if '/' not in repo else repo

            async with httpx.AsyncClient(timeout=30) as client:
                url = f"https://api.github.com/repos/{full_repo}/contents/{path}"
                r = await client.get(
                    url,
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                )

                if r.status_code != 200:
                    return f"Error: {r.status_code}"

                data = r.json()

                if not isinstance(data, list):
                    data = [data]

                files = []
                for f in data:
                    icon = "📁" if f['type'] == 'dir' else "📄"
                    files.append(f"{icon} {f['name']}")

                return f"Files in {repo}/{path or 'root'}:\n" + "\n".join(files)

        except Exception as e:
            return f"Error: {e}"

    async def _tool_search_code(self, repo: str, query: str) -> str:
        """Search code in GitHub repo"""
        try:
            full_repo = f"{self.github_owner}/{repo}" if '/' not in repo else repo

            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(
                    f"https://api.github.com/search/code",
                    params={
                        "q": f"{query} repo:{full_repo}"
                    },
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                )

                data = r.json()
                items = data.get('items', [])

                if not items:
                    return f"No results for '{query}' in {repo}"

                results = [f"Found {len(items)} matches for '{query}':\n"]
                for item in items[:10]:
                    results.append(f"- {item['path']}")

                return "\n".join(results)

        except Exception as e:
            return f"Error: {e}"

    # ==================== RAILWAY TOOLS ====================

    async def _tool_railway_logs(self, project: str, lines: int = 50) -> str:
        """Get Railway logs - simplified version using health/status endpoints"""
        try:
            if project == 'omni-agent':
                url = self.omni_agent_url
            else:
                return "Only omni-agent logs available currently"

            async with httpx.AsyncClient(timeout=15) as client:
                # Get health
                r = await client.get(f"{url}/health")
                health = r.json() if r.status_code == 200 else {"status": "error"}

                # Get recent tasks as "logs"
                r2 = await client.get(f"{url}/api/tasks")
                tasks = r2.json() if r2.status_code == 200 else {}

                # Get scheduler logs
                r3 = await client.get(f"{url}/api/scheduler/logs?limit=10")
                scheduler = r3.json() if r3.status_code == 200 else {}

                msg = f"=== {project.upper()} STATUS ===\n\n"
                msg += f"Health: {health.get('status', 'unknown')}\n\n"

                if isinstance(tasks, dict):
                    msg += f"Tasks: {tasks.get('count', 0)} total\n"

                logs = scheduler.get('logs', []) if isinstance(scheduler, dict) else []
                if logs:
                    msg += "\nRecent activity:\n"
                    for log in logs[:5]:
                        msg += f"- {log.get('animal', '?')}: {log.get('status', '?')}\n"

                return msg

        except Exception as e:
            return f"Error getting logs: {e}"

    # ==================== MEDIA TOOLS ====================

    async def _tool_send_video(self, video_url: str, caption: str = '') -> str:
        """Queue a video to be sent in chat"""
        if not video_url:
            return "No video URL provided"

        self.pending_media = {
            "url": video_url,
            "caption": caption or "Video"
        }
        return f"Video queued for sending: {video_url[:50]}..."

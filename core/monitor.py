"""
Phoenix AI Monitoring System
Watches Omni-Agent and other projects for failures
Sends alerts and can auto-diagnose issues
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import httpx

logger = logging.getLogger(__name__)


class OmniAgentMonitor:
    """Monitors the Omni-Agent animal facts automation"""

    def __init__(self, base_url: str = None, alert_callback: Callable = None):
        self.base_url = base_url or "https://web-production-770b9.up.railway.app"
        self.alert_callback = alert_callback

        # Monitoring state
        self.last_check = None
        self.last_successful_post = None
        self.consecutive_failures = 0
        self.is_running = False

        # Thresholds
        self.max_hours_without_post = 8  # Alert if no post in 8 hours
        self.max_consecutive_failures = 3

    async def check_health(self) -> Dict:
        """Check if Omni-Agent is healthy"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self.base_url}/health")
                if r.status_code == 200:
                    return {"status": "healthy", "data": r.json()}
                return {"status": "unhealthy", "code": r.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def check_tasks(self) -> Dict:
        """Check pending/failed tasks"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{self.base_url}/api/tasks")
                data = r.json()

                tasks = data if isinstance(data, list) else data.get('tasks', [])

                # Categorize tasks
                pending = [t for t in tasks if t.get('status') == 'pending']
                processing = [t for t in tasks if t.get('status') == 'processing']
                failed = [t for t in tasks if t.get('status') == 'failed']
                dead_letter = [t for t in tasks if t.get('status') == 'dead_letter']

                return {
                    "status": "ok",
                    "pending": len(pending),
                    "processing": len(processing),
                    "failed": len(failed),
                    "dead_letter": len(dead_letter),
                    "tasks": tasks
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def check_scheduler(self) -> Dict:
        """Check scheduler logs for recent activity"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{self.base_url}/api/scheduler/logs?limit=20")
                data = r.json()
                logs = data.get('logs', [])

                # Find last successful post
                last_success = None
                for log in logs:
                    if log.get('status') == 'success':
                        last_success = log
                        break

                return {
                    "status": "ok",
                    "recent_runs": len(logs),
                    "last_success": last_success,
                    "logs": logs[:5]  # Return last 5
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_full_status(self) -> Dict:
        """Get comprehensive status"""
        health = await self.check_health()
        tasks = await self.check_tasks()
        scheduler = await self.check_scheduler()

        # Determine overall status
        issues = []

        if health['status'] != 'healthy':
            issues.append(f"Health check failed: {health.get('error', health.get('code', 'unknown'))}")

        if tasks.get('dead_letter', 0) > 0:
            issues.append(f"{tasks['dead_letter']} tasks in dead letter queue")

        if tasks.get('failed', 0) > 2:
            issues.append(f"{tasks['failed']} failed tasks")

        # Check for recent activity
        if scheduler.get('last_success'):
            try:
                last_time = datetime.fromisoformat(
                    scheduler['last_success'].get('timestamp', '').replace('Z', '+00:00')
                )
                hours_ago = (datetime.utcnow().replace(tzinfo=last_time.tzinfo) - last_time).total_seconds() / 3600
                if hours_ago > self.max_hours_without_post:
                    issues.append(f"No successful post in {hours_ago:.1f} hours")
            except:
                pass

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall": "critical" if len(issues) > 2 else "warning" if issues else "healthy",
            "issues": issues,
            "health": health,
            "tasks": tasks,
            "scheduler": scheduler
        }

    async def diagnose_issue(self, issue_type: str) -> Dict:
        """Attempt to diagnose a specific issue"""
        diagnosis = {
            "issue": issue_type,
            "possible_causes": [],
            "suggested_fixes": [],
            "auto_fixable": False
        }

        if "dead letter" in issue_type.lower():
            diagnosis["possible_causes"] = [
                "Kie.ai API timeout - video generation taking too long",
                "Kie.ai API key expired or rate limited",
                "Network connectivity issues",
                "Video composition failing (FFmpeg/fonts)"
            ]
            diagnosis["suggested_fixes"] = [
                "Retry the failed tasks",
                "Check Kie.ai dashboard for API status",
                "Check Railway logs for specific errors",
                "Verify environment variables are set"
            ]
            diagnosis["auto_fixable"] = True
            diagnosis["auto_fix_action"] = "retry_dead_letter_tasks"

        elif "no successful post" in issue_type.lower():
            diagnosis["possible_causes"] = [
                "Scheduler stopped or crashed",
                "All video generations are timing out",
                "Blotato API issues preventing posting"
            ]
            diagnosis["suggested_fixes"] = [
                "Check if scheduler is running",
                "Trigger a manual test run",
                "Check Blotato API status"
            ]
            diagnosis["auto_fixable"] = True
            diagnosis["auto_fix_action"] = "trigger_test_run"

        elif "health" in issue_type.lower() or "unreachable" in issue_type.lower():
            diagnosis["possible_causes"] = [
                "Railway service crashed or restarting",
                "Deployment failed",
                "Out of Railway credits/resources"
            ]
            diagnosis["suggested_fixes"] = [
                "Check Railway dashboard for service status",
                "Review recent deployment logs",
                "Trigger a redeployment"
            ]
            diagnosis["auto_fixable"] = True
            diagnosis["auto_fix_action"] = "check_railway_status"

        return diagnosis

    async def auto_fix(self, action: str) -> Dict:
        """Attempt automatic fix for known issues"""
        try:
            if action == "retry_dead_letter_tasks":
                # Get dead letter tasks and retry them
                tasks_status = await self.check_tasks()
                tasks = tasks_status.get('tasks', [])
                dead_letter = [t for t in tasks if t.get('status') == 'dead_letter']

                retried = 0
                async with httpx.AsyncClient(timeout=30) as client:
                    for task in dead_letter[:3]:  # Limit to 3 retries
                        task_id = task.get('task_id')
                        if task_id:
                            r = await client.post(f"{self.base_url}/api/tasks/{task_id}/retry")
                            if r.status_code == 200:
                                retried += 1

                return {
                    "action": action,
                    "success": retried > 0,
                    "message": f"Retried {retried} tasks"
                }

            elif action == "trigger_test_run":
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(
                        f"{self.base_url}/api/animal-facts/run",
                        json={"dry_run": True}
                    )
                    return {
                        "action": action,
                        "success": r.status_code == 200,
                        "message": f"Test run triggered: {r.json()}"
                    }

            elif action == "check_railway_status":
                # This would need Railway client
                return {
                    "action": action,
                    "success": False,
                    "message": "Need to check Railway dashboard manually"
                }

            return {"action": action, "success": False, "message": "Unknown action"}

        except Exception as e:
            return {"action": action, "success": False, "error": str(e)}

    async def run_monitoring_loop(self, interval_seconds: int = 300):
        """Run continuous monitoring (every 5 minutes by default)"""
        self.is_running = True
        logger.info(f"Starting monitoring loop (interval: {interval_seconds}s)")

        while self.is_running:
            try:
                status = await self.get_full_status()
                self.last_check = datetime.utcnow()

                if status['overall'] != 'healthy' and self.alert_callback:
                    await self.alert_callback(status)

                # Track consecutive failures
                if status['overall'] == 'critical':
                    self.consecutive_failures += 1
                else:
                    self.consecutive_failures = 0

                # Auto-fix after multiple failures
                if self.consecutive_failures >= self.max_consecutive_failures:
                    logger.warning("Multiple consecutive failures, attempting auto-fix")
                    for issue in status['issues']:
                        diagnosis = await self.diagnose_issue(issue)
                        if diagnosis['auto_fixable']:
                            fix_result = await self.auto_fix(diagnosis['auto_fix_action'])
                            if self.alert_callback:
                                await self.alert_callback({
                                    "type": "auto_fix",
                                    "issue": issue,
                                    "result": fix_result
                                })

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

            await asyncio.sleep(interval_seconds)

    def stop(self):
        """Stop the monitoring loop"""
        self.is_running = False


class AlertManager:
    """Manages sending alerts via Telegram"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.last_alert_time = {}
        self.cooldown_minutes = 30  # Don't spam same alert

    async def send_alert(self, status: Dict):
        """Send an alert to Telegram"""
        # Check cooldown
        alert_key = status.get('overall', 'unknown')
        if alert_key in self.last_alert_time:
            elapsed = (datetime.utcnow() - self.last_alert_time[alert_key]).total_seconds() / 60
            if elapsed < self.cooldown_minutes:
                return  # Skip, in cooldown

        self.last_alert_time[alert_key] = datetime.utcnow()

        # Build alert message
        if status.get('type') == 'auto_fix':
            message = f"🔧 *Auto-Fix Attempted*\n\n"
            message += f"Issue: {status['issue']}\n"
            result = status['result']
            if result.get('success'):
                message += f"✅ {result['message']}"
            else:
                message += f"❌ Failed: {result.get('error', result.get('message', 'Unknown'))}"
        else:
            emoji = {'critical': '🚨', 'warning': '⚠️', 'healthy': '✅'}.get(status['overall'], '❓')
            message = f"{emoji} *Omni-Agent Status: {status['overall'].upper()}*\n\n"

            if status['issues']:
                message += "*Issues:*\n"
                for issue in status['issues']:
                    message += f"  • {issue}\n"

            message += f"\n_Checked at {status['timestamp'][:19]}_"

        # Send via Telegram
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

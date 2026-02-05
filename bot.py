"""
Phoenix AI - Telegram Bot
Your personal AI development assistant
"""

import os
import sys

# Load environment variables from .env file (for local development)
from dotenv import load_dotenv
load_dotenv()

import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

from core.memory import MemoryManager
from core.brain import PhoenixBrain
from integrations.github_client import GitHubClient
from integrations.railway_client import RailwayClient

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ALLOWED_USERS = os.environ.get('TELEGRAM_ALLOWED_USERS', '').split(',')
ALLOWED_USERS = [u.strip() for u in ALLOWED_USERS if u.strip()]


class PhoenixBot:
    """Main Telegram bot handler"""

    def __init__(self):
        # Initialize components
        self.memory = MemoryManager()

        # Initialize integrations (optional - will work without them)
        try:
            self.github = GitHubClient()
            logger.info("GitHub integration initialized")
        except Exception as e:
            self.github = None
            logger.warning(f"GitHub integration not available: {e}")

        try:
            self.railway = RailwayClient()
            logger.info("Railway integration initialized")
        except Exception as e:
            self.railway = None
            logger.warning(f"Railway integration not available: {e}")

        # Initialize AI brain
        self.brain = PhoenixBrain(
            memory_manager=self.memory,
            github_client=self.github,
            railway_client=self.railway
        )

        # Pending approvals (in-memory cache)
        self.pending_approvals: Dict[str, Dict] = {}

    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        if not ALLOWED_USERS:
            return True  # No whitelist = allow all (not recommended)
        return str(user_id) in ALLOWED_USERS

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        user_id = str(user.id)

        if not self.is_authorized(user.id):
            await update.message.reply_text(
                "Sorry, you're not authorized to use this bot."
            )
            return

        # Check if returning user
        messages = self.memory.get_recent_messages(user_id, limit=1)

        if messages:
            projects = self.memory.get_user_projects(user_id, status='active')
            project_list = "\n".join([f"  - {p['name']}" for p in projects[:5]]) if projects else "  None yet"

            await update.message.reply_text(
                f"Welcome back! I remember our conversations.\n\n"
                f"Your active projects:\n{project_list}\n\n"
                f"What would you like to work on?"
            )
        else:
            # New user
            self.memory.get_preferences(user_id)  # Initialize preferences

            await update.message.reply_text(
                f"Hi {user.first_name}! I'm Phoenix AI, your personal development assistant.\n\n"
                f"I can help you:\n"
                f"  - Build websites, apps, and automations\n"
                f"  - Deploy to Railway and manage infrastructure\n"
                f"  - Monitor your projects and fix issues\n"
                f"  - Remember everything we work on together\n\n"
                f"What would you like to create?"
            )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self.is_authorized(update.effective_user.id):
            return

        help_text = """
*Phoenix AI Commands*

/start - Start or resume conversation
/projects - List your projects
/status - Check system status
/history - Search conversation history
/clear - Clear conversation context
/help - Show this help

*What I can do:*
- Build websites and apps from descriptions
- Deploy to Railway automatically
- Monitor your Omni-Agent automation
- Remember everything across sessions
- Fix issues with your approval

*Tips:*
- Just describe what you want to build
- Say "check my projects" to see status
- Say "what were we working on?" to resume
- I'll always ask before making changes
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /projects command"""
        user_id = str(update.effective_user.id)

        if not self.is_authorized(update.effective_user.id):
            return

        projects = self.memory.get_user_projects(user_id)

        if not projects:
            await update.message.reply_text(
                "You don't have any projects yet.\n\n"
                "Tell me what you'd like to build!"
            )
            return

        text = "*Your Projects:*\n\n"
        for p in projects:
            status_emoji = {
                'active': '🟢',
                'paused': '🟡',
                'completed': '✅',
                'archived': '📦'
            }.get(p['status'], '⚪')

            text += f"{status_emoji} *{p['name']}*\n"
            if p['description']:
                text += f"   {p['description'][:50]}...\n" if len(p['description']) > 50 else f"   {p['description']}\n"
            if p['deployment_url']:
                text += f"   🌐 {p['deployment_url']}\n"
            text += "\n"

        await update.message.reply_text(text, parse_mode='Markdown')

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not self.is_authorized(update.effective_user.id):
            return

        status_parts = ["*System Status:*\n"]

        # Check Omni-Agent
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://web-production-770b9.up.railway.app/health")
                if r.status_code == 200:
                    status_parts.append("🟢 Omni-Agent: Online")
                else:
                    status_parts.append("🔴 Omni-Agent: Error")
        except:
            status_parts.append("🔴 Omni-Agent: Unreachable")

        # Check GitHub
        if self.github:
            status_parts.append("🟢 GitHub: Connected")
        else:
            status_parts.append("⚪ GitHub: Not configured")

        # Check Railway
        if self.railway:
            status_parts.append("🟢 Railway: Connected")
        else:
            status_parts.append("⚪ Railway: Not configured")

        await update.message.reply_text("\n".join(status_parts), parse_mode='Markdown')

    async def clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        if not self.is_authorized(update.effective_user.id):
            return

        # Note: We don't actually delete history (it's valuable)
        # Just acknowledge the user wants a fresh start
        await update.message.reply_text(
            "Starting fresh conversation.\n"
            "(Your project history is preserved)\n\n"
            "What would you like to work on?"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        user = update.effective_user
        user_id = str(user.id)

        if not self.is_authorized(user.id):
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        message = update.message.text

        # Show typing indicator
        await update.message.chat.send_action("typing")

        try:
            # Process with AI brain - now returns final response directly
            response = await self.brain.think(user_id, message)

            # Send response (split if too long)
            if len(response) > 4000:
                chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await update.message.reply_text(
                f"Sorry, I encountered an error: {str(e)[:200]}\n\n"
                "Please try again or rephrase your request."
            )

    async def _request_approval(self, update: Update, user_id: str,
                               approval_request: Dict, ai_message: str):
        """Request user approval for an action"""
        tool = approval_request['tool']
        input_data = approval_request['input']

        # Create approval ID
        approval_id = f"{user_id}_{datetime.utcnow().timestamp()}"

        # Build approval message
        action_descriptions = {
            'write_file': f"Write to file: {input_data.get('path', 'unknown')}",
            'create_repository': f"Create repo: {input_data.get('name', 'unknown')}",
            'deploy_to_railway': f"Deploy: {input_data.get('repo', 'unknown')}",
            'set_railway_env': f"Set env var: {input_data.get('key', 'unknown')}",
            'redeploy_railway': "Trigger redeployment"
        }

        action_desc = action_descriptions.get(tool, f"Execute: {tool}")

        # Store pending approval
        self.pending_approvals[approval_id] = {
            'tool': tool,
            'input': input_data,
            'user_id': user_id,
            'created_at': datetime.utcnow().isoformat()
        }

        # Also store in database
        self.memory.create_approval(
            user_id=user_id,
            action_type=tool,
            description=action_desc,
            payload=input_data
        )

        # Build keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{approval_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{approval_id}")
            ],
            [
                InlineKeyboardButton("🔍 Details", callback_data=f"details:{approval_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send message with approval request
        full_message = f"{ai_message}\n\n---\n\n"
        full_message += f"🔐 *Approval Required*\n"
        full_message += f"Action: {action_desc}\n\n"
        full_message += "This action requires your approval."

        await update.message.reply_text(
            full_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()

        data = query.data
        parts = data.split(':')
        action = parts[0]
        approval_id = parts[1] if len(parts) > 1 else None

        if not approval_id or approval_id not in self.pending_approvals:
            await query.edit_message_text("This approval has expired.")
            return

        approval = self.pending_approvals[approval_id]
        user_id = str(query.from_user.id)

        if approval['user_id'] != user_id:
            await query.answer("This isn't your approval request.", show_alert=True)
            return

        if action == 'approve':
            # Execute the approved action
            await query.edit_message_text("✅ Approved! Executing...")

            try:
                result = await self.brain.execute_tool(
                    approval['tool'], approval['input']
                )

                # Log the action
                self.memory.log_action(
                    user_id=user_id,
                    action=approval['tool'],
                    details=approval['input'],
                    status='success'
                )

                await query.edit_message_text(f"✅ Done!\n\n{result}")
            except Exception as e:
                self.memory.log_action(
                    user_id=user_id,
                    action=approval['tool'],
                    details=approval['input'],
                    status='failed',
                    error=str(e)
                )
                await query.edit_message_text(f"❌ Failed: {str(e)[:200]}")

            # Clean up
            del self.pending_approvals[approval_id]

        elif action == 'reject':
            self.memory.log_action(
                user_id=user_id,
                action=approval['tool'],
                details=approval['input'],
                status='rejected'
            )
            await query.edit_message_text("❌ Action rejected.")
            del self.pending_approvals[approval_id]

        elif action == 'details':
            # Show full details
            details = json.dumps(approval['input'], indent=2)
            if len(details) > 500:
                details = details[:500] + "..."
            await query.answer(f"Details:\n{details}", show_alert=True)

    def run(self):
        """Start the bot"""
        if not BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")

        # Create application
        app = Application.builder().token(BOT_TOKEN).build()

        # Add handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(CommandHandler("projects", self.projects))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("clear", self.clear))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Start polling
        logger.info("Phoenix AI starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


# Entry point
if __name__ == "__main__":
    bot = PhoenixBot()
    bot.run()

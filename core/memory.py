"""
Phoenix AI Memory System
Stores conversation history, project contexts, and user preferences
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Conversation(Base):
    """Stores all messages for full context"""
    __tablename__ = 'conversations'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), index=True)
    role = Column(String(20))  # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(DateTime, default=func.now())

    # Optional: link to a project context
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)

    # Metadata
    tokens_used = Column(Integer, default=0)
    tool_calls = Column(JSON, nullable=True)  # Store any tool calls made


class Project(Base):
    """Project-specific memory and context"""
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), index=True)
    name = Column(String(200))
    description = Column(Text, nullable=True)

    # Technical details
    tech_stack = Column(JSON, default=list)  # ['python', 'flask', 'postgresql']
    github_repo = Column(String(200), nullable=True)
    railway_project_id = Column(String(100), nullable=True)
    deployment_url = Column(String(500), nullable=True)

    # State
    status = Column(String(50), default='active')  # active, paused, completed, archived
    current_task = Column(Text, nullable=True)  # What we're currently working on

    # Context for AI
    context_summary = Column(Text, nullable=True)  # AI-generated summary of the project
    decisions_made = Column(JSON, default=list)  # Key decisions for reference

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_active_at = Column(DateTime, default=func.now())

    # Relationships
    conversations = relationship("Conversation", backref="project")


class UserPreference(Base):
    """Learned user preferences"""
    __tablename__ = 'user_preferences'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), unique=True, index=True)

    # Coding preferences
    preferred_languages = Column(JSON, default=list)  # ['python', 'javascript']
    preferred_frameworks = Column(JSON, default=dict)  # {'frontend': 'react', 'backend': 'flask'}
    code_style = Column(JSON, default=dict)  # {'comments': 'minimal', 'typing': 'strict'}

    # Deployment preferences
    default_platform = Column(String(50), default='railway')  # railway, vercel, aws

    # Communication preferences
    verbosity = Column(String(20), default='concise')  # concise, detailed, minimal
    timezone = Column(String(50), nullable=True)

    # Custom preferences (flexible)
    custom = Column(JSON, default=dict)

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PendingApproval(Base):
    """Track actions waiting for user approval"""
    __tablename__ = 'pending_approvals'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), index=True)

    # What needs approval
    action_type = Column(String(50))  # 'deploy', 'commit', 'env_change', 'delete'
    action_description = Column(Text)
    action_payload = Column(JSON)  # The actual action to execute

    # Approval state
    status = Column(String(20), default='pending')  # pending, approved, rejected, expired
    telegram_message_id = Column(Integer, nullable=True)  # To update the message

    # Timing
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)  # Auto-expire after 10 minutes
    resolved_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """Log all actions for safety and debugging"""
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), index=True)

    action = Column(String(100))
    details = Column(JSON)
    status = Column(String(20))  # success, failed, pending
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())


class MemoryManager:
    """Manages all memory operations"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.environ.get('DATABASE_URL', '')

        # Validate and fix database URL
        if not self.database_url or 'port' in self.database_url or self.database_url == 'sqlite:///phoenix.db':
            # Invalid or placeholder URL - use SQLite
            print("Using SQLite database (no valid DATABASE_URL found)")
            self.database_url = 'sqlite:///phoenix.db'
        elif self.database_url.startswith('postgres://'):
            # Fix Railway postgres URL format
            self.database_url = self.database_url.replace('postgres://', 'postgresql://', 1)

        try:
            self.engine = create_engine(self.database_url)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
            print(f"Database connected: {self.database_url.split('@')[-1] if '@' in self.database_url else 'sqlite'}")
        except Exception as e:
            print(f"Database connection failed: {e}, falling back to SQLite")
            self.database_url = 'sqlite:///phoenix.db'
            self.engine = create_engine(self.database_url)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    # ==================== Conversation Methods ====================

    def add_message(self, user_id: str, role: str, content: str,
                    project_id: int = None, tokens: int = 0, tool_calls: dict = None):
        """Store a message in conversation history"""
        session = self.get_session()
        try:
            msg = Conversation(
                user_id=user_id,
                role=role,
                content=content,
                project_id=project_id,
                tokens_used=tokens,
                tool_calls=tool_calls
            )
            session.add(msg)
            session.commit()
            return msg.id
        finally:
            session.close()

    def get_recent_messages(self, user_id: str, limit: int = 50,
                           project_id: int = None) -> List[Dict]:
        """Get recent conversation history"""
        session = self.get_session()
        try:
            query = session.query(Conversation).filter(
                Conversation.user_id == user_id
            )
            if project_id:
                query = query.filter(Conversation.project_id == project_id)

            messages = query.order_by(Conversation.created_at.desc()).limit(limit).all()

            return [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat(),
                    'project_id': msg.project_id
                }
                for msg in reversed(messages)  # Return in chronological order
            ]
        finally:
            session.close()

    def get_conversation_for_context(self, user_id: str, max_tokens: int = 50000) -> List[Dict]:
        """Get conversation history optimized for AI context window"""
        session = self.get_session()
        try:
            # Get recent messages
            messages = session.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(Conversation.created_at.desc()).limit(100).all()

            # Build context, respecting token limit
            context = []
            estimated_tokens = 0

            for msg in reversed(messages):
                # Rough estimate: 4 chars per token
                msg_tokens = len(msg.content) // 4
                if estimated_tokens + msg_tokens > max_tokens:
                    break
                context.append({
                    'role': msg.role,
                    'content': msg.content
                })
                estimated_tokens += msg_tokens

            return context
        finally:
            session.close()

    def search_conversations(self, user_id: str, query: str, limit: int = 10) -> List[Dict]:
        """Search conversation history"""
        session = self.get_session()
        try:
            messages = session.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.content.ilike(f'%{query}%')
            ).order_by(Conversation.created_at.desc()).limit(limit).all()

            return [
                {
                    'role': msg.role,
                    'content': msg.content[:200] + '...' if len(msg.content) > 200 else msg.content,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ]
        finally:
            session.close()

    # ==================== Project Methods ====================

    def create_project(self, user_id: str, name: str, description: str = None,
                      tech_stack: list = None) -> int:
        """Create a new project"""
        session = self.get_session()
        try:
            project = Project(
                user_id=user_id,
                name=name,
                description=description,
                tech_stack=tech_stack or []
            )
            session.add(project)
            session.commit()
            return project.id
        finally:
            session.close()

    def get_project(self, project_id: int) -> Optional[Dict]:
        """Get project by ID"""
        session = self.get_session()
        try:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                return None
            return self._project_to_dict(project)
        finally:
            session.close()

    def get_project_by_name(self, user_id: str, name: str) -> Optional[Dict]:
        """Find project by name (case-insensitive)"""
        session = self.get_session()
        try:
            project = session.query(Project).filter(
                Project.user_id == user_id,
                Project.name.ilike(f'%{name}%')
            ).first()
            if not project:
                return None
            return self._project_to_dict(project)
        finally:
            session.close()

    def get_user_projects(self, user_id: str, status: str = None) -> List[Dict]:
        """Get all projects for a user"""
        session = self.get_session()
        try:
            query = session.query(Project).filter(Project.user_id == user_id)
            if status:
                query = query.filter(Project.status == status)
            projects = query.order_by(Project.last_active_at.desc()).all()
            return [self._project_to_dict(p) for p in projects]
        finally:
            session.close()

    def update_project(self, project_id: int, **kwargs):
        """Update project fields"""
        session = self.get_session()
        try:
            project = session.query(Project).filter(Project.id == project_id).first()
            if project:
                for key, value in kwargs.items():
                    if hasattr(project, key):
                        setattr(project, key, value)
                project.last_active_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def _project_to_dict(self, project: Project) -> Dict:
        return {
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'tech_stack': project.tech_stack,
            'github_repo': project.github_repo,
            'railway_project_id': project.railway_project_id,
            'deployment_url': project.deployment_url,
            'status': project.status,
            'current_task': project.current_task,
            'context_summary': project.context_summary,
            'decisions_made': project.decisions_made,
            'created_at': project.created_at.isoformat(),
            'last_active_at': project.last_active_at.isoformat()
        }

    # ==================== Preferences Methods ====================

    def get_preferences(self, user_id: str) -> Dict:
        """Get user preferences"""
        session = self.get_session()
        try:
            prefs = session.query(UserPreference).filter(
                UserPreference.user_id == user_id
            ).first()

            if not prefs:
                # Create default preferences
                prefs = UserPreference(user_id=user_id)
                session.add(prefs)
                session.commit()

            return {
                'preferred_languages': prefs.preferred_languages,
                'preferred_frameworks': prefs.preferred_frameworks,
                'code_style': prefs.code_style,
                'default_platform': prefs.default_platform,
                'verbosity': prefs.verbosity,
                'timezone': prefs.timezone,
                'custom': prefs.custom
            }
        finally:
            session.close()

    def update_preferences(self, user_id: str, **kwargs):
        """Update user preferences"""
        session = self.get_session()
        try:
            prefs = session.query(UserPreference).filter(
                UserPreference.user_id == user_id
            ).first()

            if not prefs:
                prefs = UserPreference(user_id=user_id)
                session.add(prefs)

            for key, value in kwargs.items():
                if hasattr(prefs, key):
                    setattr(prefs, key, value)

            session.commit()
        finally:
            session.close()

    # ==================== Approval Methods ====================

    def create_approval(self, user_id: str, action_type: str,
                       description: str, payload: dict,
                       message_id: int = None) -> int:
        """Create a pending approval request"""
        session = self.get_session()
        try:
            approval = PendingApproval(
                user_id=user_id,
                action_type=action_type,
                action_description=description,
                action_payload=payload,
                telegram_message_id=message_id,
                expires_at=datetime.utcnow() + timedelta(minutes=10)
            )
            session.add(approval)
            session.commit()
            return approval.id
        finally:
            session.close()

    def get_pending_approval(self, approval_id: int) -> Optional[Dict]:
        """Get a pending approval"""
        session = self.get_session()
        try:
            approval = session.query(PendingApproval).filter(
                PendingApproval.id == approval_id,
                PendingApproval.status == 'pending'
            ).first()

            if not approval:
                return None

            # Check if expired
            if approval.expires_at < datetime.utcnow():
                approval.status = 'expired'
                session.commit()
                return None

            return {
                'id': approval.id,
                'action_type': approval.action_type,
                'description': approval.action_description,
                'payload': approval.action_payload,
                'created_at': approval.created_at.isoformat()
            }
        finally:
            session.close()

    def resolve_approval(self, approval_id: int, approved: bool):
        """Mark an approval as resolved"""
        session = self.get_session()
        try:
            approval = session.query(PendingApproval).filter(
                PendingApproval.id == approval_id
            ).first()
            if approval:
                approval.status = 'approved' if approved else 'rejected'
                approval.resolved_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    # ==================== Audit Methods ====================

    def log_action(self, user_id: str, action: str, details: dict,
                  status: str = 'success', error: str = None):
        """Log an action for audit trail"""
        session = self.get_session()
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                details=details,
                status=status,
                error_message=error
            )
            session.add(log)
            session.commit()
        finally:
            session.close()

    def get_recent_actions(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get recent actions for a user"""
        session = self.get_session()
        try:
            logs = session.query(AuditLog).filter(
                AuditLog.user_id == user_id
            ).order_by(AuditLog.created_at.desc()).limit(limit).all()

            return [
                {
                    'action': log.action,
                    'details': log.details,
                    'status': log.status,
                    'error': log.error_message,
                    'created_at': log.created_at.isoformat()
                }
                for log in logs
            ]
        finally:
            session.close()

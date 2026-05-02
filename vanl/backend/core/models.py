"""
Database Models
===============
SQLAlchemy models for RĀMAN Studio enterprise features.

Author: VidyuthLabs
Date: May 1, 2026
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from vanl.backend.core.database import Base


class User(Base):
    """User model."""
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), nullable=False, default="analyst")  # admin, analyst, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    owned_workspaces = relationship("Workspace", back_populates="owner", foreign_keys="Workspace.owner_id")
    experiments = relationship("Experiment", back_populates="creator")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }


class Workspace(Base):
    """Workspace model for team collaboration."""
    __tablename__ = "workspaces"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="owned_workspaces", foreign_keys=[owner_id])
    projects = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "owner_id": str(self.owner_id),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class WorkspaceMember(Base):
    """Workspace membership model."""
    __tablename__ = "workspace_members"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(50), nullable=False, default="member")  # admin, member, viewer
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "user_id": str(self.user_id),
            "role": self.role,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None
        }


class Project(Base):
    """Project model for organizing experiments."""
    __tablename__ = "projects"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    tags = Column(JSON)  # Array of tags
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="projects")
    creator = relationship("User")
    experiments = relationship("Experiment", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Experiment(Base):
    """Experiment model for storing electrochemical data."""
    __tablename__ = "experiments"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    technique = Column(String(50), nullable=False)  # eis, cv, gcd, etc.
    description = Column(Text)
    
    # Data storage (JSONB for efficient querying)
    data = Column(JSON)  # Raw experimental data
    parameters = Column(JSON)  # Experiment parameters
    results = Column(JSON)  # Analysis results
    experiment_metadata = Column(JSON)  # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    
    # Status tracking
    status = Column(String(50), default="draft")  # draft, running, completed, failed
    
    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="experiments")
    creator = relationship("User", back_populates="experiments")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "name": self.name,
            "technique": self.technique,
            "description": self.description,
            "data": self.data,
            "parameters": self.parameters,
            "results": self.results,
            "metadata": self.experiment_metadata,  # Return as 'metadata' for API compatibility
            "status": self.status,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class BatchJob(Base):
    """Batch processing job model."""
    __tablename__ = "batch_jobs"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Job configuration
    config = Column(JSON)  # Analysis configuration
    files = Column(JSON)  # List of files to process
    
    # Status tracking
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    
    # Results
    results = Column(JSON)  # Aggregated results
    errors = Column(JSON)  # Error messages
    
    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    workspace = relationship("Workspace")
    creator = relationship("User")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "name": self.name,
            "description": self.description,
            "config": self.config,
            "status": self.status,
            "progress": self.progress,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "results": self.results,
            "errors": self.errors,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class AuditLog(Base):
    """Audit log model for 21 CFR Part 11 compliance."""
    __tablename__ = "audit_logs"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Who
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user_email = Column(String(255), nullable=False)
    
    # What
    action = Column(String(100), nullable=False)  # CREATE, READ, UPDATE, DELETE
    resource_type = Column(String(50), nullable=False)  # experiment, project, workspace
    resource_id = Column(UUID(as_uuid=True))
    
    # Details
    details = Column(JSON)  # Old/new values, etc.
    
    # When & Where
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(500))
    
    # Tamper-proof signature
    signature = Column(String(255))  # SHA256 hash
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "user_email": self.user_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "signature": self.signature
        }


class APIKey(Base):
    """API key model for automation."""
    __tablename__ = "api_keys"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    
    # Permissions
    scopes = Column(JSON)  # List of allowed scopes
    
    # Status
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    # Relationships
    user = relationship("User")
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.name,
            "scopes": self.scopes,
            "is_active": self.is_active,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }

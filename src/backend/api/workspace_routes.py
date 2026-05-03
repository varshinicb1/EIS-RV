from fastapi import APIRouter, Depends, Security
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from src.backend.core.database import get_db
from src.backend.core.models import Workspace
from src.backend.core.rbac import require_analyst

router = APIRouter(prefix="/api/v2/workspaces", tags=["Workspaces"])

class WorkspaceCreate(BaseModel):
    name: str
    description: str = None

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str

    class Config:
        from_attributes = True

@router.post("/", response_model=WorkspaceResponse)
def create_workspace(
    workspace: WorkspaceCreate, 
    db: Session = Depends(get_db),
    user_payload: dict = Security(require_analyst)
):
    user_id = user_payload.get("id")
    new_workspace = Workspace(
        name=workspace.name,
        description=workspace.description,
        owner_id=user_id
    )
    db.add(new_workspace)
    db.commit()
    db.refresh(new_workspace)
    
    # Convert UUIDs to string for Pydantic
    return {
        "id": str(new_workspace.id),
        "name": new_workspace.name,
        "description": new_workspace.description or "",
        "owner_id": str(new_workspace.owner_id)
    }

@router.get("/", response_model=List[WorkspaceResponse])
def list_workspaces(
    db: Session = Depends(get_db),
    user_payload: dict = Security(require_analyst)
):
    user_id = user_payload.get("id")
    # In a full RBAC model, you would fetch all workspaces the user has access to.
    # For now, fetch the ones they own.
    workspaces = db.query(Workspace).filter(Workspace.owner_id == user_id).all()
    
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description or "",
            "owner_id": str(w.owner_id)
        } for w in workspaces
    ]

"""
API endpoints for vector search and embeddings.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/api/v2/embeddings", tags=["embeddings"])

vector_store = None

def get_vector_store():
    global vector_store
    if vector_store is None:
        from src.backend.embeddings.vector_store import VectorStore
        vector_store = VectorStore()
    return vector_store

class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10
    text_type_filter: Optional[str] = None
    min_score: float = 0.5

class HybridSearchRequest(BaseModel):
    query: str
    keyword_filter: Optional[Dict[str, Any]] = None
    limit: int = 10

@router.post("/semantic_search")
async def semantic_search(req: SemanticSearchRequest) -> List[Dict[str, Any]]:
    """Perform semantic search over paper corpus."""
    try:
        vs = get_vector_store()
        results = vs.semantic_search(
            query=req.query,
            limit=req.limit,
            text_type_filter=req.text_type_filter,
            min_score=req.min_score
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/hybrid_search")
async def hybrid_search(req: HybridSearchRequest) -> List[Dict[str, Any]]:
    """Perform hybrid semantic + keyword search."""
    try:
        vs = get_vector_store()
        results = vs.hybrid_search(
            query=req.query,
            keyword_filter=req.keyword_filter,
            limit=req.limit
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/index_paper/{paper_id}")
async def index_paper(paper_id: int) -> Dict[str, str]:
    """Index a paper in the vector store."""
    # This would fetch paper from DB and call vector_store.add_paper
    return {"status": "indexed", "paper_id": paper_id}

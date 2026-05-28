"""
Vector Store using Qdrant for semantic search of scientific literature.
Supports BGE, SciBERT, and sentence-transformers embeddings.
"""

import logging
from typing import List, Dict, Optional, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import numpy as np
from sentence_transformers import SentenceTransformer
import os

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = "scientific_papers",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        device: str = "cpu"
    ):
        self.client = QdrantClient(url=qdrant_url)
        self.collection_name = collection_name
        self.embedding_model = SentenceTransformer(embedding_model, device=device)
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_model.get_sentence_embedding_dimension(),
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Failed to check/create collection: {e}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        return self.embedding_model.encode(text, normalize_embeddings=True)
    
    def add_paper(
        self,
        paper_id: int,
        title: str,
        abstract: str,
        sections: Dict[str, str],
        tables: List[str]
    ):
        """Add paper embeddings to vector store."""
        points = []
        
        # Embed title + abstract
        combined = f"{title}\n\n{abstract}"
        if combined.strip():
            points.append(PointStruct(
                id=f"paper_{paper_id}_main",
                vector=self.embed_text(combined).tolist(),
                payload={
                    "paper_id": paper_id,
                    "text_type": "main",
                    "title": title
                }
            ))
        
        # Embed sections individually
        for section_name, section_text in sections.items():
            if section_text.strip() and len(section_text) > 50:
                points.append(PointStruct(
                    id=f"paper_{paper_id}_{section_name}",
                    vector=self.embed_text(section_text).tolist(),
                    payload={
                        "paper_id": paper_id,
                        "text_type": "section",
                        "section_name": section_name
                    }
                ))
        
        # Embed tables
        for i, table in enumerate(tables):
            if table.strip() and len(table) > 20:
                points.append(PointStruct(
                    id=f"paper_{paper_id}_table_{i}",
                    vector=self.embed_text(table).tolist(),
                    payload={
                        "paper_id": paper_id,
                        "text_type": "table",
                        "table_index": i
                    }
                ))
        
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"Added {len(points)} embeddings for paper {paper_id}")
    
    def semantic_search(
        self,
        query: str,
        limit: int = 10,
        text_type_filter: Optional[str] = None,
        min_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Search for semantically similar papers."""
        try:
            if not self.client.collection_exists(self.collection_name):
                logger.warning(f"Collection {self.collection_name} does not exist")
                return []
            
            query_vector = self.embed_text(query).tolist()
            
            query_filter = None
            if text_type_filter:
                query_filter = Filter(
                    must=[FieldCondition(key="text_type", match=MatchValue(value=text_type_filter))]
                )
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=min_score
            )
            
            return [
                {
                    "paper_id": hit.payload["paper_id"],
                    "text_type": hit.payload.get("text_type"),
                    "score": hit.score,
                    "payload": hit.payload
                }
                for hit in results
            ]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def hybrid_search(
        self,
        query: str,
        keyword_filter: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining semantic and keyword filters."""
        # Semantic search first
        semantic_results = self.semantic_search(query, limit=limit * 2)
        
        # Apply keyword filters if provided
        if keyword_filter:
            filtered = []
            for result in semantic_results:
                # This would need DB lookup to apply keyword filters
                # For now, return semantic results
                filtered.append(result)
            return filtered[:limit]
        
        return semantic_results[:limit]

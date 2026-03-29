"""ChromaDB vector store for concept embeddings.

Adapted from yoga-companion local-first RAG pattern.
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from ai_tutor.config import get_settings


class VectorStore:
    """
    Local-first vector store using ChromaDB.
    
    Stores concept embeddings for semantic retrieval.
    """
    
    def __init__(self, persist_directory: Optional[Path] = None):
        self.settings = get_settings()
        self.persist_directory = persist_directory or self.settings.absolute_vector_path
        self._client: Optional[chromadb.PersistentClient] = None
        self._embedding_model: Optional[SentenceTransformer] = None
        self._model_name = self.settings.embed_model
    
    def _get_client(self) -> chromadb.PersistentClient:
        """Get or create ChromaDB client."""
        if not CHROMA_AVAILABLE:
            raise RuntimeError("ChromaDB not installed. Run: pip install chromadb")
        
        if self._client is None:
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        return self._client
    
    def _get_embedding_model(self) -> SentenceTransformer:
        """Get or load sentence transformer model."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError("sentence-transformers not installed")
        
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(self._model_name)
        return self._embedding_model
    
    def embed_text(self, text: str) -> List[float]:
        """Embed text into vector."""
        model = self._get_embedding_model()
        return model.encode(text, normalize_embeddings=True).tolist()
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Batch embed texts."""
        model = self._get_embedding_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()
    
    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Get or create a ChromaDB collection."""
        client = self._get_client()
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_documents(
        self,
        collection_name: str,
        ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add documents with embeddings to collection."""
        collection = self.get_or_create_collection(collection_name)
        embeddings = self.embed_texts(texts)
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas or [{}] * len(ids)
        )
    
    def search(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over collection.
        
        Returns list of dicts with keys:
        - id: document id
        - document: text content
        - metadata: associated metadata
        - distance: cosine distance (lower is better)
        - score: similarity score (higher is better)
        """
        collection = self.get_or_create_collection(collection_name)
        query_embedding = self.embed_text(query)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            formatted.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": distance,
                "score": 1.0 - distance  # Convert to similarity score
            })
        
        return formatted
    
    def hybrid_search(
        self,
        collection_name: str,
        query: str,
        keywords: Optional[List[str]] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic + keyword matching.
        
        ZDS Pattern: Dense retrieval + lexical boost
        """
        # Get semantic results
        semantic_results = self.search(collection_name, query, n_results=n_results * 2)
        
        if not keywords:
            return semantic_results[:n_results]
        
        # Boost scores for keyword matches
        query.lower()
        keyword_set = set(k.lower() for k in keywords)
        
        for result in semantic_results:
            doc_lower = result["document"].lower()
            keyword_matches = sum(1 for kw in keyword_set if kw in doc_lower)
            
            # Boost semantic score with keyword overlap
            boost = 0.1 * keyword_matches
            result["score"] = min(1.0, result["score"] + boost)
            result["keyword_matches"] = keyword_matches
        
        # Re-sort by boosted score
        semantic_results.sort(key=lambda x: x["score"], reverse=True)
        return semantic_results[:n_results]
    
    def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        client = self._get_client()
        try:
            client.delete_collection(name)
        except Exception:
            pass
    
    def list_collections(self) -> List[str]:
        """List all collections."""
        client = self._get_client()
        return [c.name for c in client.list_collections()]
    
    def collection_stats(self, name: str) -> Dict[str, Any]:
        """Get collection statistics."""
        collection = self.get_or_create_collection(name)
        count = collection.count()
        return {
            "name": name,
            "document_count": count,
            "embedding_model": self._model_name
        }


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create vector store singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def generate_id(text: str, prefix: str = "") -> str:
    """Generate deterministic ID from text."""
    hash_val = hashlib.sha256(text.encode()).hexdigest()[:16]
    if prefix:
        return f"{prefix}-{hash_val}"
    return hash_val

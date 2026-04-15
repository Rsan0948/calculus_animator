"""Curriculum ingestion pipeline.

Builds ConceptCards from curriculum.txt and calculus_library.json,
then indexes them for RAG retrieval.

ZDS-ID: TOOL-102 (Doctrine RAG Stack - Ingestion)
"""

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from ai_tutor.rag.concept_engine import ConceptEngine, get_concept_engine


def ingest_curriculum(
    curriculum_path: Optional[Path] = None,
    formula_library_path: Optional[Path] = None,
    force_rebuild: bool = False
) -> Dict[str, Any]:
    """
    Ingest curriculum files and build RAG index.
    
    Args:
        curriculum_path: Path to curriculum.txt
        formula_library_path: Path to calculus_library.json
        force_rebuild: Rebuild even if index exists
    
    Returns:
        Dict with ingestion stats
    """
    # Find default paths
    base_dir = Path(__file__).parent.parent.parent
    
    if curriculum_path is None:
        curriculum_path = base_dir / "curriculum.txt"
    
    if formula_library_path is None:
        formula_library_path = base_dir / "data" / "calculus_library.json"
    
    
    # Check files exist
    if not curriculum_path.exists():
        return {"error": f"Curriculum not found: {curriculum_path}"}
    
    # Build concept cards
    engine = ConceptEngine()
    
    cards = engine.build_cards_from_curriculum(
        curriculum_path=curriculum_path,
        formula_library_path=formula_library_path
    )
    
    
    # Save cards
    engine.save_cards(cards)
    
    # Build indices
    index_stats = engine.index_cards(cards)
    
    # Summary
    topics = sorted(set(c.topic for c in cards))
    
    return {
        "cards_created": len(cards),
        "topics": topics,
        "curriculum_source": str(curriculum_path),
        "formula_source": str(formula_library_path.name) if formula_library_path.exists() else None,
        "cards_file": str(engine.cards_path),
        "index_file": str(engine.index_path),
        **index_stats
    }
    
    


def verify_index() -> Dict[str, Any]:
    """Verify the current index and print diagnostics."""
    engine = get_concept_engine()
    
    if not engine.cards_path.exists():
        return {"status": "error", "message": "No index found. Run ingestion first."}
    
    cards = engine.load_cards()
    
    # Check vector store
    from ai_tutor.rag.vector_store import get_vector_store
    vector_store = get_vector_store()
    
    try:
        collection_stats = vector_store.collection_stats("calculus_concepts")
    except Exception as e:
        collection_stats = {"error": str(e)}
    
    # Topic distribution
    topic_counts = {}
    for c in cards:
        topic_counts[c.topic] = topic_counts.get(c.topic, 0) + 1
    
    return {
        "status": "ok",
        "card_count": len(cards),
        "vector_stats": collection_stats,
        "topic_distribution": topic_counts,
        "cards_path": str(engine.cards_path),
        "index_path": str(engine.index_path)
    }


def test_retrieval(query: str, topic: Optional[str] = None) -> None:
    """Test concept retrieval for a query."""
    engine = get_concept_engine()
    
    if topic:
        pass
    
    concepts = engine.search(query, topic=topic, max_cards=3)
    
    for _i, _c in enumerate(concepts, 1):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest calculus curriculum for AI Tutor")
    parser.add_argument("--curriculum", type=Path, help="Path to curriculum.txt")
    parser.add_argument("--formulas", type=Path, help="Path to calculus_library.json")
    parser.add_argument("--force", action="store_true", help="Force rebuild")
    parser.add_argument("--verify", action="store_true", help="Verify existing index")
    parser.add_argument("--test", type=str, help="Test query for retrieval")
    parser.add_argument("--test-topic", type=str, help="Topic filter for test query")
    
    args = parser.parse_args()
    
    if args.verify:
        result = verify_index()
    elif args.test:
        test_retrieval(args.test, args.test_topic)
    else:
        result = ingest_curriculum(
            curriculum_path=args.curriculum,
            formula_library_path=args.formulas,
            force_rebuild=args.force
        )

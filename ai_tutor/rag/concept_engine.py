"""Concept Engine - RAG for Calculus Knowledge.

ZDS-ID: TOOL-102 (Doctrine RAG Stack adapted for Calculus)
ZDS-ID: TOOL-402 (Schema-Driven Curriculum Framework)

Converts curriculum artifacts into structured ConceptCards with:
- Hybrid retrieval (semantic + keyword)
- Pre-computed question triggers
- Failure mode detection
- Source-prioritized ranking
"""

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from sentence_transformers import CrossEncoder
    RERANK_AVAILABLE = True
except ImportError:
    RERANK_AVAILABLE = False

from ai_tutor.config import get_settings
from ai_tutor.rag.vector_store import generate_id, get_vector_store

# Calculus topic taxonomy
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "derivatives": [
        "derivative", "differentiate", "slope", "rate", "tangent", "chain rule",
        "product rule", "quotient rule"
    ],
    "integrals": [
        "integral", "integrate", "antiderivative", "area", "definite", "indefinite",
        "substitution", "by parts"
    ],
    "limits": [
        "limit", "approach", "infinity", "continuity", "lhopital", "epsilon", "delta"
    ],
    "series": [
        "series", "sequence", "convergence", "divergence", "taylor", "maclaurin",
        "power series"
    ],
    "differential_equations": [
        "ode", "differential equation", "separable", "linear", "order", "homogeneous"
    ],
    "multivariable": [
        "partial", "gradient", "multiple integral", "jacobian", "level curve", "contour"
    ],
    "applications": [
        "optimization", "related rates", "curve sketching", "area between curves",
        "volume", "work"
    ],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _word_count(text: str) -> int:
    return len(text.split())


def _safe_slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-").strip("-")
    return text or "concept"


def _extract_tags(text: str, limit: int = 10) -> List[str]:
    """Extract relevant tags from text."""
    freq: Dict[str, int] = {}
    stopwords = {
        "that", "with", "from", "this", "into", "your", "have", "will",
        "they", "when", "where", "what", "than"
    }
    
    for tok in _tokenize(text):
        if len(tok) < 4 or tok in stopwords:
            continue
        freq[tok] = freq.get(tok, 0) + 1
    
    # Also check for topic keywords
    for _topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text.lower():
                freq[kw.replace(" ", "_")] = freq.get(kw.replace(" ", "_"), 0) + 3
    
    tags = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in tags[:limit]]


def _detect_topic(text: str) -> str:
    """Detect primary topic from text."""
    text_lower = text.lower()
    scores: Dict[str, int] = {}
    
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score
    
    if not scores:
        return "general"
    
    return max(scores.items(), key=lambda x: x[1])[0]


def _build_question_triggers(concept_name: str, tags: List[str]) -> List[str]:
    """Build pre-computed question triggers for this concept."""
    triggers = [
        f"How do I solve {concept_name}?",
        f"What is the formula for {concept_name}?",
        f"When do I use {concept_name}?",
    ]
    
    if tags:
        tag_str = tags[0].replace("_", " ")
        triggers.extend([
            f"Explain {tag_str}",
            f"Why use {tag_str}?",
        ])
    
    return triggers


def _extract_failure_modes(text: str, concept_name: str) -> List[str]:
    """Extract or generate common mistakes for this concept."""
    failure_keywords = [
        "forget", "mistake", "error", "wrong", "incorrect", "common",
        "watch out", "caution"
    ]
    text_lower = text.lower()
    
    failures = []
    for kw in failure_keywords:
        if kw in text_lower:
            # Find the sentence containing the keyword
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for sent in sentences:
                if kw in sent.lower() and len(sent) > 20:
                    failures.append(_normalize_ws(sent))
                    break
    
    # Add generic failure modes if none found
    if not failures:
        failures = [
            f"Forgetting the conditions under which {concept_name} applies",
            f"Sign errors when applying {concept_name}",
            f"Not checking if the answer makes sense after using {concept_name}",
        ]
    
    return failures[:4]


def _chunk_content(text: str, target_words: int = 300, max_words: int = 500) -> List[str]:
    """
    Chunk text into semantically coherent pieces.
    
    Strategy: Split on double newlines (paragraphs) first,
    then combine small chunks, split large ones.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    chunks = []
    current_chunk = []
    current_words = 0
    
    for para in paragraphs:
        para_words = _word_count(para)
        
        # Skip header lines
        if para.startswith("#"):
            continue
        
        # If paragraph alone is too big, split on sentences
        if para_words > max_words:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_words = 0
            
            sentences = re.split(r'(?<=[.!?])\s+', para)
            sent_chunk = []
            sent_words = 0
            
            for sent in sentences:
                sw = _word_count(sent)
                if sent_words + sw > max_words and sent_chunk:
                    chunks.append(" ".join(sent_chunk))
                    sent_chunk = [sent]
                    sent_words = sw
                else:
                    sent_chunk.append(sent)
                    sent_words += sw
            
            if sent_chunk:
                chunks.append(" ".join(sent_chunk))
        
        # If adding this paragraph exceeds max, start new chunk
        elif current_words + para_words > max_words and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_words = para_words
        
        else:
            current_chunk.append(para)
            current_words += para_words
        
        # If we have enough words, finalize chunk
        if current_words >= target_words:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_words = 0
    
    # Add remaining content
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    
    return chunks


@dataclass
class ConceptCard:
    """
    Structured concept for RAG.
    
    Adapted from DoctrineCard pattern for calculus domain.
    """
    card_id: str
    concept_name: str
    topic: str
    subtopics: List[str]
    tags: List[str]
    question_triggers: List[str]
    core_formula: str
    when_to_use: str
    failure_modes: List[str]
    worked_example: str
    body: str
    source_file: str
    token_count: int
    
    def as_search_text(self) -> str:
        """Combine all searchable text."""
        parts = [
            self.concept_name,
            self.topic,
            " ".join(self.subtopics),
            " ".join(self.tags),
            self.core_formula,
            self.when_to_use,
            self.body,
        ]
        return "\n".join(p for p in parts if p)
    
    def to_context_string(self) -> str:
        """Format for LLM context injection."""
        lines = [
            f"Concept: {self.concept_name}",
            f"Topic: {self.topic}",
            f"Formula/Rule: {self.core_formula}",
            f"When to use: {self.when_to_use}",
            f"Common mistakes: {'; '.join(self.failure_modes)}",
            f"Explanation:\n{self.body[:800]}",  # Truncate if too long
        ]
        return "\n\n".join(lines)


class ConceptEngine:
    """
    RAG engine for calculus concepts.
    
    Combines:
    - Vector store (dense retrieval)
    - SQLite FTS5 (lexical retrieval)
    - Cross-encoder reranking
    - Topic routing
    """
    
    COLLECTION_NAME = "calculus_concepts"
    
    def __init__(
        self,
        cards_path: Optional[Path] = None,
        index_path: Optional[Path] = None,
    ) -> None:
        self.settings = get_settings()
        self.vector_store = get_vector_store()
        
        # Paths
        base_dir = Path(__file__).parent.parent.parent
        self.cards_path = cards_path or (base_dir / "data" / "concepts.jsonl")
        self.index_path = index_path or (base_dir / "data" / "concepts.db")
        
        self._cards_cache: Optional[List[ConceptCard]] = None
        self._rerank_model: Optional[Any] = None
    
    def _get_rerank_model(self) -> None:
        """Load cross-encoder reranker."""
        if not RERANK_AVAILABLE:
            return None
        if self._rerank_model is None and self.settings.rerank_enabled:
            try:
                self._rerank_model = CrossEncoder(self.settings.rerank_model)
            except Exception as e:
                logger.debug(f"Failed to load rerank model: {e}")
        return self._rerank_model
    
    def _extract_formula(self, text: str) -> str:
        """Extract LaTeX formula from text."""
        # Look for $$...$$ or $...$
        formulas = re.findall(r'\$\$(.+?)\$\$', text, re.DOTALL)
        if formulas:
            return f"$${formulas[0]}$$"
        
        inline = re.findall(r'\$(.+?)\$', text)
        if inline:
            return f"${inline[0]}$"
        
        return ""
    
    def _extract_when_to_use(self, text: str) -> str:
        """Extract 'when to use' guidance."""
        patterns = [
            r'(?:use|apply).+?when(.{0,200})',
            r'when.+?(?:use|apply)(.{0,200})',
            r'good for(.{0,200})',
            r'applies to(.{0,200})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return _normalize_ws(match.group(1))
        
        return "See explanation for usage conditions."
    
    def _extract_worked_example(self, text: str) -> str:
        """Extract worked example if present."""
        # Look for "Example:" or numbered examples
        pat = r'(?:example|ex\.?)\s*[:\d]?\s*(.+?)(?=\n\n|\Z)'
        example_match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if example_match:
            return _normalize_ws(example_match.group(1))[:500]
        
        # Look for "For example," or "e.g.,"
        eg_pat = r'(?:for example|e\.g\.),?\s*(.{0,400})'
        eg_match = re.search(eg_pat, text, re.IGNORECASE)
        if eg_match:
            return _normalize_ws(eg_match.group(1))
        
        return ""
    
    def build_cards_from_curriculum(
        self,
        curriculum_path: Path,
        formula_library_path: Optional[Path] = None
    ) -> List[ConceptCard]:
        """
        Build ConceptCards from curriculum and formula library.
        
        This is the ingestion pipeline.
        """
        cards = []
        
        # Process curriculum.txt
        if curriculum_path.exists():
            curriculum_text = curriculum_path.read_text(encoding="utf-8")
            
            # Split into lessons/sections
            lessons = re.split(r'\n#{2,3}\s+', curriculum_text)
            
            for _i, lesson in enumerate(lessons):
                if not lesson.strip():
                    continue
                
                lines = lesson.strip().split("\n")
                title = lines[0].strip("# ")
                content = "\n".join(lines[1:])
                
                # Chunk if too long
                chunks = _chunk_content(content)
                
                for j, chunk in enumerate(chunks):
                    topic = _detect_topic(chunk)
                    tags = _extract_tags(chunk)
                    
                    card = ConceptCard(
                        card_id=generate_id(f"{title}-{j}", "curriculum"),
                        concept_name=title if j == 0 else f"{title} (part {j+1})",
                        topic=topic,
                        subtopics=tags[:4],
                        tags=tags,
                        question_triggers=_build_question_triggers(title, tags),
                        core_formula=self._extract_formula(chunk),
                        when_to_use=self._extract_when_to_use(chunk),
                        failure_modes=_extract_failure_modes(chunk, title),
                        worked_example=self._extract_worked_example(chunk),
                        body=chunk,
                        source_file=str(curriculum_path.name),
                        token_count=_word_count(chunk)
                    )
                    cards.append(card)
        
        # Process formula library
        if formula_library_path and formula_library_path.exists():
            try:
                # Validate path is within project directory (path traversal protection)
                base_dir = Path(__file__).parent.parent.parent.resolve()
                target = formula_library_path.resolve()
                try:
                    target.relative_to(base_dir)
                except ValueError:
                    raise ValueError(f"Formula library path must be within project directory: {formula_library_path}")
                
                # guardrails: allow-path-traversal
                # Path validated above: must be within project directory
                with open(formula_library_path) as f:
                    formulas = json.load(f)
                
                for _category, items in formulas.items():
                    for item in items:
                        name = item.get("name", "")
                        formula = item.get("formula", "")
                        explanation = item.get("explanation", "")
                        
                        content = f"{name}\n{formula}\n{explanation}"
                        topic = _detect_topic(content)
                        tags = _extract_tags(content)
                        
                        card = ConceptCard(
                            card_id=generate_id(f"{name}-formula", "formula"),
                            concept_name=name,
                            topic=topic,
                            subtopics=tags[:4],
                            tags=tags,
                            question_triggers=_build_question_triggers(name, tags),
                            core_formula=formula,
                            when_to_use=explanation[:200],
                            failure_modes=_extract_failure_modes(content, name),
                            worked_example="",
                            body=content,
                            source_file=str(formula_library_path.name),
                            token_count=_word_count(content)
                        )
                        cards.append(card)
            except Exception:
                pass
        
        return cards
    
    def save_cards(self, cards: List[ConceptCard]) -> None:
        """Save cards to JSONL."""
        self.cards_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cards_path, "w", encoding="utf-8") as f:
            for card in cards:
                f.write(json.dumps(asdict(card), ensure_ascii=True) + "\n")
    
    def load_cards(self) -> List[ConceptCard]:
        """Load cards from JSONL."""
        if not self.cards_path.exists():
            return []
        
        cards = []
        with open(self.cards_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    cards.append(ConceptCard(**data))
        
        return cards
    
    def index_cards(self, cards: Optional[List[ConceptCard]] = None) -> Dict[str, Any]:
        """
        Index cards into vector store and SQLite FTS.
        
        Returns stats about the indexing.
        """
        if cards is None:
            cards = self.load_cards()
        
        if not cards:
            return {"error": "No cards to index"}
        
        # Index to vector store
        ids = [c.card_id for c in cards]
        texts = [c.as_search_text() for c in cards]
        metadatas = [
            {
                "topic": c.topic,
                "concept_name": c.concept_name,
                "source": c.source_file
            }
            for c in cards
        ]
        
        # Clear and re-add
        try:
            self.vector_store.delete_collection(self.COLLECTION_NAME)
        except Exception as e:
            logger.debug(f"Failed to delete collection (might not exist): {e}")
        
        self.vector_store.add_documents(
            self.COLLECTION_NAME,
            ids=ids,
            texts=texts,
            metadatas=metadatas
        )
        
        # Build SQLite FTS index
        self._build_fts_index(cards)
        
        return {
            "cards_indexed": len(cards),
            "topics": sorted(set(c.topic for c in cards)),
            "vector_collection": self.COLLECTION_NAME
        }
    
    def _build_fts_index(self, cards: List[ConceptCard]) -> None:
        """Build SQLite FTS5 index for lexical search."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.index_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Check FTS5 availability
            try:
                conn.execute("CREATE VIRTUAL TABLE _test USING fts5(x)")
                conn.execute("DROP TABLE _test")
                fts_available = True
            except sqlite3.Error:
                fts_available = False
            
            # Create tables
            conn.execute("DROP TABLE IF EXISTS concepts")
            conn.execute("""
                CREATE TABLE concepts (
                    card_id TEXT PRIMARY KEY,
                    concept_name TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    triggers TEXT NOT NULL,
                    body TEXT NOT NULL
                )
            """)
            
            if fts_available:
                conn.execute("DROP TABLE IF EXISTS concepts_fts")
                conn.execute("""
                    CREATE VIRTUAL TABLE concepts_fts USING fts5(
                        card_id UNINDEXED,
                        concept_name,
                        topic,
                        tags,
                        triggers,
                        body
                    )
                """)
            
            # Insert data
            for card in cards:
                conn.execute(
                    "INSERT INTO concepts VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        card.card_id,
                        card.concept_name,
                        card.topic,
                        " ".join(card.tags),
                        " ".join(card.question_triggers),
                        card.body
                    )
                )
                
                if fts_available:
                    conn.execute(
                        "INSERT INTO concepts_fts VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            card.card_id,
                            card.concept_name,
                            card.topic,
                            " ".join(card.tags),
                            " ".join(card.question_triggers),
                            card.body
                        )
                    )
            
            conn.commit()
        finally:
            conn.close()
    
    def search(
        self,
        query: str,
        topic: Optional[str] = None,
        max_cards: int = 3,
        use_rerank: bool = True
    ) -> List[ConceptCard]:
        """
        Hybrid search for concepts.
        
        Pipeline:
        1. Vector semantic search
        2. Keyword trigger matching
        3. Optional cross-encoder rerank
        """
        # Get vector results
        vector_results = self.vector_store.search(
            self.COLLECTION_NAME,
            query,
            n_results=max_cards * 3
        )
        
        # Load card details
        all_cards = {c.card_id: c for c in self.load_cards()}
        
        scored_cards = []
        for result in vector_results:
            card_id = result["id"]
            if card_id in all_cards:
                card = all_cards[card_id]
                
                # Base score from vector similarity
                score = result["score"]
                
                # Boost for topic match
                if topic and card.topic == topic:
                    score += 0.2
                
                # Boost for trigger keyword matches
                query_lower = query.lower()
                for trigger in card.question_triggers:
                    if any(word in trigger.lower() for word in query_lower.split()):
                        score += 0.15
                
                scored_cards.append((card, score))
        
        # Sort by score
        scored_cards.sort(key=lambda x: x[1], reverse=True)
        
        # Rerank with cross-encoder if available
        if use_rerank and len(scored_cards) > 1:
            rerank_model = self._get_rerank_model()
            if rerank_model:
                top_candidates = scored_cards[:max_cards * 2]
                pairs = [(query, c.as_search_text()) for c, _ in top_candidates]
                rerank_scores = rerank_model.predict(pairs)
                
                # Blend scores
                reranked = []
                for i, (card, base_score) in enumerate(top_candidates):
                    final_score = 0.4 * base_score + 0.6 * rerank_scores[i]
                    reranked.append((card, final_score))
                
                reranked.sort(key=lambda x: x[1], reverse=True)
                return [c for c, _ in reranked[:max_cards]]
        
        return [c for c, _ in scored_cards[:max_cards]]
    
    def get_by_topic(self, topic: str) -> List[ConceptCard]:
        """Get all cards for a topic."""
        cards = self.load_cards()
        return [c for c in cards if c.topic == topic]
    
    def get_card(self, card_id: str) -> Optional[ConceptCard]:
        """Get single card by ID."""
        cards = self.load_cards()
        for c in cards:
            if c.card_id == card_id:
                return c
        return None


# Singleton
_engine: Optional[ConceptEngine] = None


def get_concept_engine() -> ConceptEngine:
    """Get or create concept engine singleton."""
    global _engine
    if _engine is None:
        _engine = ConceptEngine()
    return _engine

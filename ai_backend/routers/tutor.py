"""Tutor router - Socratic AI tutoring endpoints.

ZDS-ID: TOOL-405 (Teacher-in-the-Loop)

Provides:
- /chat: Main tutoring endpoint with RAG context
- /chat/vision: Screenshot-aware tutoring
- /context: Current solver state for UI sync
"""

import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai_tutor.config import get_settings
from ai_tutor.providers.router import (
    generate_async,
    generate_stream_async,
    generate_vision_async,
)
from ai_tutor.rag.concept_engine import ConceptCard, get_concept_engine

router = APIRouter()


class SolverState(BaseModel):
    """Current state of the calculus solver."""
    expression: str = Field(..., description="LaTeX expression being solved")
    operation: Literal["derivative", "integral", "limit", "series", "simplify", "ode"] = Field(..., description="Operation type")
    step_index: int = Field(0, description="Current step number (0 = start)")
    step_count: int = Field(0, description="Total steps in solution")
    rule_used: Optional[str] = Field(None, description="Rule/technique being applied (e.g., 'product_rule')")
    current_latex: Optional[str] = Field(None, description="LaTeX of current step")
    difficulty: Optional[str] = Field(None, description="Detected difficulty: easy, medium, hard")


class ChatRequest(BaseModel):
    """Chat request with context."""
    message: str = Field(..., description="Student's question")
    solver_state: SolverState = Field(..., description="Current solver state")
    history: list = Field(default_factory=list, description="Previous messages [{role, content}, ...]")
    screenshot_b64: Optional[str] = Field(None, description="Base64-encoded screenshot (for vision)")


class ChatResponse(BaseModel):
    """Chat response."""
    response: str
    concepts_used: list = Field(default_factory=list, description="Concept cards retrieved")
    mode: str = "socratic"
    streaming: bool = False


# ═════════════════════════════════════════════════════════════════════════════
# SOCRATIC PROMPT ENGINE
# ═════════════════════════════════════════════════════════════════════════════

SOCRATIC_SYSTEM_PROMPT = """You are a Socratic tutor for calculus students. Your role is to guide students to discover answers themselves, not to give them directly.

CORE PRINCIPLES:
1. NEVER give the final answer immediately
2. Ask ONE guiding question at a time
3. Reference specific visual elements from the screenshot when relevant
4. Connect to the fundamental concept, not just the mechanical steps
5. If the student is stuck, provide a hint, not the solution

RESPONSE STRUCTURE:
- Start with acknowledgment of where they are (step X, working on Y)
- Ask a focused question that points them toward the next insight
- Optionally suggest what to look at in their work (the expression, a specific term, etc.)

CONVERSATION STYLE:
- Be encouraging but don't be overly chatty
- Use precise mathematical language
- Reference the concept cards provided for accurate terminology
- If they ask "just tell me the answer", explain why that won't help them learn

EXAMPLES OF GOOD RESPONSES:
❌ "The derivative of x²sin(x) is 2xsin(x) + x²cos(x) using the product rule."
✅ "You're working with a product of two functions. What does the product rule tell you about how to handle each part? Look at the formula provided in the concept reference."

❌ "You need to use integration by parts with u=x²."
✅ "Looking at ∫x²sin(x)dx, what choice of u would make du simpler than u itself? Remember the LIATE guideline from your concept reference."
"""

DIRECT_SYSTEM_PROMPT = """You are a helpful calculus tutor. Provide clear explanations and step-by-step guidance.

When explaining:
1. Reference the relevant mathematical rules and formulas
2. Walk through the reasoning process
3. Point out common pitfalls
4. Connect to the visual elements shown in the screenshot

Be thorough but concise. Use proper LaTeX for mathematical expressions.
"""


def format_concepts_for_prompt(concepts: list[ConceptCard]) -> str:
    """Format retrieved concepts for LLM context."""
    if not concepts:
        return "No specific concept cards retrieved for this query."
    
    lines = ["=== RELEVANT CALCULUS CONCEPTS ===\n"]
    
    for i, concept in enumerate(concepts, 1):
        lines.append(f"\n[{i}] {concept.concept_name}")
        lines.append(f"Topic: {concept.topic}")
        if concept.core_formula:
            lines.append(f"Formula: {concept.core_formula}")
        if concept.when_to_use:
            lines.append(f"When to use: {concept.when_to_use}")
        if concept.failure_modes:
            lines.append(f"Common mistakes: {'; '.join(concept.failure_modes[:2])}")
        lines.append(f"Explanation: {concept.body[:400]}...")
    
    return "\n".join(lines)


def format_solver_context(state: SolverState) -> str:
    """Format solver state for context."""
    lines = [
        "=== CURRENT PROBLEM STATE ===",
        f"Expression: {state.expression}",
        f"Operation: {state.operation}",
        f"Progress: Step {state.step_index + 1} of {state.step_count or 'unknown'}",
    ]
    
    if state.rule_used:
        lines.append(f"Technique being applied: {state.rule_used}")
    
    if state.current_latex:
        lines.append(f"Current expression: {state.current_latex}")
    
    if state.difficulty:
        lines.append(f"Detected difficulty: {state.difficulty}")
    
    return "\n".join(lines)


def build_tutor_prompt(
    user_message: str,
    solver_state: SolverState,
    concepts: list[ConceptCard],
    history: list,
    socratic_mode: bool = True
) -> tuple[str, str]:
    """
    Build the complete prompt for the tutor.
    
    Returns: (system_prompt, user_prompt)
    """
    system = SOCRATIC_SYSTEM_PROMPT if socratic_mode else DIRECT_SYSTEM_PROMPT
    
    # Build user prompt with all context
    parts = []
    
    # Solver context
    parts.append(format_solver_context(solver_state))
    parts.append("")
    
    # Retrieved concepts
    parts.append(format_concepts_for_prompt(concepts))
    parts.append("")
    
    # Conversation history (last 3 exchanges)
    if history:
        parts.append("=== CONVERSATION HISTORY ===")
        recent = history[-6:] if len(history) > 6 else history
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role.upper()}: {content[:200]}")
        parts.append("")
    
    # Current question
    parts.append("=== STUDENT QUESTION ===")
    parts.append(user_message)
    parts.append("")
    parts.append("Provide your Socratic response below:")
    
    user_prompt = "\n".join(parts)
    
    return system, user_prompt


def build_vision_prompt(
    user_message: str,
    solver_state: SolverState,
    concepts: list[ConceptCard],
    socratic_mode: bool = True
) -> str:
    """Build prompt for vision-capable models (includes screenshot)."""
    parts = []
    
    # Solver context
    parts.append(format_solver_context(solver_state))
    parts.append("")
    
    # Retrieved concepts
    parts.append(format_concepts_for_prompt(concepts))
    parts.append("")
    
    # Instructions for vision
    parts.append("""
=== SCREENSHOT ANALYSIS ===
The image shows the student's current view of the calculus animator. 
Reference specific visual elements you can see (graphs, equations, highlighted steps).
Connect your guidance to what's visible on screen.
""")
    
    # Student question
    parts.append("=== STUDENT QUESTION ===")
    parts.append(user_message)
    
    return "\n".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Main tutoring endpoint.
    
    1. Retrieves relevant concepts from RAG
    2. Builds context with solver state
    3. Generates Socratic response
    """
    settings = get_settings()
    engine = get_concept_engine()
    
    try:
        # Step 1: Retrieve relevant concepts (run in thread — avoids blocking event loop)
        query = f"{request.solver_state.operation} {request.solver_state.rule_used or ''} {request.message}"
        try:
            concepts = await asyncio.wait_for(
                asyncio.to_thread(engine.search, query=query, topic=request.solver_state.operation, max_cards=settings.max_context_cards),
                timeout=8.0
            )
        except Exception:
            concepts = []

        # Step 2: Build prompt
        system_prompt, user_prompt = build_tutor_prompt(
            user_message=request.message,
            solver_state=request.solver_state,
            concepts=concepts,
            history=request.history,
            socratic_mode=settings.socratic_mode
        )

        # Step 3: Generate response
        if settings.streaming_enabled:
            # Return streaming response
            async def async_stream():
                async for chunk in generate_stream_async(user_prompt, mode="fast", system=system_prompt):
                    yield chunk

            return StreamingResponse(
                async_stream(),
                media_type="text/event-stream",
                headers={
                    "X-Concepts-Used": ",".join([c.card_id for c in concepts]),
                    "X-Mode": "socratic" if settings.socratic_mode else "direct"
                }
            )
        # Return complete response
        response = await generate_async(user_prompt, mode="fast", system=system_prompt)

        return ChatResponse(
            response=response,
            concepts_used=[{"id": c.card_id, "name": c.concept_name} for c in concepts],
            mode="socratic" if settings.socratic_mode else "direct",
            streaming=False
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/vision")
async def chat_with_vision(request: ChatRequest):
    """
    Tutoring with screenshot analysis.
    
    Requires OpenAI (GPT-4V) or Anthropic (Claude 3) API key.
    """
    if not request.screenshot_b64:
        raise HTTPException(status_code=400, detail="screenshot_b64 required for vision endpoint")
    
    settings = get_settings()
    engine = get_concept_engine()
    
    try:
        # Step 1: Retrieve concepts (run in thread — avoids blocking event loop)
        query = f"{request.solver_state.operation} {request.solver_state.rule_used or ''} {request.message}"
        try:
            concepts = await asyncio.wait_for(
                asyncio.to_thread(engine.search, query=query, topic=request.solver_state.operation, max_cards=settings.max_context_cards),
                timeout=8.0
            )
        except Exception:
            concepts = []

        # Step 2: Build vision prompt
        system = SOCRATIC_SYSTEM_PROMPT if settings.socratic_mode else DIRECT_SYSTEM_PROMPT
        user_prompt = build_vision_prompt(
            user_message=request.message,
            solver_state=request.solver_state,
            concepts=concepts,
            socratic_mode=settings.socratic_mode
        )
        
        # Step 3: Generate with vision
        response = await generate_vision_async(
            prompt=user_prompt,
            image_b64=request.screenshot_b64,
            mode="fast",
            system=system
        )
        
        return ChatResponse(
            response=response,
            concepts_used=[{"id": c.card_id, "name": c.concept_name} for c in concepts],
            mode="socratic" if settings.socratic_mode else "direct",
            streaming=False
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming version of chat endpoint."""
    settings = get_settings()
    engine = get_concept_engine()
    
    try:
        # Retrieve concepts (run in thread — avoids blocking event loop)
        query = f"{request.solver_state.operation} {request.solver_state.rule_used or ''} {request.message}"
        try:
            concepts = await asyncio.wait_for(
                asyncio.to_thread(engine.search, query=query, topic=request.solver_state.operation, max_cards=settings.max_context_cards),
                timeout=8.0
            )
        except Exception:
            concepts = []

        # Build prompt
        system_prompt, user_prompt = build_tutor_prompt(
            user_message=request.message,
            solver_state=request.solver_state,
            concepts=concepts,
            history=request.history,
            socratic_mode=settings.socratic_mode
        )
        
        # Stream response
        async def async_stream():
            async for chunk in generate_stream_async(user_prompt, mode="fast", system=system_prompt):
                yield chunk

        return StreamingResponse(
            async_stream(),
            media_type="text/event-stream"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/concepts/search")
async def search_concepts(
    q: str,
    topic: Optional[str] = None,
    limit: int = 5
):
    """Search concept cards (for debugging/verification)."""
    engine = get_concept_engine()
    concepts = engine.search(q, topic=topic, max_cards=limit)
    
    return {
        "query": q,
        "results": [
            {
                "id": c.card_id,
                "name": c.concept_name,
                "topic": c.topic,
                "tags": c.tags,
                "formula": c.core_formula,
                "preview": c.body[:200] + "..."
            }
            for c in concepts
        ]
    }


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """Get specific concept card by ID."""
    engine = get_concept_engine()
    card = engine.get_card(concept_id)
    
    if not card:
        raise HTTPException(status_code=404, detail="Concept not found")
    
    return {
        "id": card.card_id,
        "name": card.concept_name,
        "topic": card.topic,
        "subtopics": card.subtopics,
        "tags": card.tags,
        "formula": card.core_formula,
        "when_to_use": card.when_to_use,
        "failure_modes": card.failure_modes,
        "worked_example": card.worked_example,
        "body": card.body
    }

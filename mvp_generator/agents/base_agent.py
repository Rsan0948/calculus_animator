"""Base class for all swarm agents."""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when LLM call fails after all retries."""
    pass


class BaseSwarmAgent:
    """Base agent with LLM capabilities and common prompt logic."""

    def __init__(self, name: str, role: str, model: str = "gemini-1.5-pro") -> None:
        self.name = name
        self.role = role
        
        # Get API key from environment
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set - agent %s may fail", name)
        
        self.llm = ChatGoogleGenerativeAI(
            model=model, 
            temperature=0.1,
            google_api_key=api_key
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def _generate_with_retry(
        self, 
        messages: List[BaseMessage]
    ) -> str:
        """Call the LLM with retry logic.
        
        Retries on transient failures with exponential backoff.
        """
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.warning("Agent %s LLM call failed (will retry): %s", self.name, e)
            raise

    def _generate(
        self, 
        prompt: str, 
        system_msg: Optional[str] = None,
        history: Optional[List[BaseMessage]] = None
    ) -> str:
        """Call the LLM with the given prompt and system message.
        
        Args:
            prompt: The user prompt.
            system_msg: Optional system message override.
            history: Optional conversation history.
            
        Returns:
            LLM response content.
            
        Raises:
            LLMError: If all retries are exhausted.
        """
        messages = []
        if system_msg:
            messages.append(SystemMessage(content=system_msg))
        else:
            messages.append(SystemMessage(content=f"You are the {self.name}. {self.role}"))
            
        if history:
            messages.extend(history)
            
        messages.append(HumanMessage(content=prompt))
        
        try:
            return self._generate_with_retry(messages)
        except Exception as e:
            logger.error("Agent %s failed after all retries: %s", self.name, e)
            raise LLMError(f"Agent {self.name} failed: {e}") from e
    
    def _strip_markdown_code(self, response: str) -> str:
        """Strip markdown code blocks from LLM response."""
        response = response.strip()
        if response.startswith("```python"):
            return response.split("```python", 1)[1].split("```", 1)[0].strip()
        elif response.startswith("```"):
            return response.split("```", 1)[1].split("```", 1)[0].strip()
        return response

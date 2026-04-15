"""Base class for all swarm agents."""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class BaseSwarmAgent:
    """Base agent with LLM capabilities and common prompt logic."""

    def __init__(self, name: str, role: str, model: str = "gemini-1.5-pro"):
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

    def _generate(
        self, 
        prompt: str, 
        system_msg: Optional[str] = None,
        history: Optional[List[BaseMessage]] = None
    ) -> str:
        """Call the LLM with the given prompt and system message."""
        messages = []
        if system_msg:
            messages.append(SystemMessage(content=system_msg))
        else:
            messages.append(SystemMessage(content=f"You are the {self.name}. {self.role}"))
            
        if history:
            messages.extend(history)
            
        messages.append(HumanMessage(content=prompt))
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error("Agent %s failed: %s", self.name, e)
            raise
    
    def _strip_markdown_code(self, response: str) -> str:
        """Strip markdown code blocks from LLM response."""
        response = response.strip()
        if response.startswith("```python"):
            return response.split("```python", 1)[1].split("```", 1)[0].strip()
        elif response.startswith("```"):
            return response.split("```", 1)[1].split("```", 1)[0].strip()
        return response

"""
Pydantic schemas for structured outputs as required by the test.
All outputs follow clearly defined schemas for session summarization and query understanding.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ===== Session Memory Schemas =====

class UserProfile(BaseModel):
    """User preferences and constraints from the conversation."""
    preferences: List[str] = Field(default_factory=list, description="User's stated preferences")
    constraints: List[str] = Field(default_factory=list, description="User's constraints or limitations")


class SessionSummary(BaseModel):
    """
    Structured session summary output.
    Generated when conversation context exceeds token threshold.
    """
    user_profile: UserProfile = Field(description="User preferences and constraints")
    key_facts: List[str] = Field(default_factory=list, description="Important facts mentioned in conversation")
    decisions: List[str] = Field(default_factory=list, description="Decisions made during conversation")
    open_questions: List[str] = Field(default_factory=list, description="Unresolved questions")
    todos: List[str] = Field(default_factory=list, description="Action items or tasks mentioned")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_profile": {
                    "preferences": ["Python development", "Clean code practices"],
                    "constraints": ["7 day deadline", "Must use LangGraph"]
                },
                "key_facts": ["Working on AI internship test", "Using Streamlit for UI"],
                "decisions": ["Use SQLite for storage", "Implement token counting with tiktoken"],
                "open_questions": ["Which LLM provider to use?"],
                "todos": ["Set up project structure", "Write documentation"]
            }
        }


class MessageRange(BaseModel):
    """Range of messages that were summarized."""
    from_index: int = Field(ge=0, description="Starting message index (inclusive)")
    to_index: int = Field(ge=0, description="Ending message index (inclusive)")


class SessionMemoryOutput(BaseModel):
    """
    Complete output from the Summarizer Agent.
    Includes the summary and metadata about what was summarized.
    """
    session_summary: SessionSummary
    message_range_summarized: MessageRange
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_summary": {
                    "user_profile": {"preferences": [], "constraints": []},
                    "key_facts": [],
                    "decisions": [],
                    "open_questions": [],
                    "todos": []
                },
                "message_range_summarized": {"from_index": 0, "to_index": 42},
                "timestamp": "2026-01-30T10:00:00"
            }
        }


# ===== Query Understanding Schemas =====

class QueryUnderstanding(BaseModel):
    """
    Structured output from Query Understanding Agent.
    Handles query rewriting, context augmentation, and clarification.
    """
    original_query: str = Field(description="The user's original query")
    is_ambiguous: bool = Field(description="Whether the query is ambiguous or unclear")
    rewritten_query: Optional[str] = Field(None, description="Clarified/paraphrased version if ambiguous")
    possible_interpretations: List[str] = Field(
        default_factory=list,
        description="2-3 possible meanings if query is ambiguous"
    )
    needed_context_from_memory: List[str] = Field(
        default_factory=list,
        description="Fields from session memory needed for context"
    )
    clarifying_questions: List[str] = Field(
        default_factory=list,
        description="Questions to ask user if intent is still unclear (1-3 questions)"
    )
    final_augmented_context: str = Field(
        default="",
        description="Combined context from recent messages + session memory"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "original_query": "scrape football data",
                "is_ambiguous": True,
                "rewritten_query": "Scrape football data: could be match results, standings, or player statistics",
                "possible_interpretations": [
                    "Match results (scores, dates, teams)",
                    "League standings (team rankings, points)",
                    "Player statistics (goals, assists, cards)"
                ],
                "needed_context_from_memory": ["user_profile.preferences"],
                "clarifying_questions": [],
                "final_augmented_context": "User is working on web scraping project..."
            }
        }


# ===== Message Schema =====

class Message(BaseModel):
    """
    Individual message in the conversation.
    Used for storing and retrieving conversation history.
    """
    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    token_count: Optional[int] = Field(None, description="Number of tokens in this message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (query_analysis, summary_triggered, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "Hello, I need help with my project",
                "timestamp": "2026-01-30T10:00:00",
                "token_count": 8,
                "metadata": {
                    "query_analysis": {
                        "is_ambiguous": False,
                        "rewritten_query": None
                    }
                }
            }
        }


# ===== Graph State Schema =====

class ConversationState(BaseModel):
    """
    State object passed between LangGraph agents.
    Tracks conversation flow and intermediate results.
    """
    session_id: str = Field(description="Unique session identifier")
    messages: List[Message] = Field(default_factory=list, description="Current conversation messages")
    total_tokens: int = Field(default=0, description="Total token count in current context")
    needs_summarization: bool = Field(default=False, description="Whether summarization should be triggered")
    session_summary: Optional[SessionMemoryOutput] = Field(None, description="Current session summary if exists")
    query_understanding: Optional[QueryUnderstanding] = Field(None, description="Query analysis result")
    final_response: str = Field(default="", description="Final assistant response")
    
    class Config:
        arbitrary_types_allowed = True

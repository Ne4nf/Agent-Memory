"""
LangGraph orchestrator - connects all agents in a workflow.
Implements conditional flows based on conversation state.
"""

from typing import TypedDict, Annotated, Sequence, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from .agents import Agents
from .schemas import Message, QueryUnderstanding, SessionMemoryOutput


class GraphState(TypedDict):
    """State schema for the LangGraph workflow."""
    session_id: str
    user_query: str
    messages: Sequence[Message]
    total_tokens: int
    needs_summarization: bool
    session_summary: SessionMemoryOutput | None
    query_understanding: QueryUnderstanding | None
    final_response: str


class ConversationGraph:
    """
    LangGraph orchestrator for the conversation pipeline.
    
    Flow:
    1. Context Agent → Load messages, count tokens
    2. (Conditional) Summarizer Agent → If threshold exceeded
    3. Query Agent → Analyze query, augment context
    4. Response Agent → Generate final response
    """
    
    def __init__(self, agents: Agents):
        """
        Initialize the conversation graph.
        
        Args:
            agents: Agents instance with all agent implementations
        """
        self.agents = agents
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with conditional routing."""
        
        # Create graph
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("context_agent", self.agents.context_agent)
        workflow.add_node("summarizer_agent", self.agents.summarizer_agent)
        workflow.add_node("query_agent", self.agents.query_agent)
        workflow.add_node("response_agent", self.agents.response_agent)
        
        # Set entry point
        workflow.set_entry_point("context_agent")
        
        # Add conditional edge: Context → Summarizer (if needed) OR Query
        def should_summarize(state: GraphState) -> Literal["summarizer_agent", "query_agent"]:
            """Decide if summarization is needed."""
            if state.get("needs_summarization", False):
                return "summarizer_agent"
            return "query_agent"
        
        workflow.add_conditional_edges(
            "context_agent",
            should_summarize,
            {
                "summarizer_agent": "summarizer_agent",
                "query_agent": "query_agent"
            }
        )
        
        # After summarization, go to query agent
        workflow.add_edge("summarizer_agent", "query_agent")
        
        # After query understanding, go to response agent
        workflow.add_edge("query_agent", "response_agent")
        
        # Response agent is the end
        workflow.add_edge("response_agent", END)
        
        return workflow.compile()
    
    def run(self, session_id: str, user_query: str) -> dict:
        """
        Run the conversation pipeline.
        
        Args:
            session_id: Unique session identifier
            user_query: User's input query
        
        Returns:
            Final state with response and metadata
        """
        initial_state = {
            "session_id": session_id,
            "user_query": user_query,
            "messages": [],
            "total_tokens": 0,
            "needs_summarization": False,
            "session_summary": None,
            "query_understanding": None,
            "final_response": ""
        }
        
        # Execute graph
        final_state = self.graph.invoke(initial_state)
        
        return final_state
    
    def visualize(self) -> str:
        """
        Get a text representation of the graph structure.
        Useful for debugging and documentation.
        """
        return """
Conversation Graph Flow:
========================

START
  ↓
[Context Agent]
  - Load messages from DB
  - Count tokens (tiktoken)
  - Check threshold
  ↓
[Decision: Needs Summarization?]
  ↓                    ↓
  YES                  NO
  ↓                    ↓
[Summarizer Agent]     |
  - Generate summary   |
  - Save to DB         |
  - Mark messages      |
  ↓                    ↓
[Query Agent] ←--------+
  - Detect ambiguity
  - Rewrite if needed
  - Augment context
  - Generate clarifying questions
  ↓
[Response Agent]
  - Use augmented context
  - Generate response
  ↓
END
"""


def create_conversation_graph(agents: Agents) -> ConversationGraph:
    """
    Factory function to create a conversation graph.
    
    Args:
        agents: Configured Agents instance
    
    Returns:
        ConversationGraph ready to run
    """
    return ConversationGraph(agents)

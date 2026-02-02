"""
LangGraph agents implementation.
Each agent handles a specific part of the conversation pipeline.
"""

import os
import json
from typing import List, Dict, Any, TypedDict
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .schemas import (
    Message,
    SessionMemoryOutput,
    SessionSummary,
    UserProfile,
    MessageRange,
    QueryUnderstanding,
    ConversationState
)
from .database import Database
from .utils import TokenCounter


class Agents:
    """Collection of LangGraph agents for the conversation pipeline."""
    
    def __init__(
        self,
        db: Database,
        model_name: str = "gemini-2.5-flash",
        token_threshold: int = 10000
    ):
        """
        Initialize agents with database and LLM configuration.
        
        Args:
            db: Database instance for storage
            model_name: Google Gemini model name
            token_threshold: Token limit before triggering summarization
        """
        self.db = db
        self.token_threshold = token_threshold
        self.token_counter = TokenCounter(model=model_name)
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.7
        )
        self.llm_structured = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.3
        )
    
    # ===== Context Agent =====
    
    def context_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Context Agent: Load messages, count tokens, check if summarization is needed.
        
        This is the entry point of the pipeline.
        - Loads conversation history from database
        - Counts tokens using tiktoken
        - Determines if summarization threshold is exceeded
        
        Args:
            state: Current conversation state
        
        Returns:
            Updated state with token counts and summarization flag
        """
        session_id = state["session_id"]
        
        # Load messages from database (exclude already summarized)
        messages = self.db.get_messages(session_id, exclude_summarized=True)
        
        # Count total tokens
        total_tokens = sum(
            self.token_counter.count_message_tokens(msg) for msg in messages
        )
        
        # Check if summarization is needed
        needs_summarization = total_tokens > self.token_threshold
        
        print(f"📊 Context Agent: {len(messages)} messages, {total_tokens} tokens")
        print(f"🔍 Summarization needed: {needs_summarization} (threshold: {self.token_threshold})")
        
        return {
            **state,
            "messages": messages,
            "total_tokens": total_tokens,
            "needs_summarization": needs_summarization
        }
    
    # ===== Summarizer Agent =====
    
    def summarizer_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarizer Agent: Create structured summary when token threshold exceeded.
        
        Generates a SessionMemoryOutput following the defined schema:
        - User profile (preferences, constraints)
        - Key facts
        - Decisions made
        - Open questions
        - Todos/action items
        
        Saves summary to database and marks messages as summarized.
        
        Args:
            state: Current conversation state
        
        Returns:
            Updated state with session summary
        """
        session_id = state["session_id"]
        messages = state.get("messages", [])
        
        if not messages:
            return state
        
        print(f"📝 Summarizer Agent: Creating summary for {len(messages)} messages...")
        
        # Get previous summary to enable rolling updates
        previous_summary = self.db.get_latest_summary(session_id)
        previous_summary_text = ""
        
        if previous_summary:
            s = previous_summary.session_summary
            previous_summary_text = f"""
Previous Summary (to be updated):
User Profile:
- Preferences: {', '.join(s.user_profile.preferences) if s.user_profile.preferences else 'None'}
- Constraints: {', '.join(s.user_profile.constraints) if s.user_profile.constraints else 'None'}
Key Facts: {', '.join(s.key_facts) if s.key_facts else 'None'}
Decisions: {', '.join(s.decisions) if s.decisions else 'None'}
Open Questions: {', '.join(s.open_questions) if s.open_questions else 'None'}
Todos: {', '.join(s.todos) if s.todos else 'None'}

Instructions: Merge the new conversation below with this previous summary. Update facts, add new decisions, resolve or add questions, update todos.
"""
            print(f"📚 Found previous summary with {len(s.key_facts)} facts - will merge updates")
        
        # Build conversation text for summarization
        conversation_text = "\n".join([
            f"{msg.role.upper()}: {msg.content}"
            for msg in messages
        ])
        
        # System prompt for structured summarization (rolling update)
        system_prompt = """You are an expert conversation analyst specializing in technical projects and requirements gathering.

Your task is to extract ACTIONABLE, SPECIFIC information from conversations, focusing on concrete facts rather than generic descriptions.

ROLLING SUMMARY STRATEGY:
- If previous summary exists: UPDATE it with new information (add new facts, update decisions, resolve questions)
- If no previous summary: CREATE fresh summary from scratch
- Keep all relevant previous information, don't lose context
- Mark resolved questions as completed in todos or remove them

CRITICAL: You MUST return ONLY a valid JSON object. No markdown, no explanations, no code blocks.

Required JSON schema:
{
  "user_profile": {
    "preferences": ["Specific tech preferences: languages, frameworks, tools, APIs"],
    "constraints": ["Concrete limitations: deadlines, budgets, technical restrictions, required features"]
  },
  "key_facts": ["Technical details: URLs, data points, libraries, versions, specific requirements"],
  "decisions": ["Concrete decisions made: which approach chosen, which tool selected, what to focus on"],
  "open_questions": ["Specific unresolved questions that need clarification"],
  "todos": ["Actionable next steps with clear deliverables"]
}

Extraction guidelines:
✅ GOOD examples:
- "preferences": ["Python with BeautifulSoup/Scrapy", "Champions League data from UEFA.com", "Store in CSV/SQLite"]
- "key_facts": ["Target: Champions League match results and player stats", "Data fields: team names, scores, dates, player names, goals/assists"]
- "decisions": ["Use Selenium for JavaScript-rendered content on UEFA.com", "Start with match results before player statistics"]
- "open_questions": ["Should we scrape from UEFA.com or multiple sources?", "Which specific data fields are most important?"]

❌ BAD examples (too generic):
- "key_facts": ["User wants to scrape data"]  → Not specific enough!
- "decisions": ["User decided to continue"]  → What decision exactly?

Rules:
1. Extract ONLY information that exists in the conversation
2. Be specific: Include tech stack names, URLs, data fields, numbers
3. Skip generic/obvious items
4. Empty arrays [] are OK if nothing meaningful found
5. Return ONLY JSON - start with { and end with }

Example response:
{"user_profile": {"preferences": ["Python", "BeautifulSoup/Scrapy libraries", "Champions League data"], "constraints": ["7-day deadline"]}, "key_facts": ["Target website: UEFA.com official site", "Data types: match results, schedules, standings, player stats", "Challenge: Site uses JavaScript rendering"], "decisions": ["Focus on structured C1 data (not news articles)", "Use Selenium for dynamic content"], "open_questions": ["Which specific website to scrape from?", "Store data in what format (CSV/JSON/Database)?"], "todos": ["Choose between UEFA.com vs multi-source approach", "Install Selenium and browser driver"]}"""
        
        human_prompt = f"""{previous_summary_text}

New Conversation to Process:
{conversation_text}

Analyze and extract structured information. {'UPDATE the previous summary with new information from the conversation above.' if previous_summary else 'Create a new summary.'}

Remember: Return ONLY valid JSON, no markdown code blocks."""
        
        # Call LLM for summarization
        response = self.llm_structured.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        
        # Parse JSON response
        try:
            # Try to extract JSON from response
            content = response.content.strip()
            
            print(f"📄 Raw LLM response length: {len(content)} chars")
            print(f"📄 First 100 chars: {content[:100]}...")
            
            # If response is wrapped in markdown code blocks, extract it
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
                print("✂️ Removed ```json``` wrapper")
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
                print("✂️ Removed ``` wrapper")
            
            summary_dict = json.loads(content)
            session_summary = SessionSummary(**summary_dict)
            print(f"✅ Successfully parsed summary: {len(summary_dict.get('key_facts', []))} facts")
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing summary JSON: {e}")
            print(f"📄 Full raw response:\n{response.content}\n")
            # Fallback to empty summary
            session_summary = SessionSummary(
                user_profile=UserProfile(preferences=[], constraints=[]),
                key_facts=[],
                decisions=[],
                open_questions=[],
                todos=[]
            )
        except Exception as e:
            print(f"❌ Unexpected error parsing summary: {e}")
            print(f"📄 Full raw response:\n{response.content}\n")
            # Fallback to empty summary
            session_summary = SessionSummary(
                user_profile=UserProfile(preferences=[], constraints=[]),
                key_facts=[],
                decisions=[],
                open_questions=[],
                todos=[]
            )
        
        # Calculate absolute indices in database
        # We need to know how many messages have been summarized already
        all_messages = self.db.get_messages(session_id, exclude_summarized=False)
        total_messages_in_db = len(all_messages)
        unsummarized_messages_count = len(messages)
        
        # from_index = (total messages in DB) - (messages in current unsummarized list)
        from_index = total_messages_in_db - unsummarized_messages_count
        to_index = total_messages_in_db - 1
        
        # Create complete output with metadata
        summary_output = SessionMemoryOutput(
            session_summary=session_summary,
            message_range_summarized=MessageRange(
                from_index=from_index,
                to_index=to_index
            ),
            timestamp=datetime.now()
        )
        
        # Save to database
        self.db.save_summary(session_id, summary_output)
        
        # ✅ CRITICAL: Mark messages as summarized to exclude them from future context
        self.db.mark_messages_as_summarized(
            session_id=session_id,
            from_index=from_index,
            to_index=to_index
        )
        
        print(f"✅ Summary saved: {len(session_summary.key_facts)} facts, "
              f"{len(session_summary.decisions)} decisions, "
              f"{len(session_summary.open_questions)} open questions")
        
        return {
            **state,
            "session_summary": summary_output,
            "needs_summarization": False
        }
    
    # ===== Query Understanding Agent =====
    
    def query_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query Understanding Agent: Analyze user query for ambiguity and context needs.
        
        Pipeline:
        1. Detect if query is ambiguous
        2. Rewrite query if needed
        3. Identify required context from session memory
        4. Generate clarifying questions if intent unclear
        5. Build augmented context
        
        Args:
            state: Current conversation state
        
        Returns:
            Updated state with QueryUnderstanding result
        """
        session_id = state["session_id"]
        user_query = state.get("user_query", "")
        
        if not user_query:
            return state
        
        print(f"🤔 Query Agent: Analyzing query...")
        
        # Get recent messages for context - increase to 10 for better context awareness
        recent_messages = self.db.get_recent_messages(session_id, n=10)
        recent_context = "\n".join([
            f"{msg.role.upper()}: {msg.content}" for msg in recent_messages
        ])
        
        if not recent_context:
            recent_context = "No previous conversation."
        
        # Get latest session summary if exists
        summary = self.db.get_latest_summary(session_id)
        summary_context = ""
        if summary:
            s = summary.session_summary
            summary_context = f"""
Session Memory:
- User preferences: {', '.join(s.user_profile.preferences) if s.user_profile.preferences else 'None'}
- Constraints: {', '.join(s.user_profile.constraints) if s.user_profile.constraints else 'None'}
- Key facts: {', '.join(s.key_facts[:3]) if s.key_facts else 'None'}
- Open questions: {', '.join(s.open_questions[:3]) if s.open_questions else 'None'}
- Todos: {', '.join(s.todos[:3]) if s.todos else 'None'}
"""
        
        # System prompt for query understanding
        system_prompt = """You are a query understanding expert.
Analyze the user's query and determine if it's ambiguous or needs clarification.

CRITICAL: You MUST return ONLY valid JSON. No markdown code blocks, no explanatory text.

Required JSON schema:
{
  "original_query": "the user's query",
  "is_ambiguous": true/false,
  "rewritten_query": "clarified version if ambiguous, null otherwise",
  "possible_interpretations": ["list of 2-3 possible meanings if ambiguous"],
  "needed_context_from_memory": ["list of memory fields needed"],
  "clarifying_questions": ["1-3 questions if intent unclear"],
  "final_augmented_context": "combined context summary"
}

🔥 SMART QUERY UNDERSTANDING STRATEGY:

1. **CONTEXT IS KING**: Always check recent conversation first
   - Short query like "Làm nhanh hơn" → Must use context
   - ✅ GOOD: "Optimize Python chatbot scraping performance"
   - ❌ BAD: "Speed up what?" (ignores context)

2. **ACKNOWLEDGE AMBIGUITY + PROVIDE OPTIONS**: 
   - If query is ambiguous, DON'T just ask "what do you mean?"
   - Instead: Identify 2-3 possible interpretations
   - Example: "crawl bóng đá C1" could mean:
     * Match results (scores, dates)
     * Team standings
     * Player statistics
   - Generate rewritten_query with ALL options mentioned
   - Set possible_interpretations to show these options

3. **ONLY HARD STOP if COMPLETELY UNCLEAR**:
   - If query has NO context and is genuinely cryptic → clarifying_questions
   - If query has context OR can be decomposed into options → possible_interpretations

4. **User delegation** ("theo ý bạn", "you choose"):
   - Mark is_ambiguous = false
   - Pick best single interpretation
   - NO clarifying_questions

CRITICAL: Start your response directly with { and end with }. No markdown, no code blocks."""
        
        human_prompt = f"""Recent conversation:
{recent_context}

{summary_context}

New user query: "{user_query}"

Analyze this query for ambiguity and determine what context is needed."""
        
        # Call LLM
        response = self.llm_structured.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        
        # Parse response
        try:
            # Try to extract JSON from response
            content = response.content.strip()
            
            # If response is wrapped in markdown code blocks, extract it
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            query_dict = json.loads(content)
            
            # Sanitize None values to empty lists for list fields
            if query_dict.get("possible_interpretations") is None:
                query_dict["possible_interpretations"] = []
            if query_dict.get("needed_context_from_memory") is None:
                query_dict["needed_context_from_memory"] = []
            if query_dict.get("clarifying_questions") is None:
                query_dict["clarifying_questions"] = []
            
            query_understanding = QueryUnderstanding(**query_dict)
        except json.JSONDecodeError as e:
            print(f"⚠️ Error parsing query understanding: {e}")
            print(f"Raw response: {response.content[:200]}...")
            # Fallback
            query_understanding = QueryUnderstanding(
                original_query=user_query,
                is_ambiguous=False,
                final_augmented_context=recent_context
            )
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            query_understanding = QueryUnderstanding(
                original_query=user_query,
                is_ambiguous=False,
                final_augmented_context=recent_context
            )
        
        print(f"🔍 Query is {'ambiguous' if query_understanding.is_ambiguous else 'clear'}")
        if query_understanding.clarifying_questions:
            print(f"❓ Generated {len(query_understanding.clarifying_questions)} clarifying questions")
        
        # Note: Query analysis will be saved with user message metadata in app.py
        # This keeps all message-related data together in messages table
        
        return {
            **state,
            "query_understanding": query_understanding
        }
    
    # ===== Response Generator Agent =====
    
    def response_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Response Generator: Create final response using augmented context.
        
        Implements SOFT STOP logic:
        - If query is truly ambiguous AND no rewritten query exists → Ask clarifying questions
        - Otherwise → Best effort response with optional clarifying questions at the end
        
        Uses:
        - Query understanding results
        - Session memory
        - Recent conversation
        
        Args:
            state: Current conversation state
        
        Returns:
            Updated state with final response
        """
        query_understanding = state.get("query_understanding")
        
        if not query_understanding:
            return {**state, "final_response": "I need a query to respond to."}
        
        # HARD STOP: Only if query is ambiguous AND we couldn't rewrite it
        # This means it's TRULY unclear and we can't make reasonable assumptions
        if (query_understanding.is_ambiguous and 
            not query_understanding.rewritten_query and 
            query_understanding.clarifying_questions):
            questions = "\n".join([
                f"{i+1}. {q}" for i, q in enumerate(query_understanding.clarifying_questions)
            ])
            return {
                **state,
                "final_response": f"I need some clarification:\n\n{questions}"
            }
        
        print(f"💬 Response Agent: Generating response...")
        
        # Use rewritten query if available (means we made assumptions), otherwise original
        effective_query = (
            query_understanding.rewritten_query 
            if query_understanding.rewritten_query 
            else query_understanding.original_query
        )
        
        # Build context
        context = query_understanding.final_augmented_context
        
        # Generate response - Use regular LLM without json_object mode
        system_prompt = """You are a helpful AI assistant.
Use the provided context to give accurate and relevant responses.
Respond naturally in the same language as the user's query.
If there are multiple interpretations (possible_interpretations):
1. Acknowledge the ambiguity
2. List numbered options
3. Suggest approaches for each
4. Let user choose or provide more info"""
        
        # Check if we need to present options
        has_multiple_interpretations = (
            query_understanding.possible_interpretations and 
            len(query_understanding.possible_interpretations) > 1
        )
        
        if has_multiple_interpretations:
            # Smart approach: Present options instead of guessing
            interpretations_text = "\n".join([
                f"{i+1}. {interp}" 
                for i, interp in enumerate(query_understanding.possible_interpretations)
            ])
            
            human_prompt = f"""Context:
{context}

User query: {effective_query}

This query has multiple possible interpretations:
{interpretations_text}

Provide a helpful response that:
1. Acknowledges these different interpretations
2. Gives brief guidance for each option
3. Asks user which specific aspect they want to focus on"""
        else:
            # Single clear interpretation - answer directly
            human_prompt = f"""Context:
{context}

User query: {effective_query}

Provide a helpful response."""
        
        # Use non-structured LLM for natural conversation
        llm_normal = ChatGoogleGenerativeAI(
            model=self.llm.model,
            temperature=0.7
        )
        response = llm_normal.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        
        final_response = response.content
        
        # NO MORE "soft stop" with trailing questions
        # If we have multiple interpretations, they're already in the response
        # Keep response clean
        
        print(f"✅ Response generated ({len(final_response)} chars)")
        
        return {
            **state,
            "final_response": final_response
        }

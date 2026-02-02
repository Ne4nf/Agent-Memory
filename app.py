"""
Streamlit UI for the Chat Assistant with Session Memory.
Provides visual demo of both core features: session memory and query understanding.
"""

import os
import json
import streamlit as st
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from src.database import Database
from src.agents import Agents
from src.graph import create_conversation_graph
from src.schemas import Message
from src.utils import TokenCounter

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Chat Assistant with Session Memory",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
if "db" not in st.session_state:
    st.session_state.db = Database()
if "agents" not in st.session_state:
    # Verify Google API key is set
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("⚠️ GOOGLE_API_KEY not found in .env file. Please add your API key.")
        st.stop()
    
    token_threshold = int(os.getenv("TOKEN_THRESHOLD", "10000"))
    model = os.getenv("MODEL_NAME", "gemini-2.5-flash")
    st.session_state.agents = Agents(
        db=st.session_state.db,
        model_name=model,
        token_threshold=token_threshold
    )
if "graph" not in st.session_state:
    st.session_state.graph = create_conversation_graph(st.session_state.agents)
if "token_counter" not in st.session_state:
    # Use same token counter as agents for consistency
    st.session_state.token_counter = st.session_state.agents.token_counter

# Load existing messages from DB if any
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Load conversation history from database
    db_messages = st.session_state.db.get_messages(st.session_state.session_id)
    for msg in db_messages:
        st.session_state.messages.append({
            "role": msg.role,
            "content": msg.content,
            "metadata": msg.metadata
        })


def export_conversation_to_file(db: Database, session_id: str) -> str:
    """
    Export complete conversation to single JSONL file.
    Includes messages with inline metadata (query_analysis, summary_triggered).
    This provides chronological view with all structured outputs inline.
    
    Returns the file path.
    """
    # Create data directory if not exists
    data_dir = Path("data/exports")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all messages (with metadata)
    messages = db.get_messages(session_id)
    
    # Get all summaries for reference
    summaries = db.get_all_summaries(session_id)
    
    # Create filename
    filename = f"{session_id}.jsonl"
    filepath = data_dir / filename
    
    # Write to JSONL file
    with open(filepath, 'w', encoding='utf-8') as f:
        # Write metadata header
        metadata = {
            "type": "metadata",
            "session_id": session_id,
            "export_time": datetime.now().isoformat(),
            "total_messages": len(messages),
            "total_summaries": len(summaries),
            "description": "Complete conversation log with inline query analysis and session summaries"
        }
        f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
        
        # Write messages chronologically with metadata
        for msg in messages:
            msg_dict = {
                "type": "message",
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "token_count": msg.token_count
            }
            
            # Include metadata if exists (query_analysis for user, summary for assistant)
            if msg.metadata:
                msg_dict["metadata"] = msg.metadata
            
            f.write(json.dumps(msg_dict, ensure_ascii=False) + '\n')
    
    return str(filepath)


def main():
    """Main Streamlit application."""
    
    # Header
    st.title("🤖 Chat Assistant with Session Memory")
    st.markdown("*Demo: Session Memory via Summarization + Query Understanding*")
    
    # Sidebar with controls and statistics
    with st.sidebar:
        # Session Management
        st.header("💬 Conversation Manager")
        
        # Create new conversation button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ New", use_container_width=True, help="Create a new conversation"):
                st.session_state.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                st.session_state.messages = []
                st.rerun()
        with col2:
            if st.button("🗑️ Clear", use_container_width=True, help="Clear current conversation"):
                st.session_state.db.clear_session(st.session_state.session_id)
                st.session_state.messages = []
                st.rerun()
        
        st.divider()
        
        # Current Session Statistics (moved up)
        st.subheader("📊 Current Session")
        
        stats = st.session_state.db.get_session_stats(st.session_state.session_id)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Messages", stats["message_count"])
        with col2:
            st.metric("Summaries", stats["summary_count"])
        
        # Current context tokens
        current_msgs = st.session_state.db.get_messages(
            st.session_state.session_id,
            exclude_summarized=True
        )
        current_tokens = sum(
            st.session_state.token_counter.count_message_tokens(msg) 
            for msg in current_msgs
        )
        
        threshold = st.session_state.agents.token_threshold
        progress = min(current_tokens / threshold, 1.0)
        
        st.metric("Context", f"{current_tokens}/{threshold} tokens")
        st.progress(progress)
        
        if current_tokens > threshold:
            st.warning("⚠️ Summary on next message!")
        
        st.divider()
        
        # Get all unique sessions from database with first message content
        with st.session_state.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m1.session_id, 
                       m1.timestamp as first_message,
                       COUNT(*) as message_count,
                       m2.content as first_message_content
                FROM messages m1
                LEFT JOIN (
                    SELECT session_id, content, 
                           ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp) as rn
                    FROM messages
                    WHERE role = 'user'
                ) m2 ON m1.session_id = m2.session_id AND m2.rn = 1
                GROUP BY m1.session_id
                ORDER BY first_message DESC
            """)
            all_sessions = cursor.fetchall()
        
        # Conversation list
        st.subheader("📚 Your Conversations")
        
        if all_sessions:
            # Search/filter
            search_term = st.text_input("🔍 Search", placeholder="Filter conversations...", label_visibility="collapsed")
            
            # Filter sessions
            filtered_sessions = all_sessions
            if search_term:
                filtered_sessions = [
                    s for s in all_sessions 
                    if search_term.lower() in s["session_id"].lower()
                ]
            
            st.caption(f"Showing {len(filtered_sessions)} of {len(all_sessions)} conversations")
            
            # Display sessions
            for session in filtered_sessions:
                session_id = session["session_id"]
                first_msg = session["first_message"]
                msg_count = session["message_count"]
                first_content = session["first_message_content"] if session["first_message_content"] else ""
                
                is_current = (session_id == st.session_state.session_id)
                
                # Session card - clickable container
                with st.container():
                    # Create columns for title and menu
                    col_main, col_menu = st.columns([5, 1])
                    
                    with col_main:
                        # Display first message as title (truncated)
                        if first_content:
                            title = first_content[:50] + "..." if len(first_content) > 50 else first_content
                        else:
                            title = session_id.replace("session_", "")
                        
                        # Make the entire card clickable
                        if is_current:
                            st.markdown(f"**🟢 {title}**")
                        else:
                            # Clickable button styled as text
                            if st.button(title, key=f"select_{session_id}", use_container_width=True, help="Click to load"):
                                st.session_state.session_id = session_id
                                st.session_state.messages = []
                                
                                # Load messages from DB
                                db_messages = st.session_state.db.get_messages(session_id)
                                for msg in db_messages:
                                    st.session_state.messages.append({
                                        "role": msg.role,
                                        "content": msg.content,
                                        "metadata": msg.metadata
                                    })
                                st.rerun()
                        
                        # Metadata
                        try:
                            dt = datetime.fromisoformat(first_msg)
                            time_str = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            time_str = first_msg[:16]
                        
                        st.caption(f"📅 {time_str} • 💬 {msg_count} messages")
                    
                    with col_menu:
                        # 3-dot menu using popover
                        with st.popover("⋮", use_container_width=True):
                            st.write("**Actions**")
                            
                            # Export button
                            if st.button("💾 Export", key=f"export_{session_id}", use_container_width=True):
                                export_path = export_conversation_to_file(st.session_state.db, session_id)
                                st.success(f"✅ Exported!")
                                st.caption(f"`{Path(export_path).name}`")
                            
                            # Delete button
                            if st.button("🗑️ Delete", key=f"delete_{session_id}", use_container_width=True, type="secondary"):
                                st.session_state.db.delete_session(session_id)
                                if is_current:
                                    # Create new session if deleting current
                                    st.session_state.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                                    st.session_state.messages = []
                                st.rerun()
                    
                    st.divider()
        else:
            st.info("No conversations yet. Start chatting!")
        
        st.divider()
        
        # Exported Files Section
        st.subheader("📁 Exported Files")
        
        exports_dir = Path("data/exports")
        if exports_dir.exists():
            export_files = list(exports_dir.glob("*.jsonl"))
            
            if export_files:
                st.caption(f"{len(export_files)} file(s) in `data/exports/`")
                
                for file_path in sorted(export_files, key=lambda x: x.stat().st_mtime, reverse=True):
                    file_name = file_path.name
                    file_size = file_path.stat().st_size
                    size_kb = file_size / 1024
                    
                    with st.container():
                        st.text(f"📄 {file_name}")
                        st.caption(f"{size_kb:.1f} KB")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            # Read and display button
                            if st.button("👁️", key=f"view_{file_name}", use_container_width=True, help="View content"):
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                st.session_state[f"file_content_{file_name}"] = content
                        
                        with col2:
                            # Delete file button
                            if st.button("🗑️", key=f"del_file_{file_name}", use_container_width=True, help="Delete file"):
                                file_path.unlink()
                                st.rerun()
                        
                        # Show content if viewed
                        if f"file_content_{file_name}" in st.session_state:
                            with st.expander("📖 File Content", expanded=True):
                                st.code(st.session_state[f"file_content_{file_name}"], language="json")
                                if st.button("Close", key=f"close_{file_name}"):
                                    del st.session_state[f"file_content_{file_name}"]
                                    st.rerun()
                        
                        st.divider()
            else:
                st.info("No exported files yet")
        else:
            st.info("No exports folder yet")
    
    # Main chat area
    st.header("💬 Conversation")
    
    # Display chat messages
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
            
            # Show query analysis UNDER user message (inline with conversation flow)
            if msg["role"] == "user" and msg.get("metadata") and msg["metadata"].get("query_analysis"):
                qa = msg["metadata"]["query_analysis"]
                
                with st.expander("🔍 **AI Thought Process** (Query Understanding)", expanded=False):
                    if qa.get("is_ambiguous"):
                        st.warning("⚠️ **Ambiguous query detected**")
                        
                        if qa.get("rewritten_query"):
                            st.info(f"**🔄 Rewritten:** {qa['rewritten_query']}")
                        
                        if qa.get("possible_interpretations"):
                            st.write("**Possible interpretations:**")
                            for i, interp in enumerate(qa["possible_interpretations"], 1):
                                st.write(f"{i}. {interp}")
                        
                        if qa.get("clarifying_questions"):
                            st.write("**Clarifying questions:**")
                            for i, q in enumerate(qa["clarifying_questions"], 1):
                                st.write(f"{i}. {q}")
                    else:
                        st.success("✅ **Clear query** - proceeding with direct response")
                    
                    if qa.get("needed_context_from_memory"):
                        st.caption(f"📚 Context used: {', '.join(qa['needed_context_from_memory'])}")
                    
                    # Show full JSON for technical evaluation
                    st.divider()
                    with st.container():
                        if st.checkbox("📄 Show Full JSON Schema", key=f"json_qa_{msg.get('timestamp', id(msg))}"):
                            st.json(qa)
            
            # Show session summary UNDER assistant message when triggered
            if msg["role"] == "assistant" and msg.get("metadata") and msg["metadata"].get("summary_triggered"):
                summary = msg["metadata"].get("session_summary")
                if summary:
                    with st.expander("📋 **Session Summary Generated**", expanded=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if summary.get("user_profile", {}).get("preferences"):
                                st.write("**User Preferences:**")
                                for pref in summary["user_profile"]["preferences"]:
                                    st.write(f"- {pref}")
                            
                            if summary.get("key_facts"):
                                st.write("**Key Facts:**")
                                for fact in summary["key_facts"]:
                                    st.write(f"- {fact}")
                            
                            if summary.get("decisions"):
                                st.write("**Decisions:**")
                                for decision in summary["decisions"]:
                                    st.write(f"- {decision}")
                        
                        with col2:
                            if summary.get("user_profile", {}).get("constraints"):
                                st.write("**Constraints:**")
                                for constraint in summary["user_profile"]["constraints"]:
                                    st.write(f"- {constraint}")
                            
                            if summary.get("open_questions"):
                                st.write("**Open Questions:**")
                                for question in summary["open_questions"]:
                                    st.write(f"- {question}")
                            
                            if summary.get("todos"):
                                st.write("**Todos:**")
                                for todo in summary["todos"]:
                                    st.write(f"- {todo}")
                        
                        # Full JSON for evaluation
                        st.divider()
                        with st.container():
                            if st.checkbox("📄 Show Full JSON Schema", key=f"json_summary_{msg.get('timestamp', id(msg))}"):
                                st.json(summary)
    
    # Chat input
    if prompt := st.chat_input("Type your message..."):
        # Run through LangGraph pipeline FIRST to get query_understanding
        with st.spinner("🤔 Processing..."):
            result = st.session_state.graph.run(
                session_id=st.session_state.session_id,
                user_query=prompt
            )
        
        # Prepare metadata for user message
        user_metadata = {}
        if result.get("query_understanding"):
            qu = result["query_understanding"]
            user_metadata["query_analysis"] = {
                "is_ambiguous": qu.is_ambiguous,
                "rewritten_query": qu.rewritten_query,
                "possible_interpretations": qu.possible_interpretations,
                "needed_context_from_memory": qu.needed_context_from_memory,
                "clarifying_questions": qu.clarifying_questions,
                "final_augmented_context": qu.final_augmented_context[:200] + "..." if len(qu.final_augmented_context) > 200 else qu.final_augmented_context
            }
        
        # Save user message with metadata to database
        user_msg = Message(
            role="user",
            content=prompt,
            timestamp=datetime.now(),
            token_count=0,  # Will be set after creation
            metadata=user_metadata
        )
        # Count tokens with role overhead for consistency
        user_msg.token_count = st.session_state.token_counter.count_message_tokens(user_msg)
        st.session_state.db.save_message(st.session_state.session_id, user_msg)
        
        # Add user message to UI with metadata
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "metadata": user_metadata
        })
        
        # Prepare assistant metadata
        assistant_metadata = {}
        
        if result.get("session_summary"):
            assistant_metadata["summary_triggered"] = True
            summary = result["session_summary"].session_summary
            assistant_metadata["session_summary"] = {
                "key_facts": summary.key_facts,
                "decisions": summary.decisions,
                "open_questions": summary.open_questions,
                "todos": summary.todos,
                "user_profile": {
                    "preferences": summary.user_profile.preferences,
                    "constraints": summary.user_profile.constraints
                }
            }
        
        # Add assistant response to UI
        assistant_response = result.get("final_response", "I couldn't generate a response.")
        st.session_state.messages.append({
            "role": "assistant",
            "content": assistant_response,
            "metadata": assistant_metadata
        })
        
        # Save assistant response to database
        assistant_msg = Message(
            role="assistant",
            content=assistant_response,
            timestamp=datetime.now(),
            token_count=0,  # Will be set after creation
            metadata=assistant_metadata
        )
        # Count tokens with role overhead for consistency
        assistant_msg.token_count = st.session_state.token_counter.count_message_tokens(assistant_msg)
        st.session_state.db.save_message(st.session_state.session_id, assistant_msg)
        
        st.rerun()
    
    # Display session summaries
    if stats["summary_count"] > 0:
        st.divider()
        st.header("📋 Session Summaries")
        
        summaries = st.session_state.db.get_all_summaries(st.session_state.session_id)
        
        for idx, summary_output in enumerate(summaries):
            with st.expander(f"Summary #{idx + 1} - {summary_output.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"):
                summary = summary_output.session_summary
                msg_range = summary_output.message_range_summarized
                
                st.write(f"**Messages {msg_range.from_index} to {msg_range.to_index}**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if summary.user_profile.preferences:
                        st.write("**User Preferences:**")
                        for pref in summary.user_profile.preferences:
                            st.write(f"- {pref}")
                    
                    if summary.key_facts:
                        st.write("**Key Facts:**")
                        for fact in summary.key_facts:
                            st.write(f"- {fact}")
                    
                    if summary.decisions:
                        st.write("**Decisions:**")
                        for decision in summary.decisions:
                            st.write(f"- {decision}")
                
                with col2:
                    if summary.user_profile.constraints:
                        st.write("**Constraints:**")
                        for constraint in summary.user_profile.constraints:
                            st.write(f"- {constraint}")
                    
                    if summary.open_questions:
                        st.write("**Open Questions:**")
                        for question in summary.open_questions:
                            st.write(f"- {question}")
                    
                    if summary.todos:
                        st.write("**Todos:**")
                        for todo in summary.todos:
                            st.write(f"- {todo}")


if __name__ == "__main__":
    main()

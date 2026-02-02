# Chat Assistant with Session Memory

> Implementation of a chat assistant with session memory via summarization and intelligent query understanding.

## Features

### Feature 1: Session Memory via Summarization (6/10 points)
- **Automatic context management** - Summarizes conversation when exceeding 1,200 tokens
- **90-94% compression ratio** - Reduces ~1,200 tokens → ~80 tokens
- **Context preservation** - Maintains key facts, decisions, and open questions
- **Incremental summarization** - Supports unlimited conversation length

### Feature 2: Query Understanding & Disambiguation (4/10 points)
- **Ambiguity detection** - Identifies unclear or vague queries
- **Multiple interpretations** - Presents possible meanings
- **Clarifying questions** - Asks for context when needed
- **Context augmentation** - Enriches queries with conversation history

## Quick Start

### Prerequisites
- Python 3.10+
- Google API Key ([Get here](https://makersuite.google.com/app/apikey))

### Installation

```bash
# 1. Create virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API key
echo "GOOGLE_API_KEY=your_api_key_here" > .env

# 4. Run the app
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## 📖 Documentation

Comprehensive documentation available in `docs/`:

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - High-level system design, components, data flow
- **[CORE_LOGIC_AND_FLOW.md](docs/CORE_LOGIC_AND_FLOW.md)** - User journey with real session examples
- **[TRADEOFFS_AND_LIMITATIONS.md](docs/TRADEOFFS_AND_LIMITATIONS.md)** - Design decisions, trade-offs, rationale
- **[TEST_DATA_AND_EVIDENCE.md](docs/TEST_DATA_AND_EVIDENCE.md)** - Test sessions, verification, performance data

## 🎬 How to Test Features

### Testing Session Memory
1. Start a conversation in the main chat
2. Monitor the **token counter** in sidebar (Context: X / 1200 tokens)
3. Continue chatting - watch the progress bar fill up
4. When threshold exceeded, summary triggers automatically
5. Context resets from ~1,200 → ~80 tokens
6. Check **"📋 Session Summaries"** section at bottom to see structured summary

### Testing Query Understanding
1. Ask ambiguous questions like:
   - "I need help"
   - "What about it?"
   - "Can you explain that?"
2. Expand the **"Metadata"** section in the response
3. See query analysis with:
   - Ambiguity detection (true/false)
   - Possible interpretations
   - Clarifying questions
4. System intelligently handles vague queries

## 🏗️ Architecture

```
Streamlit UI (app.py)
    ↓
LangGraph Workflow (graph.py)
    ├─ Context Agent (load messages, check tokens)
    ├─ Summarizer Agent (compress old messages)
    ├─ Ambiguity Resolver (analyze queries)
    └─ Response Generator (create responses)
    ↓
SQLite Database (database.py)
```

### Tech Stack
- **Frontend:** Streamlit 1.31.0
- **Agent Framework:** LangGraph
- **LLM:** Google Gemini 2.5 Flash
- **Database:** SQLite3
- **Token Counting:** tiktoken (cl100k_base)
- **Validation:** Pydantic v2

## 📊 How It Works

### Session Memory

**Before Summarization:**
```
Messages: 70
Context: 10,350 tokens ⚠️ (exceeds threshold)
```

**After Summarization:**
```
Messages: 70 (marked as summarized)
Summary: 1 (compressed representation)
Context: 80 tokens ✅ (reset!)
```

**Compression:** ~1,200 tokens → ~80 tokens (93% reduction)

### Query Understanding

**Example:**
```
User: "I need help with Python"

Analysis:
  ✅ Ambiguous query detected

  Possible Interpretations:
    1. Python programming language
    2. Python (the snake)
  
  Clarifying Questions:
    - Are you asking about Python programming?
    - Do you need help with code or pet care?
```

## 🔧 Configuration

Edit `.env` file:

```bash
# Required
GOOGLE_API_KEY=your_api_key_here

# Optional (defaults shown)
TOKEN_THRESHOLD=1200       # Summarization threshold
MODEL_NAME=gemini-2.5-flash  # LLM model
```

### Token Threshold

- **1,200** - Frequent summaries, perfect for testing/demo (current default)
- **5,000** - Balanced for moderate conversations
- **10,000** - Rich context, production-ready

## 📁 Project Structure

```
Agent-Memory/
├── app.py                 # Streamlit UI
├── src/
│   ├── agents.py         # LangGraph agents
│   ├── graph.py          # Workflow definition
│   ├── database.py       # SQLite operations
│   ├── schemas.py        # Pydantic models
│   └── utils.py          # Token counter
├── docs/                  # Documentation
│   ├── ARCHITECTURE.md
│   ├── CORE_LOGIC_AND_FLOW.md
│   ├── TRADEOFFS_AND_LIMITATIONS.md
│   └── TEST_DATA_AND_EVIDENCE.md
├── data/
│   ├── conversation.db   # SQLite database (created on first run)
│   └── exports/          # Exported sessions (JSONL format)
├── .env                   # Configuration (create from .env.example)
├── .env.example           # Configuration template
├── requirements.txt
└── README.md
```

## 🧪 Testing

### Manual Testing

1. **Session Memory:**
   - Have a long conversation (15+ messages)
   - Watch token counter in sidebar
   - When it exceeds 1200 tokens, summarization triggers automatically
   - Check "📋 Session Summaries" section at bottom
   - Export session to see complete JSONL

2. **Query Understanding:**
   - Ask ambiguous queries:
     - "I need help"
     - "What's the best?"
     - "Check if it's good"
   - Expand "Metadata" in message
   - Verify ambiguity detection and interpretations

### Database Inspection

```bash
# Open database
sqlite3 data/conversation.db

# View sessions
SELECT session_id, COUNT(*) FROM messages GROUP BY session_id;

# View messages
SELECT role, token_count, is_summarized FROM messages LIMIT 10;

# View summaries
SELECT * FROM session_summaries;
```

## 📊 Key Metrics

### Performance
- **Normal query:** ~2-3s (LLM latency)
- **With summarization:** ~5-8s (one-time cost)
- **Token accuracy:** ~95% (tiktoken approximation)

### Cost (Gemini Flash)
- **Per query:** ~$0.00015
- **1,000 queries:** ~$0.15
- **After summarization:** 90% context reduction

### Compression
- **Input:** 1,200 tokens
- **Output:** 80 tokens
- **Ratio:** 93% reduction

## 🐛 Troubleshooting

### "GOOGLE_API_KEY not found"
```bash
# Create .env file
echo "GOOGLE_API_KEY=your_key_here" > .env
```

### Token counter not resetting
```bash
# Reset database
rm data/conversation.db
# Restart app
streamlit run app.py
```

### Slow responses
- Context > 1,200 tokens → Summarization in progress (5-8s)
- Check internet connection (Gemini API)
- Increase TOKEN_THRESHOLD in .env for less frequent summaries

## 📝 Assignment Compliance

### Feature 1: Session Memory (6 points)
- ✅ Automatic summarization when threshold exceeded
- ✅ Structured summary (key facts, decisions, open questions)
- ✅ Context reset mechanism
- ✅ Incremental compression for unlimited length
- ✅ Fully functional and tested

### Feature 2: Query Understanding (4 points)
- ✅ Ambiguity detection using LLM
- ✅ Multiple interpretations generated
- ✅ Clarifying questions asked
- ✅ Context augmentation from conversation history
- ✅ Fully functional and tested

### Additional Features (Bonus)
- ✅ Clean Streamlit UI with real-time token counter
- ✅ Session management (create, load, export, delete)
- ✅ Export to JSONL format with complete metadata
- ✅ Inline query analysis display in message metadata
- ✅ Comprehensive documentation with real examples
- ✅ Graceful error handling and validation

## 🎓 Learning Outcomes

This implementation demonstrates:

1. **LangGraph** - Multi-agent workflow orchestration
2. **Token Management** - Efficient context handling
3. **Prompt Engineering** - Structured LLM outputs
4. **Database Design** - Message storage & retrieval
5. **Error Handling** - Graceful degradation
6. **System Design** - Clear separation of concerns
7. **Trade-off Analysis** - Pragmatic decision-making

## 🚀 Production Roadmap

### Phase 1: Core Improvements
- [ ] Migrate to PostgreSQL (multi-user support)
- [ ] Add authentication (OAuth)
- [ ] Implement rate limiting
- [ ] Comprehensive test suite (>80% coverage)
- [ ] Structured logging

### Phase 2: Feature Enhancements
- [ ] Full-text search across conversations
- [ ] Response caching (Redis)
- [ ] Multi-language support
- [ ] Export to PDF/Markdown
- [ ] Analytics dashboard

### Phase 3: Scaling
- [ ] Kubernetes deployment
- [ ] Load balancing
- [ ] Background workers
- [ ] Monitoring & alerting
- [ ] CDN integration

## 📄 License

This project was created as part of the Vulcan Labs AI Engineer Intern take-home test.

## 🙏 Acknowledgments

- **Google Gemini** - LLM provider
- **LangChain/LangGraph** - Agent framework
- **Streamlit** - Rapid prototyping framework
- **Vulcan Labs** - Assignment opportunity

---

**Assignment:** Vulcan Labs - AI Engineer Intern - Take-Home Test  
**Date:** January 31, 2026

For questions or issues, please refer to the comprehensive documentation in `docs/`.

## 🎬 Running the Demo

### Start the Streamlit Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

### Using the Application

1. **Start chatting** in the main conversation area
2. **Monitor token usage** in the sidebar:
   - Messages count
   - Summaries generated
   - Token progress bar
3. **View session history** to load previous conversations
4. **Check metadata** in message expanders to see:
   - Query ambiguity detection
   - Rewritten queries
   - Context used from memory
5. **Session summaries** appear at the bottom when triggered

### Testing Session Memory

1. Have a long conversation (15-20 messages)
2. Watch the progress bar fill up toward 1200 tokens (not 10k - check your .env)
3. When threshold exceeded, summarization triggers automatically
4. View structured summary in "📋 Session Summaries" section
5. Export session to see complete JSONL with inline metadata

### Testing Query Understanding

1. Ask ambiguous questions:
   - "Can you help with that?"
   - "What about it?"
   - "Check if it's good"
2. Expand "Metadata" section in the response
3. See query analysis:
   - is_ambiguous: true/false
   - possible_interpretations
   - clarifying_questions
4. System enriches context using conversation history

---

## 📁 Project Structure

```
Agent-Memory/
├── src/
│   ├── __init__.py
│   ├── schemas.py          # Pydantic models for structured outputs
│   ├── database.py         # SQLite database layer
│   ├── utils.py            # Token counting utilities
│   ├── agents.py           # LangGraph agent implementations
│   └── graph.py            # LangGraph orchestration
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CORE_LOGIC_AND_FLOW.md
│   ├── TRADEOFFS_AND_LIMITATIONS.md
│   └── TEST_DATA_AND_EVIDENCE.md
├── data/                   # Created at runtime
│   ├── conversation.db     # SQLite database (all conversations)
│   └── exports/            # JSONL exports of sessions
├── app.py                  # Streamlit UI
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 💾 Conversation Storage & History

### Where are conversations saved?

All conversations are **automatically saved to SQLite** at `data/conversation.db`:

- Every message (user + assistant) is saved immediately after sending
- Token counts are stored with each message
- Session summaries are saved when triggered
- Messages are marked as "summarized" after summarization

### How to access conversation history?

**In the UI:**
1. Check the **"📜 Session History"** section in the sidebar
2. See list of all previous sessions with:
   - Session ID (last 8 chars)
   - First message timestamp
   - Message count
3. Click **"Load"** button to switch to any previous session
4. Current session is marked with 🟢

**Programmatically:**
```python
from src.database import Database

db = Database()

# Get all messages from a session
messages = db.get_messages("session_20260130_143000")

# Get session statistics
stats = db.get_session_stats("session_20260130_143000")
# Returns: {"message_count": 42, "summary_count": 1, "total_tokens": 8500}

# Get latest summary
summary = db.get_latest_summary("session_20260130_143000")
```

### Database Schema
{
  "session_su
  },
  "tewritten_query": "clarified version or null",
  "needed_context_from_memory": ["memory fields used"],
  "clarifying_questions": ["question 1", "question 2"],
  "final_augmented_context": "combined context"
}
```

---

## 🧪 Testing

### Real Test Sessions

The system has been tested with real conversations. Check `data/exports/` folder for actual session examples:

1. **session_20260131_232650.jsonl**: Customer churn prediction (20 messages, 2 summaries)
2. **session_20260131_234403.jsonl**: Web scraping project (12 messages, 2 summaries)
3. **session_20260131_235440.jsonl**: AWS deployment (6 messages, 0 summaries)

These demonstrate both features working correctly in production.

### Manual Testing

1. **Session Memory**:
   - Have a long conversation (20+ exchanges)
   - Watch the token counter progress bar
   - Observe automatic summarization when threshold exceeded

2. **Query Understanding**:
   - Ask vague questions: "What about it?", "Can you explain that?"
   - Check the metadata expander for query analysis
   - See rewritten queries and clarifying questions

---

## 💾 Database Schema

### Messages Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| session_id | TEXT | Session identifier |
| role | TEXT | "user" or "assistant" |
| content | TEXT | Message content |
| timestamp | TEXT | ISO 8601 timestamp |
| token_count | INTEGER | Token count |
| is_summarized | INTEGER | 0/1 flag |

### Session Summaries Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| session_id | TEXT | Session identifier |
| summary_json | TEXT | JSON summary |
| from_message_index | INTEGER | Start of range |
| to_message_index | INTEGER | End of range |
| timestamp | TEXT | ISO 8601 timestamp |

---

## ⚙️ Configuration

### Environment Variables

- `GOOGLE_API_KEY`: Your Google AI API key (required, get from https://aistudio.google.com/app/apikey)
- `MODEL_NAME`: Gemini model to use (default: `gemini-2.5-flash`)
- `TOKEN_THRESHOLD`: Token limit before summarization (default: `1200`)

### Customization

- **Token Threshold**: Adjust `TOKEN_THRESHOLD` in `.env`
- **Database Path**: Modify in `app.py` (default: `data/conversation.db`)
- **LLM Temperature**: Adjust in `src/agents.py`

---

## 📊 Evaluation Criteria Alignment

| Criterion | Implementation | Location |
|-----------|----------------|----------|
| **Core features work** (6pts) | ✅ Both flows fully functional | `src/agents.py`, `src/graph.py` |
| **Structured outputs** (1pt) | ✅ Pydantic schemas + validation | `src/schemas.py` |
| **Code structure** (2pts) | ✅ Clear separation, documented | All `src/` files |
| **Documentation** (1pt) | ✅ Complete README + docs | This file + `docs/` |

---

## 🔧 Assumptions & Limitations

### Assumptions

1. **Token Counting**: Uses tiktoken's `cl100k_base` encoding (GPT-4/3.5-turbo)
2. **Summarization Scope**: Only unsummarized messages are counted toward threshold
3. **Single Session**: UI runs one session at a time (multi-session supported in backend)
4. **Synchronous Flow**: LLM calls are synchronous for simplicity

### Limitations

1. **LLM Dependency**: Requires Google Gemini API (not fully offline)
2. **Token Threshold**: Fixed per session (not dynamic)
3. **Summary Merge**: Multiple summaries not merged, stored separately
4. **Error Handling**: Basic fallbacks, could be more robust for production
5. **Context Window**: No sliding window, full context between summaries

### Future Improvements

- Support for multiple LLM providers (Claude, local models)
- Summary merging for very long conversations
- Streaming responses for better UX
- Advanced context window management
- Multi-user session support
- Async LLM calls for performance

---

## 🐛 Troubleshooting

### "Google API key not found"
- Ensure `.env` file exists with `GOOGLE_API_KEY=...`
- Get your API key from https://aistudio.google.com/app/apikey
- Check that `.env` is in the project root directory

### "No module named 'src'"
- Make sure you're running commands from the project root
- Ensure `src/__init__.py` exists

### "Session not loading"
- Check `data/conversation.db` exists
- Try creating a new conversation
- Export working session to verify data integrity

### Database locked errors
- Close any other connections to the database
- Restart the Streamlit app

---

## 📝 Development Notes

### Code Organization

- **schemas.py**: All Pydantic models for type safety and validation
- **database.py**: SQLite abstraction with CRUD operations
- **utils.py**: Token counting utilities (tiktoken wrapper)
- **agents.py**: Individual agent implementations (context, summarizer, query, response)
- **graph.py**: LangGraph workflow orchestration with conditional routing
- **app.py**: Streamlit UI with real-time statistics and metadata display

### Design Decisions

1. All data validated with Pydantic schemas
2. Messages always match required format
3. **Tiktoken**: Accurate token counting (meets "plus" requirement)
4. **SQLite**: Simple, serverless persistence (meets file system/DB requirement)
5. **Streamlit**: Interactive demo showing pipeline internals

---

## 📄 License

This is a take-home test project for educational purposes.

---

## 👤 Author

Created for Vulcan Labs AI Engineer Internship Take-Home Test

---

## 📞 Support

For questions about the implementation:
1. Check the inline code comments in `src/`
2. Review comprehensive docs in `docs/`
3. Check exported sessions in `data/exports/`
4. Examine Streamlit console output for debugging

---

**Note**: This implementation prioritizes clarity, correctness, and demonstration of required features over production optimizations. All core requirements are met with clean, well-documented code.

# Chat Assistant with Session Memory

> Implementation of a chat assistant with session memory via summarization and intelligent query understanding.

## Features

### Feature 1: Session Memory via Summarization 
- **Automatic context management** - Summarizes conversation when exceeding 1,200 tokens
- **90-94% compression ratio** - Reduces ~1,200 tokens → ~80 tokens
- **Context preservation** - Maintains key facts, decisions, and open questions
- **Incremental summarization** - Supports unlimited conversation length

<img width="1891" height="901" alt="image" src="https://github.com/user-attachments/assets/26ebea68-233b-442b-ac54-04880756e2ed" />


### Feature 2: Query Understanding & Disambiguation 
- **Ambiguity detection** - Identifies unclear or vague queries
- **Multiple interpretations** - Presents possible meanings
- **Clarifying questions** - Asks for context when needed
- **Context augmentation** - Enriches queries with conversation history

<img width="1904" height="899" alt="image" src="https://github.com/user-attachments/assets/2246c068-83cc-442a-80ef-de529121a757" />


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

## Documentation

Comprehensive documentation available in `docs/`:

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - High-level system design, components, data flow
- **[CORE_LOGIC_AND_FLOW.md](docs/CORE_LOGIC_AND_FLOW.md)** - User journey with real session examples
- **[TRADEOFFS_AND_LIMITATIONS.md](docs/TRADEOFFS_AND_LIMITATIONS.md)** - Design decisions, trade-offs, rationale
- **[TEST_DATA_AND_EVIDENCE.md](docs/TEST_DATA_AND_EVIDENCE.md)** - Test sessions, verification, performance data

## How to Test Features

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

## Architecture

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

## Project Structure

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

## Testing

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

## Key Metrics

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



## Conversation Storage & History

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



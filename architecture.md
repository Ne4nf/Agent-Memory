# Logo Design Agent - Architecture & Design

**Version**: 1.0  
**Last Updated**: March 20, 2026  
**Status**: Design Document

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Core Components](#core-components)
3. [User Workflow](#user-workflow)
4. [Reasoning Engine Logic](#reasoning-engine-logic)
5. [Data Flow](#data-flow)
6. [Decision Trees](#decision-trees)
7. [Interaction Patterns](#interaction-patterns)
8. [Error Handling](#error-handling)

---

## System Architecture

### High-Level System Diagram

```mermaid
graph TB
    UserChat["👤 User Chat Interface"]
    AIHubSDK["🤖 AI-Hub-SDK Framework"]
    LogoWorker["📋 Logo Design Worker"]
    IntentDetector["🎯 Intent Detection"]
    BrandInference["🏷️ Brand Context Inference"]
    StyleEngine["🎨 Style Inference Engine"]
    DesignDirector["🧭 Design Direction Selection"]
    ImgGenTool["🖼️ Image Generation Tool<br/>DALL-E 3/Gemini Imagen"]
    ImgAnalyzer["🔍 Image Analysis Tool<br/>Vision API"]
    EditParser["✏️ Edit Command Parser"]
    EvalSystem["✅ Auto-Evaluation System<br/>LLM-as-Judge"]
    
    CloudStorage["☁️ Cloud Storage<br/>PNG Results"]
    Redis["📦 Redis Cache<br/>Session Data"]
    Webhook["🔔 Webhook Notifier<br/>Result Delivery"]
    PubSub["📨 Google Pub/Sub<br/>Async Queue"]
    
    UserChat -->|User Message| AIHubSDK
    AIHubSDK -->|Orchestrate| LogoWorker
    
    LogoWorker -->|Detect Intent| IntentDetector
    IntentDetector -->|Brand Details| BrandInference
    BrandInference -->|Brand Context| StyleEngine
    StyleEngine -->|Design Params| DesignDirector
    
    DesignDirector -->|Stream Reasoning| UserChat
    DesignDirector -->|Generate Logos| ImgGenTool
    ImgGenTool -->|Image Bytes| CloudStorage
    
    LogoWorker -->|Analyze References| ImgAnalyzer
    ImgAnalyzer -->|Style Elements| StyleEngine
    
    LogoWorker -->|Parse Edits| EditParser
    EditParser -->|Regenerate| ImgGenTool
    
    ImgGenTool -->|Queue Job| PubSub
    PubSub -->|Long-Running| LogoWorker
    LogoWorker -->|Store Results| Redis
    Redis -->|Notify| Webhook
    Webhook -->|Deliver Results| UserChat
    
    ImgGenTool -->|Evaluate Quality| EvalSystem
    EvalSystem -->|Metrics| Redis
    
    style UserChat fill:#e1f5ff
    style AIHubSDK fill:#f3e5f5
    style LogoWorker fill:#fff3e0
    style CloudStorage fill:#e8f5e9
    style Redis fill:#e0f2f1
    style Webhook fill:#fce4ec
    style PubSub fill:#f0f4c3
```

### Layered Architecture

```mermaid
graph LR
    A["🎯 User Intent Layer<br/>Intent Detection"] -->|Brand Context| B["🏷️ Brand Context Layer<br/>Inference & Mapping"]
    B -->|Design Parameters| C["🎨 Design Layer<br/>Style & Direction"]
    C -->|Generation Config| D["🛠️ Tool Layer<br/>MCP Integration"]
    D -->|PNG Output| E["📊 Evaluation Layer<br/>Quality Assessment"]
    E -->|Feedback| F["💾 Persistence Layer<br/>Redis/Cloud Storage"]
    
    G["⚡ Execution Layer<br/>Async Queue<Pub/Sub>"]
    C -.->|Async Jobs| G
    G -.->|Results| F
    
    style A fill:#ffebee
    style B fill:#fce4ec
    style C fill:#f3e5f5
    style D fill:#ede7f6
    style E fill:#e8eaf6
    style F fill:#e3f2fd
    style G fill:#f1f8e9
```

---

## Core Components

### 1. Intent Detection Module

**Purpose**: Identify logo design requests and extract key intent signals

**Inputs**: User message text  
**Outputs**: Intent confidence score, detected intent type, extracted keywords

```mermaid
graph TD
    UserMsg["User Message"]
    Tokenize["Tokenize & Normalize"]
    PatternMatch["Pattern Matching<br/>logo, design, brand"]
    LLMClassify["LLM Classification<br/>Intent + Confidence"]
    ExtractKW["Extract Keywords<br/>industry, style, colors"]
    Output["Intent Signal<br/>type, confidence, keywords"]
    
    UserMsg --> Tokenize
    Tokenize --> PatternMatch
    PatternMatch -->|High Confidence| Output
    PatternMatch -->|Ambiguous| LLMClassify
    LLMClassify --> ExtractKW
    ExtractKW --> Output
    
    style UserMsg fill:#fff9c4
    style Output fill:#c8e6c9
```

### 2. Brand Context Inference Engine

**Purpose**: Extract and structure brand information from user input

**Key Logic**:
- Extract brand name (required for context, optional for symbol-only logos)
- Detect industry/category
- Identify values, tone, target audience
- Build brand profile for inference

**Data Structure**:
```
BrandContext {
  name: str,              # Brand name (nullable for symbol-only)
  industry: str,          # tech, coffee, beauty, etc.
  values: List[str],      # core values
  tone: str,              # professional, playful, luxury, etc.
  audience: str,          # target demographic
  style_hints: List[str]  # user-provided style preferences
}
```

```mermaid
graph TD
    UserInput["User Input Text"]
    
    ExtractName["Extract Brand Name"]
    ExtractIndustry["Detect Industry Category"]
    ExtractValues["Extract Values/Tone"]
    ExtractAudience["Infer Target Audience"]
    
    CheckName{Brand Name<br/>Provided?}
    Placeholder["Use Placeholder Name<br/>Generic Symbol"]
    MapIndustry["Map Industry to<br/>Design Patterns"]
    
    ApplyDefault["Apply Industry Defaults<br/>Modern/Minimal/Luxury"]
    BuildContext["Build Brand Context<br/>Object"]
    
    UserInput --> ExtractName
    UserInput --> ExtractIndustry
    UserInput --> ExtractValues
    UserInput --> ExtractAudience
    
    ExtractName --> CheckName
    CheckName -->|No| Placeholder
    CheckName -->|Yes| MapIndustry
    Placeholder --> MapIndustry
    
    ExtractIndustry --> ApplyDefault
    ExtractValues --> ApplyDefault
    ExtractAudience --> ApplyDefault
    
    ApplyDefault --> BuildContext
    MapIndustry --> BuildContext
    
    style UserInput fill:#fff9c4
    style BuildContext fill:#c8e6c9
    style Placeholder fill:#ffccbc
```

### 3. Style Inference Engine

**Purpose**: Map brand context to design principles and create design directions

**Industry Mapping Reference**:
```
tech/startup       → Modern, Minimal, Geometric
coffee/food        → Warm, Vintage, Handcrafted
beauty/luxury      → Elegant, Minimalist, Premium
healthcare/fitness → Clean, Trustworthy, Dynamic
education          → Professional, Innovative, Accessible
```

```mermaid
graph TD
    BrandCtx["Brand Context"]
    Ref["Reference Image<br/>Optional"]
    
    IndustryMap["Industry Style Mapping<br/>tech→modern, etc."]
    ExtractRef["Extract Style Elements<br/>Colors, Shapes, Typography"]
    MergeStyles["Merge Industry Style<br/>+ Reference Elements"]
    ConflictResolve["Resolve Conflicts<br/>User Request > Reference"]
    
    Direction1["Design Direction 1<br/>Concept A + Rationale"]
    Direction2["Design Direction 2<br/>Concept B + Rationale"]
    Direction3["Design Direction 3<br/>Concept C + Rationale"]
    Direction4["Design Direction 4<br/>Concept D + Rationale"]
    
    BrandCtx --> IndustryMap
    Ref --> ExtractRef
    IndustryMap --> MergeStyles
    ExtractRef --> MergeStyles
    MergeStyles --> ConflictResolve
    
    ConflictResolve --> Direction1
    ConflictResolve --> Direction2
    ConflictResolve --> Direction3
    ConflictResolve --> Direction4
    
    style BrandCtx fill:#e3f2fd
    style ConflictResolve fill:#fff9c4
    style Direction1 fill:#c8e6c9
    style Direction2 fill:#c8e6c9
    style Direction3 fill:#c8e6c9
    style Direction4 fill:#c8e6c9
```

### 4. Design Direction Selection Logic

**Purpose**: Present direction options OR skip if request is specific

**Decision Tree**:
- **Specific Request** (e.g., "red circular logo, serif") → Skip selection, proceed to generation
- **Ambiguous Request** (e.g., "modern tech logo") → Present 3-4 directions, wait for selection
- **No Direction Selected** → Default to first option, document assumption

```mermaid
graph TD
    Request["User Request"]
    
    CheckSpecific{Request Contains<br/>Specific Design<br/>Details?<br/>color, shape, style}
    
    Specific["SPECIFIC PATH:<br/>Skip Direction Selection"]
    Ambiguous["AMBIGUOUS PATH:<br/>Present Directions"]
    
    GenDirections["Generate 3-4<br/>Design Direction Options"]
    Present["Present to User<br/>with Names & Descriptions"]
    UserSelect{User Selects<br/>Direction?}
    Skip["User Skips<br/>Selection"}
    
    SelectDefault["Default to Direction #1"]
    DocAssume["Document Assumption<br/>in Design Guidelines"]
    
    SelectedDir["Selected Design Direction"]
    GenLogos["Proceed to Logo<br/>Generation"]
    
    Request --> CheckSpecific
    CheckSpecific -->|Yes, specific| Specific
    CheckSpecific -->|No, ambiguous| Ambiguous
    
    Specific --> SelectedDir
    
    Ambiguous --> GenDirections
    GenDirections --> Present
    Present --> UserSelect
    
    UserSelect -->|Selects| SelectedDir
    UserSelect -->|Skips| Skip
    Skip --> SelectDefault
    SelectDefault --> DocAssume
    DocAssume --> SelectedDir
    
    SelectedDir --> GenLogos
    
    style Specific fill:#c8e6c9
    style Ambiguous fill:#ffccbc
    style SelectedDir fill:#81c784
    style GenLogos fill:#4caf50
```

---

## User Workflow

### Complete Multi-Turn Conversation Flow

```mermaid
sequenceDiagram
    actor User
    participant Chat as Chat Interface
    participant Worker as Worker Task
    participant Intent as Intent Detector
    participant Brand as Brand Inference
    participant Style as Style Engine
    participant ImgGen as Image Generator
    participant Eval as Auto-Evaluator
    participant Webhook as Webhook
    participant Redis as Redis Cache

    User->>Chat: Message: "Design logo for TechStart"
    Chat->>Worker: onMessage(user_msg)
    activate Worker
    
    Note over Worker: === PHASE 1: INPUT ANALYSIS ===
    Worker->>Intent: detect_intent(msg)
    Intent-->>Worker: {type: logo_design, confidence: 0.95}
    
    Worker->>Brand: extract_brand(msg)
    Brand-->>Worker: {name: TechStart, industry: tech, ...}
    
    Note over Worker: STREAM: "Analyzing brand context..."
    Worker->>Chat: stream("Input Understanding: TechStart, tech...")
    
    Note over Worker: === PHASE 2: STYLE INFERENCE ===
    Worker->>Style: infer_directions(brand_ctx)
    Style-->>Worker: [Direction1, Direction2, Direction3, Direction4]
    
    Worker->>Chat: stream("Inferring styles based on industry...")
    deactivate Worker
    
    Chat->>User: Display: 4 design direction options
    User->>Chat: Select: "Direction 2: Geometric Modern"
    
    Chat->>Worker: onDirectionSelected(Direction2)
    activate Worker
    
    Note over Worker: === PHASE 3: LOGO GENERATION ===
    Worker->>ImgGen: queue_generation(design_params)
    ImgGen-->>Worker: job_id: uuid-123
    
    Worker->>Redis: store_session(job_id, brand_ctx)
    ParallelGuard: Async via Pub/Sub
    
    ImgGen->>ImgGen: generate_logos() [long-running]
    ImgGen->>Redis: store_results(job_id, png_urls)
    
    Worker->>Eval: evaluate_quality(png_urls, brand_ctx)
    Eval-->>Worker: {alignment: 0.92, quality: 0.88}
    Redis->>Redis: store_eval_metrics(job_id)
    
    ImgGen->>Webhook: notify_completion(job_id)
    Webhook-->>Chat: result_ready(job_id)
    deactivate Worker
    
    Chat->>Redis: fetch_results(job_id)
    Chat->>User: Display: 3-4 PNG logos + explanations
    User->>Chat: Edit: "Change icon color to blue"
    
    Chat->>Worker: onEditCommand(edit)
    activate Worker
    
    Note over Worker: === PHASE 4: EDIT & REGENERATION ===
    Worker->>ImgGen: parse_edit_intent(edit_text)
    ImgGen-->>Worker: {target: icon, color: blue}
    
    Worker->>ImgGen: regenerate_with_edit(logo_id, edit_params)
    ImgGen->>ImgGen: regenerate() [async]
    ImgGen->>Webhook: notify_completion(job_id)
    deactivate Worker
    
    Webhook-->>Chat: updated_result()
    Chat->>User: Display: Updated logo + edit summary
    User->>Chat: "Save this version"
    Note over Chat: MVP: Single-session, no persistence
```

### Phase-by-Phase Detail: Generation Flow

```mermaid
graph LR
    P1["📥 PHASE 1<br/>Input Analysis<br/>- Intent detection<br/>- Brand extraction<br/>- Reference analysis"]
    
    P2["🧭 PHASE 2<br/>Design Direction<br/>- Style inference<br/>- Direction generation<br/>- User selection"]
    
    P3["🖼️ PHASE 3<br/>Logo Generation<br/>- Queue jobs<br/>- Async gen<br/>- Auto-evaluation"]
    
    P4["✏️ PHASE 4<br/>Iteration & Edit<br/>- Parse edits<br/>- Regenerate<br/>- Update results"]
    
    P1 -->|Stream Reasoning| P2
    P2 -->|Direction Selected| P3
    P3 -->|Logos Complete| Chat["💬 User Chat"]
    Chat -->|Edit Command| P4
    P4 -->|Updated Logo| Chat
    
    style P1 fill:#fff9c4
    style P2 fill:#ffccbc
    style P3 fill:#c8e6c9
    style P4 fill:#e1bee7
    style Chat fill:#e3f2fd
```

---

## Reasoning Engine Logic

### Visible Reasoning Display (FR-005a)

**Timing**: Real-time streaming BEFORE logo generation  
**Channels**: Chat interface with structured blocks (not continuous text)

```mermaid
graph TD
    subgraph Stream["📡 Streaming Real-Time Reasoning"]
        Input["1️⃣ Input Understanding<br/>TechStart, AI/ML, modern"]
        Analysis["2️⃣ Image Reference Analysis<br/>[if provided]"]
        Inference["3️⃣ Style Inference<br/>Tech → Geometric Modern"]
        Exploration["4️⃣ Reference Exploration<br/>Colors: blue/cyan, sans-serif"]
    end
    
    subgraph Display["💬 Chat Display<br/>Bulleted blocks, not prose"]
        Block1["✓ Understanding<br/>• Brand: TechStart<br/>• Industry: AI/ML<br/>• Style: Modern"]
        Block2["✓ Style Inference<br/>• Mapping: Tech→Geometric<br/>• Aesthetic: Minimal<br/>• Palette: Blue tones"]
        Block3["→ Generating logos..."]
    end
    
    Stream -->|formatted as blocks| Display
    
    style Stream fill:#fff9c4
    style Display fill:#c8e6c9
```

### Edit Intent Recognition Logic

**Purpose**: Parse natural language edits and map to logo modifications

```mermaid
graph TD
    EditText["Edit Command<br/>e.g., 'change icon to blue'"]
    
    TokenNLP["NLP Token Analysis<br/>Identify action, target, modifier"]
    Templates["Match to Edit Templates<br/>Color, Shape, Style, Layout"]
    Target["Identify Logo Target<br/>Icon, Text, Background, Shape"]
    Params["Extract Parameters<br/>blue = #0000FF"]
    Validate["Validate Edit<br/>Is it feasible?"]
    
    FeasibleYes["✓ Feasible"]
    FeasibleNo["✗ Not feasible<br/>Explain & suggest alternatives"]
    
    RegenerateParams["Build Regen Parameters<br/>preserve other elements"]
    Queue["Queue Regeneration"]
    
    EditText --> TokenNLP
    TokenNLP --> Templates
    Templates --> Target
    Target --> Params
    Params --> Validate
    
    Validate -->|Yes| FeasibleYes
    Validate -->|No| FeasibleNo
    
    FeasibleYes --> RegenerateParams
    FeasibleNo --> EditText
    RegenerateParams --> Queue
    
    style FeasibleYes fill:#c8e6c9
    style FeasibleNo fill:#ffccbc
    style Queue fill:#81c784
```

### Auto-Evaluation System (LLM-as-Judge)

**Purpose**: Assess logo quality and brand alignment  
**Scope**: Internal quality monitoring (not user-facing in MVP)

```mermaid
graph TD
    Logo["Generated Logo<br/>PNG image"]
    BrandCtx["Brand Context<br/>TechStart, tech, modern"]
    Guidelines["Design Guidelines<br/>Inferred parameters"]
    
    BranchAlign["🎯 Brand Alignment<br/>Does logo reflect brand?<br/>Score: 0-1"]
    DesignQual["✨ Design Quality<br/>Clarity, balance, professional<br/>Score: 0-1"]
    EditSuccess["✏️ Edit Success<br/>Did modifications preserve concept?<br/>Score: 0-1"]
    ExplainQual["📝 Explanation Quality<br/>Are guidelines clear?<br/>Score: 0-1"]
    
    LLMJudge["🤖 LLM Evaluator<br/>gpt-4-vision"]
    
    AggScore["Aggregate Score<br/>Avg of all metrics"]
    Result["Quality Metrics Stored<br/>Redis metadata for monitoring"]
    
    Logo --> LLMJudge
    BrandCtx --> LLMJudge
    Guidelines --> LLMJudge
    
    LLMJudge --> BranchAlign
    LLMJudge --> DesignQual
    LLMJudge --> EditSuccess
    LLMJudge --> ExplainQual
    
    BranchAlign --> AggScore
    DesignQual --> AggScore
    EditSuccess --> AggScore
    ExplainQual --> AggScore
    
    AggScore --> Result
    
    style LLMJudge fill:#f3e5f5
    style Result fill:#c8e6c9
```

---

## Data Flow

### Complete Request/Response Data Journey

```mermaid
graph TD
    UserMsg["🔵 User Message<br/>{msg, session_id}"]
    
    Intent["🟢 Intent Output<br/>{type, confidence, keywords}"]
    BrandData["🟢 Brand Context<br/>{name, industry, values, tone}"]
    StyleDirs["🟢 Style Directions<br/>[{name, style, palette, desc}]"]
    DesignGuidelines["🟢 Design Guidelines<br/>{ai_prompt, visual_desc,<br/>typography, techniques}"]
    
    GenJob["🟡 Generation Job<br/>{logo_id, job_id, status,<br/>design_params}"]
    PNGOutput["🟡 PNG Results<br/>{urls[], colors[], timestamp}"]
    EvalMetrics["🟡 Eval Metrics<br/>{alignment, quality,<br/>clarity_score}"]
    
    EditCmd["🔵 Edit Command<br/>{target, intent, params}"]
    UpdatedLogo["🟡 Updated PNG<br/>{url, edit_summary}"]
    
    Redis["💾 Redis State<br/>session_data<br/>results<br/>eval_metrics"]
    CloudStore["☁️ Cloud Storage<br/>profile: {color_mode=png18}<br/>logo images"]
    Webhook["🔔 Webhook<br/>notification<br/>result_ready"]
    
    UserMsg --> Intent
    UserMsg --> BrandData
    BrandData --> StyleDirs
    StyleDirs --> DesignGuidelines
    
    DesignGuidelines --> GenJob
    GenJob --> PNGOutput
    PNGOutput --> EvalMetrics
    
    PNGOutput --> CloudStore
    GenJob --> Redis
    EvalMetrics --> Redis
    Redis --> Webhook
    Webhook -.->|notify| UserMsg
    
    EditCmd --> UpdatedLogo
    UpdatedLogo --> CloudStore
    UpdatedLogo --> Redis
    
    style UserMsg fill:#bbdefb
    style Intent fill:#c8e6c9
    style GenJob fill:#fff9c4
    style PNGOutput fill:#fff9c4
    style EvalMetrics fill:#c8e6c9
    style Redis fill:#e0f2f1
    style CloudStore fill:#f0f4c3
    style Webhook fill:#fce4ec
    style EditCmd fill:#bbdefb
    style UpdatedLogo fill:#fff9c4
```

---

## Decision Trees

### 1. Request Analysis Decision Tree

```mermaid
graph TD
    Req["User Request Received"]
    
    Q1{Intent is<br/>logo design?}
    No1["Not a logo task<br/>Decline"]
    Yes1["Proceed"]
    
    Q2{Brand Name<br/>Provided?}
    NameNo["No brand name<br/>Use placeholder or<br/>symbol-only approach"]
    NameYes["Extract name"]
    
    Q3{Request is<br/>Specific?<br/>color, shape, style}
    Specific["Generated Direction<br/>Skip selection"]
    Ambiguous["Generate Multiple<br/>Directions"]
    
    Q4{Reference<br/>Image?}
    NoRef["Use industry defaults"]
    HasRef["Analyze image<br/>Extract style"]
    
    Req --> Q1
    Q1 -->|No| No1
    Q1 -->|Yes| Yes1
    
    Yes1 --> Q2
    Q2 -->|No| NameNo
    Q2 -->|Yes| NameYes
    
    NameNo --> Q3
    NameYes --> Q3
    
    Q3 -->|Yes| Specific
    Q3 -->|No| Ambiguous
    
    Specific --> Q4
    Ambiguous --> Q4
    Q4 -->|None| NoRef
    Q4 -->|Provided| HasRef
    
    NoRef -.-> Generation["Proceed to<br/>Logo Generation"]
    HasRef -.-> Generation
    
    style No1 fill:#ffccbc
    style Generation fill:#c8e6c9
```

### 2. Logo Generation Decision Tree

```mermaid
graph TD
    DirSelected["Design Direction Selected"]
    
    Q1{Generation<br/>Parameters<br/>Valid?}
    Invalid["Reject with<br/>schema error"]
    Valid["Queue job<br/>to Pub/Sub"]
    
    Q2{Job Status?}
    Timeout["Timeout >60s<br/>Inform user"]
    Error["API Error<br/>Transparent error msg<br/>Suggest retry params"]
    Success["Success<br/>Store PNG in Cloud"]
    
    Q3{Evaluation<br/>Score OK?<br/>quality > 0.7}
    LowQual["Low quality<br/>Suggest regeneration<br/>with modified params"]
    GoodQual["Good quality<br/>Display to user"]
    
    Suggest["Auto-suggest<br/>Design Variations"]
    
    DirSelected --> Q1
    Q1 -->|No| Invalid
    Q1 -->|Yes| Valid
    
    Valid --> Q2
    Q2 -->|Timeout| Timeout
    Q2 -->|Error| Error
    Q2 -->|Success| Success
    
    Success --> Q3
    Q3 -->|No| LowQual
    Q3 -->|Yes| GoodQual
    
    GoodQual --> Suggest
    
    style Invalid fill:#ffccbc
    style Timeout fill:#ffccbc
    style Error fill:#ffccbc
    style Success fill:#c8e6c9
    style GoodQual fill:#81c784
    style Suggest fill:#4caf50
```

### 3. Edit Interpretation Decision Tree

```mermaid
graph TD
    Edit["Edit Command Received<br/>e.g., 'change color to blue'"]
    
    Q1{Edit Intent<br/>Recognized?}
    Unknown["Unknown intent<br/>Ask for clarification"]
    Recognized["Parse parameters"]
    
    Q2{Target Logo<br/>Identified?}
    MultiLogo["Multiple logos<br/>Ask user to select"]
    SingleLogo["Use current logo"]
    
    Q3{Edit is<br/>Feasible?<br/>color OK, shape OK}
    Unfeasible["Feasible but<br/>requires major rework<br/>Suggest alternatives"]
    Feasible["Generate<br/>edit params"]
    
    Q4{Preserve<br/>other elements?}
    No["Don't preserve<br/>Full regeneration"]
    Yes["Preserve unmodified<br/>Partial regeneration"]
    
    Regen["Queue Regeneration<br/>with edit params"]
    Eval["Auto-eval<br/>new logo"]
    Result["Display updated logo<br/>with edit summary"]
    
    Edit --> Q1
    Q1 -->|No| Unknown
    Q1 -->|Yes| Q2 & Recognized
    
    Q2 -->|Multiple| MultiLogo
    Q2 -->|Single| SingleLogo
    
    SingleLogo --> Q3
    MultiLogo --> Q3
    
    Q3 -->|No| Unfeasible
    Q3 -->|Yes| Feasible
    
    Feasible --> Q4
    Q4 -->|Yes| Yes
    Q4 -->|No| No
    
    Yes --> Regen
    No --> Regen
    
    Regen --> Eval
    Eval --> Result
    
    style Unknown fill:#ffccbc
    style Unfeasible fill:#ffe0b2
    style Result fill:#c8e6c9
```

---

## Interaction Patterns

### Pattern 1: Real-Time Streaming (FR-005a)

**Service**: `AIHubStreamService`  
**Protocol**: Server-sent events (SSE) / WebSocket

```mermaid
sequenceDiagram
    actor User
    participant Chat as Chat
    participant Worker as Worker
    
    User->>Chat: Select design direction
    Chat->>Worker: onDirectionSelected()
    activate Worker
    
    Worker->>Chat: stream("🔄 Analyzing brand...")
    Chat->>User: Display: "Analyzing brand context"
    
    Worker->>Chat: stream("✓ Brand: Modern Tech")
    Chat->>User: Update: Add brand analysis detail
    
    Worker->>Chat: stream("🔄 Inferring style...")
    Chat->>User: Display: "Inferring style"
    
    Worker->>Chat: stream("✓ Style: Geometric modern with blue/cyan")
    Chat->>User: Update: Add style detail
    
    Worker->>Chat: stream("🔄 Generating logos...")
    Chat->>User: Display: Loading indicator
    deactivate Worker
    
    Note over Chat: Image gen happens async via Pub/Sub
    
    Chat->>User: [30s later] Display: 3-4 PNG logos
```

### Pattern 2: Async Generation with Webhook Notification

**Service**: `AIHubAsyncService` + Google Pub/Sub + Webhook

```mermaid
sequenceDiagram
    participant Chat as Chat Client
    participant Worker as Worker
    participant Queue as Pub/Sub Queue
    participant ImgGen as Image Generator
    participant Webhook as Webhook Server
    participant Redis as Redis
    
    Chat->>Worker: Stream reasoning (FR-005a)
    Worker->>Queue: queue_generation_job({design_params, job_id})
    Worker-->>Chat: ✓ Job queued, check back in 30s
    
    Note over Queue,ImgGen: Async Processing
    
    Queue->>ImgGen: dequeue(job_id)
    ImgGen->>ImgGen: generate_logos() [long-running, ~15-30s]
    ImgGen->>Redis: store_results(job_id, {png_urls, metadata})
    
    ImgGen->>Webhook: POST /logo-ready<br/>{job_id, timestamp}
    Webhook-->>ImgGen: ✓ 200 OK
    
    Webhook->>Chat: send_ws_notification(job_id)
    Chat->>Chat: fetch_results(job_id)
    Chat->>Redis: GET job_id
    Redis-->>Chat: {png_urls, colors, eval_metrics}
    
    Chat->>Chat: render_logos()
    Chat->>User: Display logos
```

### Pattern 3: Session Data Persistence (Single-Session Model)

**Duration**: During active chat session only  
**Storage**: Redis with 1-hour TTL

```mermaid
graph TD
    Session["Session Start<br/>session_id = uuid()"]
    Store1["Store: Initial<br/>brand_context"]
    Store2["Store: Selected<br/>design_direction"]
    Store3["Store: Generation<br/>results"]
    Store4["Store: Edit<br/>history"]
    
    Retrieve["Retrieve via<br/>session_id"]
    
    Expire["TTL Expires<br/>~60 minutes"]
    Delete["Auto-delete<br/>from Redis"]
    
    Session --> Store1
    Store1 --> Store2
    Store2 --> Store3
    Store3 --> Store4
    
    Retrieve -->|Anytime during session| Store4
    
    Store4 --> Expire
    Expire --> Delete
    
    style Delete fill:#ffccbc
```

---

## Error Handling

### Error Handling Strategy: Transparent Failure (FR-014)

**Philosophy**: Surface errors immediately to user with actionable suggestions  
**No Silent Retries**: User controls retry decision

```mermaid
graph TD
    Request["Request to Tool/API"]
    
    Q1{Tool Call<br/>Succeeds?}
    Success["✓ Success<br/>Continue"]
    Fail["✗ Failure"]
    
    Q2{Error Type?}
    
    Timeout["Timeout<br/>API slow"]
    Invalid["Invalid Request<br/>Schema error"]
    ServiceDown["Service Down<br/>API unavailable"]
    RateLimit["Rate Limit<br/>Too many requests"]
    Other["Other Error<br/>Unexpected"]
    
    TimeoutMsg["Msg: Logo generation took too long.<br/>Try with simpler geometry shapes.<br/>Or skip details to simplify."]
    InvalidMsg["Msg: Input parameters invalid.<br/>Please check brand context."]
    ServiceMsg["Msg: Image service unavailable.<br/>Try again in 30 seconds."]
    RateLimitMsg["Msg: Too many requests.<br/>Please wait 5 minutes."]
    OtherMsg["Msg: Unexpected error [code].<br/>Contact support with error ID."]
    
    UserRetry["User decides:<br/>Retry or Abandon"]
    
    Request --> Q1
    Q1 -->|Success| Success
    Q1 -->|Fail| Fail
    
    Fail --> Q2
    Q2 -->|Timeout| Timeout
    Q2 -->|Invalid| Invalid
    Q2 -->|Down| ServiceDown
    Q2 -->|RateLimit| RateLimit
    Q2 -->|Other| Other
    
    Timeout --> TimeoutMsg
    Invalid --> InvalidMsg
    ServiceDown --> ServiceMsg
    RateLimit --> RateLimitMsg
    Other --> OtherMsg
    
    TimeoutMsg --> UserRetry
    InvalidMsg --> UserRetry
    ServiceMsg --> UserRetry
    RateLimitMsg --> UserRetry
    OtherMsg --> UserRetry
    
    style Success fill:#c8e6c9
    style Timeout fill:#ffccbc
    style Invalid fill:#ffccbc
    style ServiceDown fill:#ffccbc
    style UserRetry fill:#fff9c4
```

### Error Recovery Flow

```mermaid
graph TD
    Error["Error Occurred<br/>{type, message, context}"]
    
    Log["Log Error<br/>Langfuse trace<br/>with full context"]
    
    Categorize["Categorize Severity<br/>Critical/Warning/Info"]
    
    IsCritical{Critical<br/>Error?}
    
    NotCritical["Non-Critical<br/>Continue with<br/>fallback defaults"]
    
    Critical["Critical Error<br/>Session unusable"]
    
    UserNotif["Notify User<br/>with actionable message"]
    
    Suggest["Suggest Retry<br/>with adjusted params<br/>OR<br/>Alternative approach"]
    
    Error --> Log
    Log --> Categorize
    Categorize --> IsCritical
    
    IsCritical -->|No| NotCritical
    IsCritical -->|Yes| Critical
    
    NotCritical --> UserNotif
    Critical --> UserNotif
    UserNotif --> Suggest
    
    style Log fill:#fff9c4
    style UserNotif fill:#ffccbc
    style Suggest fill:#ffe0b2
```

---

## Performance & Scalability

### Request Latency Targets

```
INPUT ANALYSIS
├─ Intent detection: ~100ms
├─ Brand extraction: ~200ms
└─ Total: ~300ms

REASONING STREAMING (FR-005a)
├─ Style inference: ~500ms
├─ Stream to user: real-time (progressive)
└─ Total: ~500ms visible

DESIGN DIRECTION SELECTION
├─ Generate 4 options: ~1-2s
└─ Present to user: instant

LOGO GENERATION (Async via Pub/Sub)
├─ Queue job: ~50ms
├─ DALL-E/Imagen generation: ~15-30s [async]
├─ Auto-evaluation: ~5s [parallel]
├─ Webhook notification: <2s after completion
└─ Total time from user's perspective: ~2s notification + fetch results

EDIT & REGENERATION
├─ Parse edit command: ~200ms
├─ Regenerate logo: ~15-30s [async]
└─ Notification: <2s after completion
```

### Concurrency Model

```mermaid
graph TD
    Session["Single User Session<br/>session_id"]
    
    Sync["Synchronous Operations<br/>Intent, Brand, Style<br/>User-facing, <5s"]
    Async["Asynchronous Operations<br/>Image generation, Evaluation<br/>Queued via Pub/Sub"]
    
    Stream["Real-Time Streams<br/>Reasoning, Status updates<br/>WebSocket/SSE"]
    
    Session --> Sync
    Sync --> |Reason ready| Stream
    Stream --> Async
    Async --> |Result ready| Webhook
    Webhook --> Chat["Deliver to Chat<br/>Redis + Notification"]
    
    style Sync fill:#c8e6c9
    style Async fill:#fff9c4
    style Stream fill:#e3f2fd
    style Chat fill:#81c784
```

---

## Component Responsibilities

| Component | Responsibility | Owned by |
|-----------|-----------------|----------|
| **Intent Detection** | Classify user intent (logo design vs other) | Worker + LLM |
| **Brand Inference** | Extract and structure brand info from text | Worker + NLP |
| **Style Inference** | Map brand context to design directions | Worker + Inference Engine |
| **Design Direction Selection** | Present alternatives or skip if specific | Worker + UI Logic |
| **Image Generation** | Call DALL-E/Imagen API via MCP tool | Image Gen Tool (MCP) |
| **Image Analysis** | Extract design elements from reference images | Vision API Tool (MCP) |
| **Edit Parser** | Parse natural language edit commands | Worker + NLP |
| **Auto-Evaluation** | Assess logo quality (LLM-as-judge) | Eval System (LLM) |
| **Async Execution** | Queue and execute long-running jobs | Pub/Sub + Message Queue |
| **Webhook Delivery** | Notify client of completion | Webhook Server |
| **Session Storage** | Persist session state during conversation | Redis (1-hour TTL) |
| **Cloud Storage** | Store PNG image files | Cloud Storage (GCS/S3) |

---

## Summary Architecture Principles

1. **Real-time Reasoning First**: Visible reasoning steps (FR-005a) delivered via streaming BEFORE generation
2. **Async Everything Long**: Image generation happens async via Pub/Sub; webhook notifies client
3. **Transparent Failure**: Errors surfaced immediately with actionable suggestions (no silent retry)
4. **Single-Session Simplicity**: No session persistence across visits; Redis TTL sufficient
5. **LLM-as-Judge Quality**: Auto-evaluation monitors logo quality but doesn't block delivery
6. **Conditional Directions**: Only present direction selection if request is ambiguous
7. **MCP Standardization**: All tools use MCP for consistent observability and error handling
8. **Preserve Unmentioned**: Edits preserve unmentioned regions to maintain brand consistency


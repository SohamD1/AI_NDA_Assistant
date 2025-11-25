# LexiDoc - AI Legal Document Assistant

A full-stack chat interface that uses **streaming SSE responses**, **LLM function calling**, and **prompt engineering** to help users generate legal documents through conversation.

## Features

### Core Features (100% Complete)

#### 1. Server-Sent Events (SSE) Streaming (30%)
- **Token-by-token streaming** - Responses stream in real-time like ChatGPT
- **Connection management** - Handles reconnection and error recovery
- **Tool status indicators** - Shows when tools are being called/executed
- **Streams both conversation and document generation**

#### 2. LLM Function/Tool Calling (40%)
Three tools implemented:
- **`extract_information`** - Extracts structured data from documents (entities, facts, key points, metadata)
- **`generate_document`** - Creates legal documents from specifications
- **`apply_edits`** - Modifies existing documents based on requests

Tool flow:
1. Claude detects when to use a tool
2. Backend executes the Python function
3. Result is pushed back to Claude
4. Conversation continues with tool results

#### 3. System Prompts (30%)
Comprehensive system prompt that:
- Defines Claude as "LexiDoc" legal document assistant
- Specifies when to use each tool with examples
- Handles edge cases (missing info, ambiguous requests)
- Includes clarifying question templates
- Maintains conversation context

### Nice-to-Have Features (All Implemented)
- **Conversation memory** - Maintains last 20 messages across requests
- **Document preview panel** - Live preview of generated documents
- **Edit highlighting** - Diff view showing changes between document versions
- **Copy/Download** - Export documents easily
- **Session management** - Clear history, persistent sessions

## Tech Stack

- **Backend**: Python 3.10+ / Flask
- **Frontend**: React (Vite)
- **LLM API**: Anthropic Claude (claude-sonnet-4)
- **Streaming**: Server-Sent Events (SSE)

## Project Structure

```
LexidenAI_TakeHome/
├── app.py              # Flask backend with SSE streaming & tool use
├── tools.py            # Tool definitions and execution functions
├── system_prompt.py    # LexiDoc system prompt
├── requirements.txt    # Python dependencies
├── .env                # API key (create this)
└── frontend/
    ├── src/
    │   ├── App.jsx     # React chat UI with document preview
    │   └── App.css     # Styling
    └── package.json
```

## Setup & Running

### 1. Backend Setup

```bash
# Create virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file with your API key
echo "ANTHROPIC_API_KEY=your_key_here" > .env

# Run backend
python app.py
```

Backend runs on `http://localhost:5000`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stream` | POST | SSE streaming chat with tool support |
| `/chat` | POST | Non-streaming chat (for testing) |
| `/history` | GET | Get conversation history |
| `/history` | DELETE | Clear conversation history |

### Request Format
```json
{
  "message": "Help me create an NDA",
  "session_id": "optional_session_id"
}
```

## Tool Implementations

### extract_information
Extracts from legal text:
- **Entities**: Parties, dates, monetary values, percentages, durations, emails
- **Facts**: Obligations, conditions, prohibitions, definitions
- **Key Points**: Summary sentences, action items, deadlines
- **Metadata**: Document type, word count, sections

### generate_document
Generates document structures for:
- Reports, summaries, articles, emails, memos, proposals
- Customizable sections and tone (formal, informal, technical)
- Max length constraints

### apply_edits
Edit types:
- Grammar fixes (spacing, punctuation, capitalization)
- Simplification (legal jargon to plain language)
- Tone changes (formal/informal)
- Formatting improvements
- Custom edits based on instructions

## Prompt Engineering Decisions

### 1. Role Definition
Claude is defined as "LexiDoc" - a specialized legal document assistant. This grounds the model in a specific persona with clear expertise boundaries.

### 2. Tool Trigger Patterns
Each tool has explicit trigger patterns:
- Extract: "What does this say about...", "Find all mentions of..."
- Generate: "Create a...", "Draft an...", "I need a..."
- Edit: "Make it more formal", "Simplify this", "Change the tone"

### 3. Clarifying Questions
The prompt includes templates for gathering missing information before generating documents:
- Party names and details
- Document purpose
- Key terms and conditions
- Jurisdiction requirements

### 4. Output Formatting
Structured output formats for each operation:
- Extractions: Tables with risk levels
- Documents: Numbered sections with clear headers
- Edits: Before/after comparisons with change lists

### 5. Memory Instructions
Guidelines for maintaining context:
- Track current document and type
- Remember party names once identified
- Reference previous extractions and edits

## Testing the App

1. Start backend: `python app.py`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5173`

### Sample Conversations

**Creating an NDA:**
```
You: Help me create an NDA between my company TechCorp and a freelancer
LexiDoc: [Asks clarifying questions about mutual/one-way, duration, etc.]
You: Mutual NDA, 2 years, for software development work
LexiDoc: [Generates NDA document in preview panel]
```

**Extracting Information:**
```
You: [Paste a contract]
You: What are the payment terms in this agreement?
LexiDoc: [Uses extract_information tool, returns structured data]
```

**Editing a Document:**
```
You: Make the liability clause more favorable to the vendor
LexiDoc: [Uses apply_edits tool, shows diff in preview]
```

## Files Overview

### app.py
- Flask app with CORS
- SSE streaming endpoint with tool detection
- Conversation memory (20 messages max)
- Tool execution loop

### tools.py
- Tool JSON schemas for Claude
- `extract_information()` - Regex-based extraction
- `generate_document()` - Template-based generation
- `apply_edits()` - Text transformation functions
- `execute_tool()` - Router function

### system_prompt.py
- 300+ line comprehensive system prompt
- Tool usage guidelines with examples
- Clarifying question templates
- Output format specifications
- Memory maintenance instructions

### App.jsx
- Split-view layout (chat + document preview)
- SSE stream parsing with tool events
- Document extraction from responses
- Diff view for edit highlighting
- Session management

## Limitations & Future Improvements

1. **In-memory storage** - Production would use Redis/database
2. **Mock tool outputs** - Real implementation would use NLP/AI
3. **No authentication** - Add user auth for production
4. **Single model** - Could support multiple LLM providers

## Video Demo Checklist

For the walkthrough video, demonstrate:
1. [ ] Chat interface with streaming responses
2. [ ] Asking for a document (triggers clarifying questions)
3. [ ] Document generation (appears in preview panel)
4. [ ] Extracting information from pasted text
5. [ ] Editing a document (shows diff view)
6. [ ] Tool status indicators during execution
7. [ ] Conversation memory (reference earlier context)
8. [ ] Clear history functionality

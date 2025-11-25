# LexiDoc - AI NDA Document Assistant

A full-stack chat interface that uses **streaming SSE responses**, **LLM function calling**, and **prompt engineering** to help users generate Non-Disclosure Agreements through conversation.

## Features

### Core Features

#### 1. Server-Sent Events (SSE) Streaming
- **Token-by-token streaming** - Responses stream in real-time
- **Base64 encoding** - Preserves all characters including newlines during streaming
- **Tool status indicators** - Shows when tools are being called/executed
- **Streams both conversation and document generation**

#### 2. LLM Function/Tool Calling
Three tools implemented:
- **`extract_information`** - Saves structured data (party names, dates, purpose) to session memory
- **`generate_document`** - Creates NDA documents in LaTeX format, rendered in preview panel
- **`apply_edits`** - Modifies existing documents based on user requests

Tool flow:
1. Claude detects when to use a tool
2. Backend executes the Python function
3. LaTeX content is base64 encoded and sent to frontend
4. Document renders in the preview panel
5. Diff highlighting shows changes between versions

#### 3. System Prompts
Comprehensive system prompt that:
- Defines Claude as "LexiDoc" NDA assistant
- Enforces bullet-point formatting for questions
- Specifies when to use each tool
- Prevents raw LaTeX in chat (tool-only)
- Excludes jurisdiction/governing law for simplicity

### Additional Features
- **Conversation memory** - Maintains last 20 messages across requests
- **Document preview panel** - Live LaTeX-to-HTML rendering
- **Edit highlighting** - Diff view showing additions/deletions between versions
- **PDF Download** - Export documents via print dialog
- **Copy LaTeX** - Copy raw LaTeX to clipboard
- **Session management** - Clear history functionality

## Tech Stack

- **Backend**: Python 3.10+ / Flask
- **Frontend**: React (Vite)
- **LLM API**: Anthropic Claude (claude-sonnet-4)
- **Streaming**: Server-Sent Events (SSE) with base64 encoding

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
    │   ├── App.css     # Styling (dark theme)
    │   ├── index.css   # Base styles
    │   └── main.jsx    # React entry point
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
| `/extract-structured` | POST | Extract structured data using JSON schema |

### Request Format
```json
{
  "message": "Help me create an NDA",
  "session_id": "optional_session_id"
}
```

### SSE Event Types
- `[TEXT:<base64>]` - Streamed text content (base64 encoded)
- `[LATEX_DOCUMENT:<base64>]` - Full LaTeX document for preview
- `[DIFF_DATA:<base64>]` - Diff information for edit highlighting
- `[TOOL_START:<name>]` - Tool execution starting
- `[TOOL_EXECUTING:<name>]` - Tool currently running
- `[TOOL_RESULT:<name>]` - Tool completed
- `[DONE]` - Stream finished

## Tool Implementations

### extract_information
Saves to session memory:
- Party A name (Disclosing Party)
- Party B name (Receiving Party)
- Effective date
- Purpose of the NDA
- Mutual vs one-way

### generate_document
Generates NDA with:
- Title and effective date
- Party definitions
- Confidential information definition
- Obligations of receiving party
- Term and termination
- Signature blocks (simple text format, no tables)

### apply_edits
Allows modifications like:
- Making NDA mutual/one-way
- Changing party names
- Adjusting confidentiality period
- Adding/removing clauses

## Prompt Engineering Decisions

### 1. Role Definition
Claude is defined as "LexiDoc" - a specialized NDA assistant that refuses to generate other document types.

### 2. Communication Style
Enforced bullet-point formatting:
- Questions grouped under bold headers
- One piece of information per bullet
- Short, scannable responses

### 3. Tool-Only Document Output
LaTeX is NEVER output in chat - only via tools. This keeps chat clean and ensures documents render in the preview panel.

### 4. Simplified NDA
- No jurisdiction/governing law clauses
- No complex tabular signatures
- Focus on core NDA elements

### 5. Diff Highlighting
When edits are made:
- Computes line-by-line diff
- Highlights additions in green
- Shows deletion count
- Toggle to show/hide changes

## Architecture

### Backend (app.py)
- Flask app with CORS
- Anthropic streaming client
- Document version history with diff computation
- Tool execution loop
- Base64 encoding for SSE safety

### Frontend (App.jsx)
- Split-view layout (50/50 chat + preview)
- SSE stream parsing with buffering
- LaTeX-to-HTML parser for preview
- Markdown-like chat formatting
- Dark theme UI

## Testing the App

1. Start backend: `python app.py`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5173`

### Sample Conversation

```
You: I need an NDA

LexiDoc: I'll help you create an NDA. I need a few details:

**Party Information:**
- What is the full legal name of the Disclosing Party?
- What is the full legal name of the Receiving Party?

**Agreement Details:**
- What is the purpose of this NDA?
- Should this be mutual or one-way?
- What is the effective date?

You: TechCorp Inc and John Smith, for a consulting project, mutual, starting today

LexiDoc: [Generates NDA in preview panel]

You: Change the confidentiality period to 3 years

LexiDoc: [Updates document, shows diff highlighting]
```

## Limitations & Future Improvements

1. **In-memory storage** - Production would use Redis/database
2. **No authentication** - Add user auth for production
3. **Single document type** - Could expand to other legal documents
4. **Basic LaTeX parser** - Could use proper LaTeX rendering library

"""Flask backend with Anthropic Claude streaming, tool use, and conversation memory."""

import os
import json
import base64
import difflib
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
import anthropic

from tools import TOOLS, execute_tool
from system_prompt import SYSTEM_PROMPT

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Model configuration
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
MAX_HISTORY_LENGTH = 20  # Keep last 20 messages

# In-memory conversation storage (per session)
# In production, use Redis, database, or session storage
conversations = {}

# Store document history for diff highlighting (per session)
document_history = {}


def get_document_history(session_id: str) -> list:
    """Get document version history for a session."""
    if session_id not in document_history:
        document_history[session_id] = []
    return document_history[session_id]


def add_document_version(session_id: str, latex_content: str) -> dict:
    """
    Add a new document version and compute diff from previous version.

    Returns:
        dict with 'content', 'diff', and 'version' keys
    """
    history = get_document_history(session_id)
    version = len(history) + 1

    diff_data = None
    if history:
        # Compute diff from previous version
        previous = history[-1]["content"]
        diff_data = compute_diff(previous, latex_content)

    version_entry = {
        "version": version,
        "content": latex_content,
        "diff": diff_data
    }
    history.append(version_entry)
    return version_entry


def compute_diff(old_text: str, new_text: str) -> dict:
    """
    Compute line-by-line diff between two LaTeX documents.

    Returns:
        dict with 'additions', 'deletions', and 'changes' lists
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    differ = difflib.unified_diff(old_lines, new_lines, lineterm='')

    additions = []
    deletions = []
    changes = []

    # Parse unified diff output
    old_line_num = 0
    new_line_num = 0

    for line in differ:
        if line.startswith('@@'):
            # Parse hunk header: @@ -start,count +start,count @@
            import re
            match = re.match(r'@@ -(\d+)', line)
            if match:
                old_line_num = int(match.group(1)) - 1
            match = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)', line)
            if match:
                new_line_num = int(match.group(1)) - 1
        elif line.startswith('-') and not line.startswith('---'):
            old_line_num += 1
            deletions.append({
                "line": old_line_num,
                "content": line[1:].rstrip('\n')
            })
        elif line.startswith('+') and not line.startswith('+++'):
            new_line_num += 1
            additions.append({
                "line": new_line_num,
                "content": line[1:].rstrip('\n')
            })
        elif not line.startswith('---') and not line.startswith('+++'):
            old_line_num += 1
            new_line_num += 1

    # Find changed sections (sequential additions/deletions that are modifications)
    # Group nearby additions and deletions as "changes"
    for add in additions:
        for dele in deletions:
            # Use sequence matcher to find similar lines (modifications vs new content)
            ratio = difflib.SequenceMatcher(None, dele["content"], add["content"]).ratio()
            if ratio > 0.5:  # Lines are similar enough to be considered a modification
                changes.append({
                    "old_line": dele["line"],
                    "new_line": add["line"],
                    "old_content": dele["content"],
                    "new_content": add["content"],
                    "similarity": ratio
                })

    return {
        "additions": additions,
        "deletions": deletions,
        "changes": changes,
        "has_changes": len(additions) > 0 or len(deletions) > 0
    }


def clear_document_history(session_id: str):
    """Clear document history for a session."""
    if session_id in document_history:
        del document_history[session_id]


def get_conversation(session_id: str) -> list:
    """Get conversation history for a session."""
    if session_id not in conversations:
        conversations[session_id] = []
    return conversations[session_id]


def add_to_conversation(session_id: str, role: str, content) -> list:
    """
    Add a message to conversation history and trim to MAX_HISTORY_LENGTH.

    Args:
        session_id: Unique session identifier
        role: 'user' or 'assistant'
        content: Message content (string or list of content blocks)

    Returns:
        Updated conversation history
    """
    history = get_conversation(session_id)

    # Add new message
    history.append({"role": role, "content": content})

    # Trim to keep only last MAX_HISTORY_LENGTH messages
    # But ensure we don't cut in the middle of a tool use exchange
    if len(history) > MAX_HISTORY_LENGTH:
        # Find a safe trim point (not in middle of tool use)
        trim_start = len(history) - MAX_HISTORY_LENGTH

        # Make sure we start with a user message for valid conversation
        while trim_start < len(history):
            if history[trim_start]["role"] == "user":
                # Check if it's a tool_result (which needs the preceding assistant message)
                content = history[trim_start]["content"]
                if isinstance(content, list) and content and isinstance(content[0], dict):
                    if content[0].get("type") == "tool_result":
                        trim_start += 1
                        continue
                break
            trim_start += 1

        conversations[session_id] = history[trim_start:]

    return conversations[session_id]


def clear_conversation(session_id: str):
    """Clear conversation history for a session."""
    if session_id in conversations:
        del conversations[session_id]


def serialize_content_for_history(content) -> list:
    """
    Convert Anthropic content blocks to serializable format for history.

    Args:
        content: Content from Anthropic response (list of content blocks)

    Returns:
        Serializable list of content dictionaries
    """
    if isinstance(content, str):
        return content

    serialized = []
    for block in content:
        if hasattr(block, "type"):
            if block.type == "text":
                serialized.append({
                    "type": "text",
                    "text": block.text
                })
            elif block.type == "tool_use":
                serialized.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        elif isinstance(block, dict):
            serialized.append(block)

    return serialized


@app.route("/chat", methods=["POST"])
def chat():
    """Non-streaming chat endpoint with tool support and memory."""
    data = request.get_json() or {}
    message = data.get("message", "")
    session_id = data.get("session_id", "default")

    # Get existing conversation history
    history = get_conversation(session_id)

    # Build messages with history
    messages = history + [{"role": "user", "content": message}]

    # Initial response
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages
    )

    # Track messages added during this turn for history
    turn_messages = [{"role": "user", "content": message}]

    # Handle tool use loop
    while response.stop_reason == "tool_use":
        # Find tool use blocks
        tool_uses = [block for block in response.content if block.type == "tool_use"]

        # Execute each tool and collect results
        tool_results = []
        for tool_use in tool_uses:
            result = execute_tool(tool_use.name, tool_use.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result
            })

        # Add assistant response and tool results to messages
        assistant_content = serialize_content_for_history(response.content)
        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

        # Track for history
        turn_messages.append({"role": "assistant", "content": assistant_content})
        turn_messages.append({"role": "user", "content": tool_results})

        # Continue conversation
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

    # Extract final text response
    text_content = ""
    for block in response.content:
        if hasattr(block, "text"):
            text_content += block.text

    # Add final assistant response to turn messages
    final_content = serialize_content_for_history(response.content)
    turn_messages.append({"role": "assistant", "content": final_content})

    # Save all turn messages to history
    for msg in turn_messages:
        add_to_conversation(session_id, msg["role"], msg["content"])

    return jsonify({
        "response": text_content,
        "message_received": message,
        "session_id": session_id,
        "history_length": len(get_conversation(session_id))
    })


@app.route("/stream", methods=["POST"])
def stream():
    """SSE streaming endpoint with tool use support and memory."""
    data = request.get_json() or {}
    message = data.get("message", "")
    session_id = data.get("session_id", "default")

    def generate():
        # Get existing conversation history
        history = get_conversation(session_id)

        # Build messages from history
        messages = history + [{"role": "user", "content": message}]

        # Track messages for this turn
        turn_messages = [{"role": "user", "content": message}]

        # Loop to handle multiple tool calls
        while True:
            current_tool_use = None
            current_tool_input = ""

            # Stream the response
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            ) as stream_response:

                for event in stream_response:
                    # Handle different event types
                    if event.type == "content_block_start":
                        if event.content_block.type == "text":
                            pass
                        elif event.content_block.type == "tool_use":
                            current_tool_use = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": {}
                            }
                            current_tool_input = ""
                            yield f"data: [TOOL_START:{event.content_block.name}]\n\n"

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            # Base64 encode text to preserve newlines and special chars
                            text = event.delta.text
                            encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
                            yield f"data: [TEXT:{encoded}]\n\n"
                        elif hasattr(event.delta, "partial_json"):
                            current_tool_input += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool_use is not None:
                            try:
                                current_tool_use["input"] = json.loads(current_tool_input) if current_tool_input else {}
                            except json.JSONDecodeError:
                                current_tool_use["input"] = {}
                            current_tool_use = None
                            current_tool_input = ""

                final_message = stream_response.get_final_message()

            # Check if we need to handle tool use
            if final_message.stop_reason == "tool_use":
                tool_use_blocks = [
                    block for block in final_message.content
                    if block.type == "tool_use"
                ]

                tool_results = []
                for tool_block in tool_use_blocks:
                    yield f"data: [TOOL_EXECUTING:{tool_block.name}]\n\n"

                    # Check if this is a document generation tool - send LaTeX to frontend
                    if tool_block.name in ["generate_document", "apply_edits"]:
                        latex_content = tool_block.input.get("latex_content", "")
                        if latex_content:
                            # Add to document history and compute diff
                            version_data = add_document_version(session_id, latex_content)

                            # Send LaTeX content as a special event for the preview panel
                            # Base64 encode to avoid SSE parsing issues with newlines
                            encoded_latex = base64.b64encode(latex_content.encode('utf-8')).decode('utf-8')
                            yield f"data: [LATEX_DOCUMENT:{encoded_latex}]\n\n"

                            # Send diff data if this is an edit (not first document)
                            if version_data.get("diff") and version_data["diff"]["has_changes"]:
                                diff_json = json.dumps(version_data["diff"])
                                encoded_diff = base64.b64encode(diff_json.encode('utf-8')).decode('utf-8')
                                yield f"data: [DIFF_DATA:{encoded_diff}]\n\n"

                    result = execute_tool(tool_block.name, tool_block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": result
                    })
                    yield f"data: [TOOL_RESULT:{tool_block.name}]\n\n"

                # Serialize and add to messages
                assistant_content = serialize_content_for_history(final_message.content)
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

                # Track for history
                turn_messages.append({"role": "assistant", "content": assistant_content})
                turn_messages.append({"role": "user", "content": tool_results})

            else:
                # Final response - save to history
                final_content = serialize_content_for_history(final_message.content)
                turn_messages.append({"role": "assistant", "content": final_content})

                # Save all turn messages to conversation history
                for msg in turn_messages:
                    add_to_conversation(session_id, msg["role"], msg["content"])

                break

        yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


# JSON Schema for structured NDA information extraction (used without function calling)
NDA_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "party_a": {
            "type": "string",
            "description": "Full legal name of the Disclosing Party"
        },
        "party_b": {
            "type": "string",
            "description": "Full legal name of the Receiving Party"
        },
        "effective_date": {
            "type": "string",
            "description": "The effective date of the agreement"
        },
        "purpose": {
            "type": "string",
            "description": "The specific reason for the NDA"
        },
        "is_mutual": {
            "type": "boolean",
            "description": "True if both parties disclose information"
        },
        "confidentiality_period": {
            "type": "string",
            "description": "Duration of confidentiality obligations"
        },
        "additional_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any additional terms or clauses mentioned"
        }
    },
    "required": ["party_a"]
}


@app.route("/extract-structured", methods=["POST"])
def extract_structured():
    """
    Extract structured information from text using JSON schema validation.
    This demonstrates structured outputs WITHOUT using function calling.
    Uses prompt engineering + prefilled assistant response to enforce JSON.
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    custom_schema = data.get("schema", NDA_EXTRACTION_SCHEMA)

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Use prompt engineering + prefilled assistant message to force JSON output
    # This technique works with any Anthropic SDK version
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system="""You are a structured data extraction assistant. You ONLY output valid JSON.
Never include explanations, markdown formatting, or code blocks.
Your entire response must be parseable JSON matching the requested schema.""",
        messages=[
            {
                "role": "user",
                "content": f"""Extract structured information from the following text and return it as JSON matching this schema:

Schema:
{json.dumps(custom_schema, indent=2)}

Text to extract from:
{text}

Respond with ONLY the JSON object. No markdown, no code blocks, no explanation."""
            },
            {
                "role": "assistant",
                "content": "{"  # Prefill to force JSON start
            }
        ]
    )

    # Parse and validate the response
    try:
        # Reconstruct full JSON (we prefilled with "{")
        response_text = "{" + response.content[0].text

        # Clean up any trailing content after the JSON
        # Find the matching closing brace
        brace_count = 0
        json_end = 0
        for i, char in enumerate(response_text):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break

        if json_end > 0:
            response_text = response_text[:json_end]

        extracted_data = json.loads(response_text)

        # Validate against schema (basic validation)
        validated = validate_against_schema(extracted_data, custom_schema)

        return jsonify({
            "success": True,
            "data": extracted_data,
            "validated": validated,
            "raw_response": response_text
        })
    except json.JSONDecodeError as e:
        return jsonify({
            "success": False,
            "error": f"Failed to parse JSON response: {str(e)}",
            "raw_response": "{" + (response.content[0].text if response.content else "")
        }), 500


def validate_against_schema(data: dict, schema: dict) -> dict:
    """
    Basic JSON schema validation.
    Returns validation result with any errors found.
    """
    errors = []
    warnings = []

    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in data or data[field] is None:
            errors.append(f"Missing required field: {field}")

    # Check field types
    properties = schema.get("properties", {})
    for field, value in data.items():
        if field in properties:
            expected_type = properties[field].get("type")
            if expected_type:
                if expected_type == "string" and not isinstance(value, str):
                    warnings.append(f"Field '{field}' should be string, got {type(value).__name__}")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    warnings.append(f"Field '{field}' should be boolean, got {type(value).__name__}")
                elif expected_type == "array" and not isinstance(value, list):
                    warnings.append(f"Field '{field}' should be array, got {type(value).__name__}")
                elif expected_type == "object" and not isinstance(value, dict):
                    warnings.append(f"Field '{field}' should be object, got {type(value).__name__}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


@app.route("/history", methods=["GET"])
def get_history():
    """Get conversation history for a session."""
    session_id = request.args.get("session_id", "default")
    history = get_conversation(session_id)

    return jsonify({
        "session_id": session_id,
        "history": history,
        "message_count": len(history)
    })


@app.route("/history", methods=["DELETE"])
def delete_history():
    """Clear conversation history for a session."""
    session_id = request.args.get("session_id", "default")
    clear_conversation(session_id)
    clear_document_history(session_id)

    return jsonify({
        "session_id": session_id,
        "status": "cleared"
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)

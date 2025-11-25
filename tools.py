"""Claude tool definitions for the chat application."""

# Tool definitions compatible with Claude's tools=[...] parameter

EXTRACT_INFORMATION = {
    "name": "extract_information",
    "description": "Extract structured information from text. Use this to pull out specific data points, entities, facts, or key details from unstructured content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "source_text": {
                "type": "string",
                "description": "The text to extract information from"
            },
            "extraction_type": {
                "type": "string",
                "enum": ["entities", "facts", "key_points", "metadata", "custom"],
                "description": "The type of information to extract"
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific fields or data points to extract (e.g., ['name', 'date', 'location'])"
            },
            "output_format": {
                "type": "string",
                "enum": ["json", "markdown", "plain_text"],
                "default": "json",
                "description": "Format for the extracted information"
            }
        },
        "required": ["source_text", "extraction_type"]
    }
}

GENERATE_DOCUMENT = {
    "name": "generate_document",
    "description": "Generate a structured document based on specifications. Use this to create reports, summaries, articles, or other formatted content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "enum": ["report", "summary", "article", "email", "memo", "proposal", "custom"],
                "description": "The type of document to generate"
            },
            "title": {
                "type": "string",
                "description": "Title or subject of the document"
            },
            "content_requirements": {
                "type": "string",
                "description": "Description of what the document should contain"
            },
            "sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of sections to include (e.g., ['Introduction', 'Analysis', 'Conclusion'])"
            },
            "tone": {
                "type": "string",
                "enum": ["formal", "informal", "technical", "casual", "professional"],
                "default": "professional",
                "description": "Writing tone for the document"
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum length in words (optional)"
            }
        },
        "required": ["document_type", "title", "content_requirements"]
    }
}

APPLY_EDITS = {
    "name": "apply_edits",
    "description": "Apply edits or modifications to existing text. Use this to revise, reformat, correct, or transform content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "original_text": {
                "type": "string",
                "description": "The original text to be edited"
            },
            "edit_type": {
                "type": "string",
                "enum": ["grammar", "style", "tone", "format", "simplify", "expand", "translate", "custom"],
                "description": "The type of edit to apply"
            },
            "instructions": {
                "type": "string",
                "description": "Specific instructions for how to edit the text"
            },
            "preserve_meaning": {
                "type": "boolean",
                "default": True,
                "description": "Whether to preserve the original meaning while editing"
            },
            "target_language": {
                "type": "string",
                "description": "Target language for translation (only used when edit_type is 'translate')"
            }
        },
        "required": ["original_text", "edit_type"]
    }
}

# List of all tools for easy import
TOOLS = [EXTRACT_INFORMATION, GENERATE_DOCUMENT, APPLY_EDITS]


# =============================================================================
# Tool Execution Functions
# =============================================================================

import json


def execute_extract_information(source_text: str, extraction_type: str,
                                 fields: list = None, output_format: str = "json") -> str:
    """
    Execute the extract_information tool.
    In a real implementation, this might use NLP, regex, or another AI call.
    For now, returns a structured mock response.
    """
    result = {
        "extraction_type": extraction_type,
        "source_length": len(source_text),
        "fields_requested": fields or [],
        "extracted_data": {}
    }

    # Mock extraction based on type
    if extraction_type == "entities":
        result["extracted_data"] = {
            "parties": ["Party A (extracted)", "Party B (extracted)"],
            "dates": ["Date found in document"],
            "locations": ["Location found in document"]
        }
    elif extraction_type == "facts":
        result["extracted_data"] = {
            "key_facts": [
                "Fact 1 extracted from document",
                "Fact 2 extracted from document"
            ]
        }
    elif extraction_type == "key_points":
        result["extracted_data"] = {
            "summary_points": [
                "Key point 1 from analysis",
                "Key point 2 from analysis"
            ]
        }
    elif extraction_type == "metadata":
        result["extracted_data"] = {
            "document_type": "Contract/Agreement",
            "word_count": len(source_text.split()),
            "sections_found": ["Introduction", "Terms", "Signatures"]
        }
    else:  # custom
        if fields:
            result["extracted_data"] = {field: f"Extracted value for {field}" for field in fields}
        else:
            result["extracted_data"] = {"note": "Custom extraction performed"}

    if output_format == "json":
        return json.dumps(result, indent=2)
    elif output_format == "markdown":
        md = f"## Extraction Results ({extraction_type})\n\n"
        for key, value in result["extracted_data"].items():
            md += f"**{key}**: {value}\n\n"
        return md
    else:  # plain_text
        return str(result["extracted_data"])


def execute_generate_document(document_type: str, title: str, content_requirements: str,
                               sections: list = None, tone: str = "professional",
                               max_length: int = None) -> str:
    """
    Execute the generate_document tool.
    Returns a structured document template.
    """
    sections = sections or ["Introduction", "Main Content", "Conclusion"]

    doc = f"""# {title}

**Document Type:** {document_type.title()}
**Tone:** {tone.title()}
{'**Max Length:** ' + str(max_length) + ' words' if max_length else ''}

---

"""

    for i, section in enumerate(sections, 1):
        doc += f"""## {i}. {section}

[Content for {section} based on requirements: {content_requirements[:100]}...]

"""

    doc += """---

*Document generated by LexiDoc Assistant*
*Please review and customize before use*
"""

    return doc


def execute_apply_edits(original_text: str, edit_type: str, instructions: str = None,
                        preserve_meaning: bool = True, target_language: str = None) -> str:
    """
    Execute the apply_edits tool.
    Returns the edited text with changes noted.
    """
    result = {
        "edit_type": edit_type,
        "preserve_meaning": preserve_meaning,
        "original_length": len(original_text),
        "edited_text": "",
        "changes_made": []
    }

    # Mock edits based on type
    if edit_type == "grammar":
        result["edited_text"] = original_text  # Would fix grammar
        result["changes_made"] = ["Grammar corrections applied", "Punctuation reviewed"]
    elif edit_type == "simplify":
        result["edited_text"] = original_text  # Would simplify
        result["changes_made"] = ["Complex sentences simplified", "Jargon replaced with plain language"]
    elif edit_type == "translate":
        result["edited_text"] = f"[Translated to {target_language or 'target language'}]: {original_text}"
        result["changes_made"] = [f"Translated to {target_language or 'specified language'}"]
    elif edit_type == "style":
        result["edited_text"] = original_text
        result["changes_made"] = ["Style adjustments made per instructions"]
    elif edit_type == "tone":
        result["edited_text"] = original_text
        result["changes_made"] = ["Tone adjusted as requested"]
    elif edit_type == "format":
        result["edited_text"] = original_text
        result["changes_made"] = ["Formatting improved", "Structure reorganized"]
    elif edit_type == "expand":
        result["edited_text"] = original_text + "\n\n[Additional content would be added here]"
        result["changes_made"] = ["Content expanded with additional details"]
    else:  # custom
        result["edited_text"] = original_text
        result["changes_made"] = [f"Custom edits applied: {instructions or 'as specified'}"]

    return json.dumps(result, indent=2)


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Route tool execution to the appropriate function.
    Returns the tool result as a string.
    """
    if tool_name == "extract_information":
        return execute_extract_information(**tool_input)
    elif tool_name == "generate_document":
        return execute_generate_document(**tool_input)
    elif tool_name == "apply_edits":
        return execute_apply_edits(**tool_input)
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

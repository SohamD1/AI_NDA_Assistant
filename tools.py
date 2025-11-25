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

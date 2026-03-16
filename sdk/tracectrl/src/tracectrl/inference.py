"""Tool category inference from tool name and description."""

TOOL_CATEGORY_RULES = [
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["exec", "run_code", "python", "bash", "shell", "eval", "compile"]), "code_execution"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["send_email", "send_mail", "email", "smtp"]), "email"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["http", "fetch", "request", "curl", "scrape", "browse", "web"]), "external_api"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["write_file", "save_file", "create_file", "delete_file", "rm ", " mv "]), "file_system"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["vector", "embed", "upsert", "add_document", "index"]), "memory_write"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["search", "query", "retrieve", "recall", "lookup"]), "memory_read"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["human", "approval", "confirm", "ask_user", "hitl"]), "human_interaction"),
    (lambda n, d: True, "internal_api"),
]


def infer_tool_category(tool_name: str, tool_description: str = "") -> str:
    """Classify a tool into a risk category based on its name and description."""
    for match_fn, category in TOOL_CATEGORY_RULES:
        if match_fn(tool_name, tool_description):
            return category
    return "internal_api"

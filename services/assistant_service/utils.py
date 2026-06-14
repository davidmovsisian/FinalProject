def format_context(context: str) -> str:
    """Normalize optional context text and provide a default when missing."""
    cleaned = context.strip()
    return cleaned if cleaned else "No similar listings context was provided."

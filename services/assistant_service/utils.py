def format_context(context: str) -> str:
    cleaned = context.strip()
    return cleaned if cleaned else "No similar listings context was provided."

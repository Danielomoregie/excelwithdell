SESSION_KEY = "chat_conversation"
MAX_TURNS = 20


def get_conversation(session_store):
    """Return a validated conversation list from Flask session storage."""
    conversation = session_store.get(SESSION_KEY, [])
    if isinstance(conversation, list):
        return conversation
    return []


def append_message(conversation, role, content):
    """Append a role/content message and cap history length."""
    conversation.append({"role": role, "content": content})
    if len(conversation) > MAX_TURNS:
        return conversation[-MAX_TURNS:]
    return conversation


def save_conversation(session_store, conversation):
    """Persist conversation to Flask session storage."""
    session_store[SESSION_KEY] = conversation
    session_store.modified = True

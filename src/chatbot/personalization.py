def build_system_prompt(user):
    """Build a system prompt scaffold that can be personalized by user profile."""
    base_prompt = (
        "You are a helpful assistant for the FusionTech product dashboard. "
        "Give concise, actionable responses in a professional tone."
    )

    if not user or not isinstance(user, dict):
        return base_prompt

    first_name = str(user.get("first_name", "")).strip()
    department = str(user.get("department", "")).strip()

    # Keep this lightweight for now; richer department-specific behavior can be added later.
    personalization_bits = []
    if first_name:
        personalization_bits.append(f"The current user is {first_name}.")
    if department:
        personalization_bits.append(f"Their department is {department}.")

    if personalization_bits:
        return f"{base_prompt} {' '.join(personalization_bits)}"

    return base_prompt


def build_model_input(conversation, user):
    """Compose OpenAI input payload from system prompt + prior turns."""
    system_prompt = build_system_prompt(user)
    return [{"role": "system", "content": system_prompt}] + conversation

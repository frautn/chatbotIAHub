import logging

import requests

log = logging.getLogger(__name__)

# How many of the learner's most recent chats to inspect when a model is
# pinned: enough to skip past unrelated activities without fetching everything.
MAX_CANDIDATES_CHECKED = 20
REQUEST_TIMEOUT = 5


def find_resumable_chat(base_url, email, name, model, exclude_chat_ids):
    """Best-effort lookup of the Open WebUI chat the learner should resume.

    Signs in as the learner via Open WebUI's trusted-header auth (the same
    mechanism nginx uses), then picks their most recent chat that isn't
    already claimed by another resource link. When *model* is set, only a
    chat whose `models` list contains it is eligible, so distinct
    model-pinned activities never share a conversation.

    Returns a chat id, or None if unavailable/not found. Never raises.
    """
    if not base_url:
        return None

    try:
        signin = requests.post(
            f"{base_url}/api/v1/auths/signin",
            json={"email": email, "password": "lti-gateway"},
            headers={"X-Forwarded-Email": email, "X-Forwarded-Name": name},
            timeout=REQUEST_TIMEOUT,
        )
        signin.raise_for_status()
        token = signin.json()["token"]
    except (requests.RequestException, KeyError, ValueError):
        log.warning("Could not sign in to Open WebUI to resolve a resumable chat", exc_info=True)
        return None

    headers = {"Authorization": f"Bearer {token}"}
    try:
        listing = requests.get(f"{base_url}/api/v1/chats/", headers=headers, timeout=REQUEST_TIMEOUT)
        listing.raise_for_status()
        chats = listing.json()
    except (requests.RequestException, ValueError):
        log.warning("Could not list Open WebUI chats to resolve a resumable chat", exc_info=True)
        return None

    exclude = set(exclude_chat_ids)
    candidates = [chat["id"] for chat in chats if chat.get("id") not in exclude]

    if not model:
        return candidates[0] if candidates else None

    for chat_id in candidates[:MAX_CANDIDATES_CHECKED]:
        try:
            detail = requests.get(
                f"{base_url}/api/v1/chats/{chat_id}", headers=headers, timeout=REQUEST_TIMEOUT
            )
            detail.raise_for_status()
            chat_models = (detail.json().get("chat") or {}).get("models") or []
        except (requests.RequestException, ValueError):
            continue
        if model in chat_models:
            return chat_id
    return None

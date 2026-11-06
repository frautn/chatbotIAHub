import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lti_gateway.webui_client import find_resumable_chat  # noqa: E402

BASE_URL = "http://openwebui.internal"


def _signin_response(token="tok-1"):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"token": token}
    return response


def _listing_response(chat_ids):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = [{"id": chat_id} for chat_id in chat_ids]
    return response


def _detail_response(models):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"chat": {"models": models}}
    return response


def test_resumes_chat_whose_sole_model_matches():
    with patch("lti_gateway.webui_client.requests.post", return_value=_signin_response()):
        with patch("lti_gateway.webui_client.requests.get") as mocked_get:
            mocked_get.side_effect = [
                _listing_response(["chat-1"]),
                _detail_response(["model-a"]),
            ]
            chat_id = find_resumable_chat(BASE_URL, "a@b", "Ana", "model-a", [])
    assert chat_id == "chat-1"


def test_does_not_resume_chat_with_additional_models():
    """A chat whose `models` list has picked up more than one model over its
    lifetime (e.g. the learner or a teacher switched models mid-conversation)
    must not be mistaken for a chat dedicated to the pinned model, even
    though the pinned model is technically present in that list."""
    with patch("lti_gateway.webui_client.requests.post", return_value=_signin_response()):
        with patch("lti_gateway.webui_client.requests.get") as mocked_get:
            mocked_get.side_effect = [
                _listing_response(["chat-mixed", "chat-pure"]),
                _detail_response(["model-a", "model-b"]),
                _detail_response(["model-a"]),
            ]
            chat_id = find_resumable_chat(BASE_URL, "a@b", "Ana", "model-a", [])
    assert chat_id == "chat-pure"


def test_no_pure_match_falls_back_to_none():
    with patch("lti_gateway.webui_client.requests.post", return_value=_signin_response()):
        with patch("lti_gateway.webui_client.requests.get") as mocked_get:
            mocked_get.side_effect = [
                _listing_response(["chat-mixed"]),
                _detail_response(["model-a", "model-b"]),
            ]
            chat_id = find_resumable_chat(BASE_URL, "a@b", "Ana", "model-a", [])
    assert chat_id is None


def test_without_a_pinned_model_most_recent_chat_is_reused():
    with patch("lti_gateway.webui_client.requests.post", return_value=_signin_response()):
        with patch("lti_gateway.webui_client.requests.get", return_value=_listing_response(["chat-1", "chat-2"])):
            chat_id = find_resumable_chat(BASE_URL, "a@b", "Ana", "", [])
    assert chat_id == "chat-1"


def test_excluded_chat_ids_are_skipped():
    with patch("lti_gateway.webui_client.requests.post", return_value=_signin_response()):
        with patch("lti_gateway.webui_client.requests.get") as mocked_get:
            mocked_get.side_effect = [
                _listing_response(["chat-claimed", "chat-free"]),
                _detail_response(["model-a"]),
            ]
            chat_id = find_resumable_chat(BASE_URL, "a@b", "Ana", "model-a", ["chat-claimed"])
    assert chat_id == "chat-free"

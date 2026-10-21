"""
title: Force Chat Title Filter
author: E. Palazzo, GPT-6.1
version: 1.4
"""

from typing import Callable, Optional
from open_webui.models.chats import Chats


class Filter:
    def __init__(self):
        pass

    async def _set_initial_title(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable] = None,
        __model__: Optional[dict] = None,
    ) -> dict:
        chat_id = None
        if __metadata__:
            chat_id = __metadata__.get("chat_id")
        if not chat_id and isinstance(body, dict):
            chat_id = body.get("chat_id") or body.get("metadata", {}).get("chat_id")

        if chat_id:
            model = __model__ or {}
            new_title = model.get("name") or model.get("id") or body.get("model")
            if not new_title:
                return body

            try:
                chat_obj = await Chats.get_chat_by_id(chat_id)
                if not chat_obj:
                    return body

                chat_data = dict(chat_obj.chat)
                if chat_data.get("model_title_initialized"):
                    return body
                default_titles = (None, "", "New Chat", "Nuevo chat")
                if any(
                    title not in default_titles
                    for title in (chat_data.get("title"), getattr(chat_obj, "title", None))
                ):
                    return body

                chat_data["title"] = new_title
                chat_data["model_title_initialized"] = True
                await Chats.update_chat_by_id(chat_id, chat_data)
                await Chats.update_chat_title_by_id(chat_id, new_title)

                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "chat:title",
                            "data": new_title,
                        }
                    )
            except Exception as e:
                print(f"Error updating chat title in filter: {e}")

        return body

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable] = None,
        __model__: Optional[dict] = None,
    ) -> dict:
        return await self._set_initial_title(
            body, __user__, __metadata__, __event_emitter__, __model__
        )

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable] = None,
        __model__: Optional[dict] = None,
    ) -> dict:
        return await self._set_initial_title(
            body, __user__, __metadata__, __event_emitter__, __model__
        )
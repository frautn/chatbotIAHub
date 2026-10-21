"""
title: Force Chat Title Filter
author: E. Palazzo, gemini-3.6
version: 1.4
"""

import asyncio
from typing import Dict, Any, Callable, Optional
from open_webui.models.chats import Chats


class Filter:
    def __init__(self):
        pass

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable] = None,
    ) -> dict:
        # Extract chat_id
        chat_id = None
        if __metadata__:
            chat_id = __metadata__.get("chat_id")
        if not chat_id and isinstance(body, dict):
            chat_id = body.get("chat_id") or body.get("metadata", {}).get("chat_id")

        # 1. Extract model name from payload body or metadata
        model_name = body.get("model")
        if not model_name and __metadata__:
            model_name = __metadata__.get("model")

        if chat_id:
            # 2. Wait for background auto-title generation to finish overwriting
            await asyncio.sleep(1.5)

            try:
                # 3. Retrieve chat object from database
                chat_obj = await Chats.get_chat_by_id(chat_id)
                if chat_obj:
                    chat_data = chat_obj.chat

                    # Fallback to model stored in chat metadata if body didn't contain it
                    if not model_name and isinstance(chat_data, dict):
                        models = chat_data.get("models", [])
                        if models and isinstance(models, list) and len(models) > 0:
                            model_name = models[0]

                    # Use model name if found, otherwise fallback title
                    new_title = model_name if model_name else "New Chat"

                    # 4. Update the nested JSON object used by the sidebar list API
                    chat_data["title"] = new_title

                    # 5. Persist updates to DB table and chat JSON
                    await Chats.update_chat_by_id(chat_id, chat_data)
                    await Chats.update_chat_title_by_id(chat_id, new_title)

                    # 6. Push real-time update to the frontend UI
                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "chat:title",
                                "data": new_title,
                            }
                        )
            except Exception as e:
                print(f"Error setting chat title to model name: {e}")

        return body

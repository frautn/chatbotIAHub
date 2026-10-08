import re
import requests
from pydantic import BaseModel

class Filter:
    class Valves(BaseModel):
        gateway_url: str = "http://lti-gateway:8090/api/scores"
        api_token: str = ""

    def __init__(self):
        self.valves = self.Valves()

    def outlet(self, body: dict, __user__: dict = None) -> dict:
        content = body["messages"][-1]["content"]
        match = re.search(r"<grade score=\"(\d+)\" max=\"(\d+)\"\s*/>", content)
        if not match:
            return body

        requests.post(
            self.valves.gateway_url,
            json={
                "chat_id": body["chat_id"],
                "score_given": float(match.group(1)),
                "score_maximum": float(match.group(2)),
            },
            headers={"Authorization": f"Bearer {self.valves.api_token}"},
            timeout=5,
        )
        body["messages"][-1]["content"] = content[: match.start()] + content[match.end():]
        return body
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.request import Request, urlopen


class LarkNotifier:
    def __init__(self, webhook_url: str, secret: str = "", timeout: int = 12):
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = timeout

    def send(self, text: str) -> None:
        payload: dict[str, object] = {"msg_type": "text", "content": {"text": text}}
        if self.secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\n{self.secret}".encode()
            digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
            payload.update({"timestamp": timestamp, "sign": base64.b64encode(digest).decode()})
        request = Request(
            self.webhook_url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            result = json.load(response)
        code = result.get("code", result.get("StatusCode", 0))
        if code not in (0, None):
            raise RuntimeError(f"Lark rejected message: {result}")


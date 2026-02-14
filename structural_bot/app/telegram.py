from __future__ import annotations

import os
import io
import httpx


class TelegramBot:
    def __init__(self) -> None:
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.base = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, text: str) -> None:
        if not self.token or not self.chat_id:
            return
        async with httpx.AsyncClient(timeout=20) as http:
            await http.post(
                f"{self.base}/sendMessage",
                json={"chat_id": self.chat_id, "text": text[:4096], "parse_mode": "HTML"},
            )

    async def send_csv(self, filename: str, content: str, caption: str = "") -> None:
        if not self.token or not self.chat_id:
            return
        async with httpx.AsyncClient(timeout=30) as http:
            files = {"document": (filename, content.encode("utf-8"), "text/csv")}
            data = {"chat_id": self.chat_id, "caption": caption}
            await http.post(f"{self.base}/sendDocument", data=data, files=files)

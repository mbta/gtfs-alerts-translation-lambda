import asyncio
import logging
import time

import httpx

from gtfs_translation.core.translator import Translator


class SmartlingTranslator(Translator):
    _token: str | None = None
    _token_expiry: float = 0

    def __init__(self, user_id: str, user_secret: str, account_uid: str):
        self.user_id = user_id
        self.user_secret = user_secret
        self.account_uid = account_uid
        self.client = httpx.AsyncClient(timeout=10.0)
        self._token_lock = asyncio.Lock()

    async def _get_token(self) -> str:
        async with self._token_lock:
            now = time.time()
            if self._token and now < self._token_expiry:
                return self._token

            url = "https://api.smartling.com/auth-api/v2/authenticate"
            payload = {"userIdentifier": self.user_id, "userSecret": self.user_secret}

            resp = await self.client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            self._token = data["response"]["data"]["accessToken"]
            # Refresh 1 minute before expiry (expiresIn is in seconds)
            expires_in = data["response"]["data"]["expiresIn"]
            self._token_expiry = now + expires_in - 60

            return self._token

    async def translate_batch(self, texts: list[str], target_lang: str) -> list[str]:
        """
        Translates a batch of texts using Smartling MT API.
        Retry on 401 once (token expiry race condition).
        """
        if not texts:
            return []

        try:
            return await self._do_translate_batch(texts, target_lang)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Force refresh
                self._token = None
                return await self._do_translate_batch(texts, target_lang)
            raise e

    async def _do_translate_batch(self, texts: list[str], target_lang: str) -> list[str]:
        token = await self._get_token()

        # MT Router API handles multiple items
        url = f"https://api.smartling.com/mt-router-api/v2/accounts/{self.account_uid}/smartling-mt"

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Use the string index as the key to ensure order mapping
        payload = {
            "sourceLocaleId": "en",
            "targetLocaleId": target_lang,
            "items": [{"key": str(i), "sourceText": text} for i, text in enumerate(texts)],
        }

        try:
            # The MT API can handle up to 1000 items, which is likely plenty for our alerts.
            # If we ever exceed this, we'd need to chunk the texts here.
            resp = await self.client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logging.error(
                "Smartling MT API error: %s - %s", e.response.status_code, e.response.text
            )
            raise e
        except Exception as e:
            logging.exception("Unexpected error calling Smartling MT API")
            raise e

        data = resp.json()
        # Response format:
        # { "response": { "data": { "items": [ { "key": "0", "translationText": "..." }, ... ] } } }
        items = data["response"]["data"]["items"]

        # Sort by key (index) to maintain original order
        sorted_items = sorted(items, key=lambda x: int(x["key"]))
        return [item["translationText"] for item in sorted_items]

    async def close(self) -> None:
        await self.client.aclose()

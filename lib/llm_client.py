"""OpenRouter LLM client for hedge discovery.

Async client for calling LLMs via OpenRouter API.
Used for extracting logical implications between markets.
"""

import asyncio
import os

import httpx

# =============================================================================
# CONFIGURATION
# =============================================================================

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Default model (free tier) - multiple models for fallback
# Note: Model quality matters - must follow JSON format and reject spurious correlations
DEFAULT_MODEL = "nvidia/nemotron-nano-9b-v2:free"

# Free models rotation (fallback when rate limited)
FREE_MODELS = [
    "nvidia/nemotron-nano-9b-v2:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "z-ai/glm-4.5-air:free",
    "stepfun/step-3.5-flash:free",
    "deepseek/deepseek-r1-0528:free",
]

# Request settings
LLM_TIMEOUT = 120.0
LLM_MAX_RETRIES = 4
LLM_DELAY_BETWEEN_CALLS = 3.0  # seconds between calls (free tier rate limit)


# =============================================================================
# LLM CLIENT
# =============================================================================


class LLMClient:
    """
    Async client for OpenRouter API.
    Supports model rotation for free tier rate limits.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        timeout: float = LLM_TIMEOUT,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. "
                "Get a free key at https://openrouter.ai/keys"
            )

        self.model = model
        self.models = FREE_MODELS.copy()
        self._current_model_idx = 0
        self.timeout = timeout
        self.base_url = OPENROUTER_BASE_URL

        self._client: httpx.AsyncClient | None = None

    def _next_model(self) -> str:
        """Rotate to next free model."""
        self._current_model_idx = (self._current_model_idx + 1) % len(self.models)
        model = self.models[self._current_model_idx]
        return model

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> str:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response

        Returns:
            The assistant's response text
        """
        client = await self._get_client()

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Rate limit: wait between calls
        await asyncio.sleep(LLM_DELAY_BETWEEN_CALLS)

        for attempt in range(LLM_MAX_RETRIES):
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if content:
                    return content
                # Some models return empty content
                return data["choices"][0]["message"].get("reasoning_content", "")

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited — rotate model
                    old_model = payload["model"]
                    new_model = self._next_model()
                    payload["model"] = new_model
                    wait_time = 5
                    print(f"  [LLM] Rate limited on {old_model.split('/')[-1]}, switching to {new_model.split('/')[-1]}...")
                    await asyncio.sleep(wait_time)
                    continue
                elif e.response.status_code in (502, 503):
                    wait_time = min(2 ** (attempt + 2), 30)
                    print(f"  [LLM] Server error {e.response.status_code}, retry in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise

            except (httpx.RequestError, httpx.ReadTimeout) as e:
                wait_time = min(2 ** (attempt + 1), 20)
                if attempt < LLM_MAX_RETRIES - 1:
                    print(f"  [LLM] Request error: {e}, retry in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise

        raise RuntimeError(f"Failed after {LLM_MAX_RETRIES} attempts")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_llm_client: LLMClient | None = None


def get_llm_client(model: str = DEFAULT_MODEL) -> LLMClient:
    """
    Get LLM client singleton.

    Args:
        model: Model identifier from OpenRouter

    Returns:
        LLMClient instance
    """
    global _llm_client

    if _llm_client is None or _llm_client.model != model:
        _llm_client = LLMClient(model=model)

    return _llm_client


async def close_llm_client() -> None:
    """Close the LLM client connection."""
    global _llm_client
    if _llm_client:
        await _llm_client.close()
        _llm_client = None

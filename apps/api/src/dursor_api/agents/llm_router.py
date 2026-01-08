"""LLM Router for multi-provider support."""

from dataclasses import dataclass
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from dursor_api.domain.enums import Provider


@dataclass
class LLMConfig:
    """Configuration for an LLM."""

    provider: Provider
    model_name: str
    api_key: str
    temperature: float = 0.0
    max_tokens: int = 4096


class LLMClient:
    """Client for interacting with LLMs."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._openai_client: AsyncOpenAI | None = None
        self._anthropic_client: AsyncAnthropic | None = None

    async def generate(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            messages: List of messages with 'role' and 'content'.
            system: Optional system prompt.

        Returns:
            Generated text response.
        """
        if self.config.provider == Provider.OPENAI:
            return await self._generate_openai(messages, system)
        elif self.config.provider == Provider.ANTHROPIC:
            return await self._generate_anthropic(messages, system)
        elif self.config.provider == Provider.GOOGLE:
            return await self._generate_google(messages, system)
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")

    async def _generate_openai(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
    ) -> str:
        """Generate using OpenAI API."""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=self.config.api_key)

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        # gpt-5-mini uses max_completion_tokens and doesn't support temperature
        if self.config.model_name == "gpt-5-mini":
            response = await self._openai_client.chat.completions.create(
                model=self.config.model_name,
                messages=all_messages,
                max_completion_tokens=self.config.max_tokens,
            )
        else:
            response = await self._openai_client.chat.completions.create(
                model=self.config.model_name,
                messages=all_messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

        return response.choices[0].message.content or ""

    async def _generate_anthropic(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
    ) -> str:
        """Generate using Anthropic API."""
        if self._anthropic_client is None:
            self._anthropic_client = AsyncAnthropic(api_key=self.config.api_key)

        response = await self._anthropic_client.messages.create(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            system=system or "",
            messages=messages,
        )

        # Extract text from content blocks
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)

        return "".join(text_parts)

    async def _generate_google(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
    ) -> str:
        """Generate using Google Generative AI API (REST)."""
        # Use REST API for async support
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model_name}:generateContent"

        # Convert messages to Google format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        request_body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
        }

        if system:
            request_body["systemInstruction"] = {"parts": [{"text": system}]}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=request_body,
                params={"key": self.config.api_key},
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

        # Extract text from response
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(part.get("text", "") for part in parts)

        return ""


class LLMRouter:
    """Router for managing multiple LLM clients."""

    def __init__(self):
        self._clients: dict[str, LLMClient] = {}

    def get_client(self, config: LLMConfig) -> LLMClient:
        """Get or create an LLM client for the given config.

        Args:
            config: LLM configuration.

        Returns:
            LLMClient instance.
        """
        key = f"{config.provider.value}:{config.model_name}"
        if key not in self._clients:
            self._clients[key] = LLMClient(config)
        return self._clients[key]

    def clear(self) -> None:
        """Clear all cached clients."""
        self._clients.clear()

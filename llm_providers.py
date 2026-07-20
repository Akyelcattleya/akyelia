"""Akyel AI - Multi-LLM Provider Integration"""
import json
import re
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

import httpx

from config import config, LLMProviderConfig


class LLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, provider_config: LLMProviderConfig):
        self.config = provider_config
        self.api_key = ""
        if provider_config.requires_key:
            import os
            self.api_key = os.getenv(provider_config.api_key_env, "")

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        ...

    def get_available_models(self) -> list[str]:
        return self.config.models

    @property
    def is_available(self) -> bool:
        if self.config.requires_key:
            return bool(self.api_key)
        return True


class OpenAICompatibleProvider(LLMProvider):
    """Provider using OpenAI-compatible API format (DeepSeek, OpenAI, Groq)."""

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        model = model or self.config.default_model
        url = f"{self.config.base_url}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue


class AnthropicProvider(LLMProvider):
    """Provider using Anthropic API format."""

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        model = model or self.config.default_model
        url = f"{self.config.base_url}/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        # Convert OpenAI-style messages to Anthropic format
        system_msg = None
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "user":
                anthropic_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                anthropic_messages.append({"role": "assistant", "content": msg["content"]})

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if system_msg:
            payload["system"] = system_msg

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        try:
                            chunk = json.loads(data)
                            if chunk.get("type") == "content_block_delta":
                                delta = chunk.get("delta", {})
                                content = delta.get("text", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue


class GeminiProvider(LLMProvider):
    """Provider using Google Gemini API format."""

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        model = model or self.config.default_model

        # Convert messages to Gemini format
        gemini_contents = []
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                gemini_contents.append({
                    "role": "user",
                    "parts": [{"text": msg["content"]}]
                })
            elif msg["role"] == "assistant":
                gemini_contents.append({
                    "role": "model",
                    "parts": [{"text": msg["content"]}]
                })

        url = f"{self.config.base_url}/models/{model}:streamGenerateContent?alt=sse&key={self.api_key}"

        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        try:
                            chunk = json.loads(data)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                content = candidates[0].get("content", {})
                                parts = content.get("parts", [])
                                for part in parts:
                                    text = part.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue


class OllamaProvider(LLMProvider):
    """Provider using Ollama local API."""

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        model = model or self.config.default_model
        url = f"{self.config.base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue


# Provider registry
PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "openai": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


def get_provider(provider_name: str) -> Optional[LLMProvider]:
    """Get a configured LLM provider by name."""
    if provider_name not in config.providers:
        return None

    provider_config = config.providers[provider_name]
    provider_class = PROVIDER_REGISTRY.get(provider_config.api_type)

    if provider_class is None:
        return None

    return provider_class(provider_config)


def get_available_providers() -> dict:
    """Get list of available providers with their status."""
    result = {}
    for name, pconf in config.providers.items():
        provider = get_provider(name)
        result[name] = {
            "name": name,
            "display_name": pconf.display_name,
            "icon": pconf.icon,
            "description": pconf.description,
            "available": provider.is_available if provider else False,
            "models": pconf.models,
            "default_model": pconf.default_model,
        }
    return result

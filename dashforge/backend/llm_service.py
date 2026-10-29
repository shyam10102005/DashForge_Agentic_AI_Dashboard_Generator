"""
DashForge - LLM Service
Provider-independent LLM interface using Ollama for local inference.
"""
import json
import httpx
from typing import Optional
from backend.config import settings


class LLMService:
    """Interface to Ollama for local LLM inference."""

    def __init__(self):
        self.base_url = settings.ollama.base_url
        self.model = settings.ollama.model
        self.timeout = settings.agent_timeout

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 3072,
        json_mode: bool = False
    ) -> str:
        """Generate a response from the LLM."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                return result.get("message", {}).get("content", "")
        except httpx.TimeoutException:
            return "Error: LLM request timed out. Please try again."
        except httpx.ConnectError:
            return "Error: Cannot connect to Ollama. Make sure Ollama is running (ollama serve)."
        except Exception as e:
            return f"Error: LLM request failed - {str(e)}"

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
    ) -> dict:
        """Generate a JSON response from the LLM."""
        response = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            json_mode=True
        )

        try:
            if response.startswith("Error:"):
                return {"error": response}

            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            return {"error": f"Failed to parse LLM response as JSON: {response[:200]}"}

    async def check_health(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


# Singleton
llm = LLMService()

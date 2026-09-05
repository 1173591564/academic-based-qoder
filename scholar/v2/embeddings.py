"""Small embedding-provider adapter shared by builds and online queries."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from scholar import config

from .models import ScholarError


@dataclass(frozen=True)
class EmbeddingProvider:
    provider: str
    model: str
    api_key: str
    dimensions: int
    timeout_seconds: float = 30

    def __call__(self, text: str) -> list[float]:
        return self.embed(text)

    def embed(self, text: str, timeout_seconds: float | None = None) -> list[float]:
        if not self.api_key:
            raise ScholarError(
                "VECTOR_UNAVAILABLE", "embedding provider is not configured"
            )
        if self.provider == "zhipu":
            url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
        elif self.provider == "openai":
            url = "https://api.openai.com/v1/embeddings"
        else:
            raise ScholarError(
                "VECTOR_UNAVAILABLE",
                f"unsupported embedding provider: {self.provider}",
            )
        payload_data: dict[str, str | int] = {
            "model": self.model,
            "input": text[:8_000],
        }
        if self.provider == "openai":
            payload_data["dimensions"] = self.dimensions
        payload = json.dumps(payload_data).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=(
                    self.timeout_seconds
                    if timeout_seconds is None
                    else min(self.timeout_seconds, timeout_seconds)
                ),
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
            embedding = [float(value) for value in body["data"][0]["embedding"]]
        except ScholarError:
            raise
        except Exception as error:
            raise ScholarError(
                "EXTERNAL_UNAVAILABLE", "embedding provider request failed"
            ) from error
        if len(embedding) != self.dimensions:
            raise ScholarError(
                "VECTOR_UNAVAILABLE",
                f"embedding dimension {len(embedding)} does not match "
                f"{self.dimensions}",
            )
        return embedding


def configured_provider() -> EmbeddingProvider | None:
    if not config.EMBEDDING_API_KEY:
        return None
    return EmbeddingProvider(
        provider=config.EMBEDDING_PROVIDER,
        model=config.EMBEDDING_MODEL,
        api_key=config.EMBEDDING_API_KEY,
        dimensions=config.V2_EMBEDDING_DIM,
    )

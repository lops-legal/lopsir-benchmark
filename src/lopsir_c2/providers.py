"""Free remote inference used by C2: NVIDIA API Catalog and OpenRouter.

Keys come only from the environment (.env, ignored by Git) and are never logged.
Every call records tokens, latency, retries and failures in a usage ledger so the
report can state real API usage instead of assumed costs (free tier => USD 0 billed).
"""
import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv

from .common import ARTIFACTS, ROOT, write_json

load_dotenv(ROOT / ".env")

NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class Ledger:
    """Thread-safe usage accounting per provider/model."""

    def __init__(self):
        self.lock = threading.Lock()
        self.rows = {}

    def add(self, provider, model, *, tokens=0, seconds=0.0, ok=True, retries=0):
        with self.lock:
            row = self.rows.setdefault(f"{provider}:{model}", {"requests": 0, "failed": 0, "retries": 0,
                                                              "prompt_tokens": 0, "seconds": 0.0})
            row["requests"] += 1
            row["failed"] += 0 if ok else 1
            row["retries"] += retries
            row["prompt_tokens"] += tokens
            row["seconds"] += seconds

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.rows))


LEDGER = Ledger()


def _post(provider, url, payload, timeout=300, max_retries=8):
    key = os.environ["NVIDIA_API_KEY" if provider == "nvidia" else "OPENROUTER_API_KEY"]
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    delay, start = 2.0, time.perf_counter()
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as error:
            response, failure = None, str(error)
        if response is not None and response.ok:
            body = response.json()
            if provider == "openrouter" and "error" in body:
                failure = str(body["error"])[:300]
            else:
                usage = body.get("usage") or {}
                LEDGER.add(provider, payload["model"], tokens=usage.get("prompt_tokens", 0) or usage.get("total_tokens", 0),
                           seconds=time.perf_counter() - start, retries=attempt)
                return body
        elif response is not None:
            failure = f"HTTP {response.status_code}: {response.text[:300]}"
            if response.status_code in (400, 401, 403, 404, 410, 422):
                break  # not transient
        if attempt < max_retries:
            time.sleep(delay)
            delay = min(delay * 2, 60)
    LEDGER.add(provider, payload["model"], seconds=time.perf_counter() - start, ok=False, retries=attempt)
    raise RuntimeError(f"{provider} {payload['model']} failed: {failure}")


# ---------------------------------------------------------------- embeddings

EMBEDDERS = {
    # NVIDIA API Catalog, free trial endpoint (checked 2026-10-29)
    "nemotron-3.5-embed-8b": {"provider": "nvidia", "model": "nvidia/nemotron-3.5-embed-8b", "dim": 4096},
    "nemotron-3.5-embed-1b": {"provider": "nvidia", "model": "nvidia/nemotron-3.5-embed-1b", "dim": 2048},
    # OpenRouter ':free' mirror of the same weights, used only as fallback
    "nemotron-3.5-embed-8b@openrouter": {"provider": "openrouter", "model": "nvidia/nemotron-3.5-embed-8b:free", "dim": 4096},
}


def embed_batch(name, texts, input_type):
    spec = EMBEDDERS[name]
    if spec["provider"] == "nvidia":
        body = _post("nvidia", f"{NVIDIA_BASE}/embeddings", {
            "model": spec["model"], "input": texts, "input_type": input_type,
            "encoding_format": "float", "truncate": "END"})
    else:
        body = _post("openrouter", f"{OPENROUTER_BASE}/embeddings", {"model": spec["model"], "input": texts})
    rows = sorted(body["data"], key=lambda item: item["index"])
    return np.asarray([row["embedding"] for row in rows], dtype=np.float32)


class EmbeddingStore:
    """Resumable vector store: artifacts/c2/vectors/<dataset>/<embedder>/<kind>.{npy,ids.json}.
    Vectors are saved in shards while encoding, so an interrupted run continues where it stopped.
    The id order is stored next to the matrix to avoid misalignment."""

    def __init__(self, dataset, embedder, kind):
        self.embedder, self.kind = embedder, kind
        self.dir = ARTIFACTS / "vectors" / dataset / embedder
        self.shards = self.dir / f"{kind}.shards"
        self.dir.mkdir(parents=True, exist_ok=True)

    @property
    def matrix_path(self):
        return self.dir / f"{self.kind}.npy"

    def load(self):
        ids = json.loads((self.dir / f"{self.kind}.ids.json").read_text(encoding="utf-8"))
        return ids, np.load(self.matrix_path)

    def exists(self):
        return self.matrix_path.exists()

    def build(self, ids, texts, input_type, batch_size=32, workers=3, progress=None):
        if self.exists():
            return self.load()
        self.shards.mkdir(exist_ok=True)
        batches = [(i, ids[i:i + batch_size], texts[i:i + batch_size]) for i in range(0, len(ids), batch_size)]
        todo = [b for b in batches if not (self.shards / f"{b[0]:08d}.npy").exists()]
        started = time.perf_counter()

        def work(batch):
            offset, _, chunk = batch
            vectors = embed_batch(self.embedder, chunk, input_type)
            np.save(self.shards / f"{offset:08d}.npy", vectors)
            return len(chunk)

        done = len(ids) - sum(len(b[1]) for b in todo)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for count in pool.map(work, todo):
                done += count
                if progress:
                    progress(done, len(ids), time.perf_counter() - started)
        matrix = np.concatenate([np.load(self.shards / f"{b[0]:08d}.npy") for b in batches])
        if matrix.shape[0] != len(ids):
            raise ValueError("Vector count does not match ids")
        np.save(self.matrix_path, matrix)
        (self.dir / f"{self.kind}.ids.json").write_text(json.dumps(ids), encoding="utf-8")
        write_json(self.dir / f"{self.kind}.meta.json", {
            "embedder": EMBEDDERS[self.embedder], "input_type": input_type, "count": len(ids),
            "shape": list(matrix.shape), "dtype": str(matrix.dtype), "truncate": "END",
            "encode_seconds_this_session": time.perf_counter() - started,
            "ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest()})
        for shard in self.shards.glob("*.npy"):
            shard.unlink()
        self.shards.rmdir()
        return ids, matrix


# ---------------------------------------------------------------- chat (query expansion)

# Free chat models answering on 2026-10-29 (nemotron-3-super returned 404 for this account;
# gemma-4-31b on NVIDIA answered but queued for ~4 minutes, so it is only a fallback).
# Nemotron 3.5 Lightning is a reasoning model: with thinking on, short budgets return empty
# content, so thinking is disabled explicitly (2.6 s per expansion on OpenRouter, cost 0).
CHAT_MODELS = {
    "nemotron-3.5-lightning@openrouter": {"provider": "openrouter", "model": "nvidia/nemotron-3.5-lightning:free",
                                          "extra": {"reasoning": {"enabled": False}}},
    "nemotron-3.5-lightning": {"provider": "nvidia", "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
                               "extra": {"chat_template_kwargs": {"enable_thinking": False}}},
    "gemma-4-31b": {"provider": "nvidia", "model": "google/gemma-4-31b-it"},
}


class ChatCache:
    """Prompt-keyed JSON cache so generated expansions are frozen and reusable."""

    def __init__(self, name):
        self.path = ARTIFACTS / "cache" / f"chat-{name}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.items = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.lock = threading.Lock()

    def key(self, model, prompt, params):
        return hashlib.sha256(json.dumps([model, prompt, params], sort_keys=True).encode()).hexdigest()

    def get(self, key):
        return self.items.get(key)

    def put(self, key, value):
        with self.lock:
            self.items[key] = value
            self.path.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")


def chat(name, messages, *, max_tokens=256, temperature=0.0, cache=None):
    spec = CHAT_MODELS[name]
    params = {"max_tokens": max_tokens, "temperature": temperature, **spec.get("extra", {})}
    key = cache.key(spec["model"], messages, params) if cache else None
    if cache and cache.get(key):
        return cache.get(key)
    base = NVIDIA_BASE if spec["provider"] == "nvidia" else OPENROUTER_BASE
    body = _post(spec["provider"], f"{base}/chat/completions", {"model": spec["model"], "messages": messages, **params})
    message = body["choices"][0]["message"]
    text = (message.get("content") or "").strip()
    if cache and text:
        cache.put(key, text)
    return text

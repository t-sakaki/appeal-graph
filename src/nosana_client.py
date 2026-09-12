"""Nosana上にデプロイしたLLM推論エンドポイント（vLLM OpenAI互換API）を呼び出すクライアント。

デプロイのライフサイクル（作成・起動・エンドポイント確認）はNosana Deployments APIで行い、
実行中はここから通常のOpenAI Chat Completions形式でリクエストする。
"""
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

NOSANA_API_KEY = os.environ["NOSANA_API_KEY"]
NOSANA_API_BASE = "https://dashboard.k8s.prd.nos.ci/api"
NOSANA_MODEL_NAME = "DeepSeek-R1-Distill-Qwen-1.5B"


def _headers():
    return {"Authorization": f"Bearer {NOSANA_API_KEY}"}


def get_deployment(deployment_id: str) -> dict:
    resp = requests.get(f"{NOSANA_API_BASE}/deployments/{deployment_id}", headers=_headers())
    resp.raise_for_status()
    return resp.json()


def get_endpoint_url(deployment_id: str) -> str | None:
    deployment = get_deployment(deployment_id)
    for endpoint in deployment.get("endpoints", []):
        if endpoint.get("online"):
            return endpoint["url"]
    return None


def wait_for_endpoint(deployment_id: str, timeout_seconds: int = 300, poll_interval: int = 10) -> str:
    """デプロイのステータスがオンラインになるまで待機し、エンドポイントURLを返す。"""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        deployment = get_deployment(deployment_id)
        status = deployment.get("status")
        print(f"[Nosana] status={status}")
        for endpoint in deployment.get("endpoints", []):
            if endpoint.get("online"):
                return endpoint["url"]
        time.sleep(poll_interval)
    raise TimeoutError(f"Nosana deployment {deployment_id} did not come online within {timeout_seconds}s")


def generate_draft_text(endpoint_url: str, prompt: str, max_tokens: int = 500) -> str:
    """Nosana上のvLLMエンドポイントにOpenAI互換のChat Completions APIでリクエストする。"""
    resp = requests.post(
        f"{endpoint_url}/v1/chat/completions",
        json={
            "model": NOSANA_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


if __name__ == "__main__":
    import sys

    deployment_id = sys.argv[1]
    url = wait_for_endpoint(deployment_id)
    print(f"[Nosana] endpoint online: {url}")
    text = generate_draft_text(url, "こんにちは、一言で自己紹介してください。")
    print(text)

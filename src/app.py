"""GraphSandbox Copilot（裁決・答申版）— FastAPI Webラッパー。

Neo4j(グラフコンテキスト) -> ドラフト生成(Nosana LLM、未設定時はテンプレート生成) ->
Daytonaサンドボックスでの判例引用検証、という一連のコアループをHTTP経由で叩けるようにする。
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import build_draft, build_verification_code
from graph_context import GraphContext
from sandbox_runner import SandboxRunner

app = FastAPI(title="Toushin Graph Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class VerifyResponse(BaseModel):
    authority: str
    review_authority: str
    ground_name: str
    draft_body: str
    citations_in_graph: list[str]
    sandbox_exit_code: int
    sandbox_result: dict
    status: str


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html><body style="font-family: sans-serif; max-width: 720px; margin: 40px auto;">
    <h1>Toushin Graph Copilot</h1>
    <p>Neo4jの法令グラフ + Daytonaサンドボックスによる判例引用検証API。</p>
    <ul>
      <li><a href="/authorities">GET /authorities</a> — 対応機関・条文一覧</li>
      <li>GET /verify?authority_key=anjo-city&article_number=第7条第2号</li>
    </ul>
    </body></html>
    """


@app.get("/authorities")
def list_authorities():
    graph = GraphContext()
    try:
        return graph.list_authorities()
    finally:
        graph.close()


@app.get("/verify", response_model=VerifyResponse)
def verify(authority_key: str, article_number: str):
    graph = GraphContext()
    sandbox = SandboxRunner()
    try:
        context = graph.get_context_for(authority_key, article_number)
        if not context:
            raise HTTPException(status_code=404, detail="authority_key/article_number not found")

        draft = build_draft(context)
        code = build_verification_code(draft, context["citations"])
        result = sandbox.run_code(code)

        status = "verified" if result["exit_code"] == 0 else "unverified_citation_detected"

        return VerifyResponse(
            authority=context["authority"],
            review_authority=context["review_authority"],
            ground_name=context["ground_name"],
            draft_body=draft["body"],
            citations_in_graph=context["citations"],
            sandbox_exit_code=result["exit_code"],
            sandbox_result={"raw": result["result"]},
            status=status,
        )
    finally:
        sandbox.cleanup()
        graph.close()

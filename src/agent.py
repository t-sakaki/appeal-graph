"""GraphSandbox Copilot（裁決・答申版）コアロジック。

Neo4jのグラフから機関・条文・反論ロジック・判例のコンテキストを取得し、
そのコンテキストのみを根拠に審査請求の反論書ドラフトを生成する。
生成したドラフトが実際にグラフに存在する判例のみを引用しているかを
Daytonaサンドボックス内のコードで検証する（LLMの判例ハルシネーション対策）。
"""
import json

from graph_context import GraphContext
from sandbox_runner import SandboxRunner


def build_draft(context: dict) -> dict:
    """グラフコンテキストのみを根拠に反論書ドラフトを組み立てる（デモ用の単純な生成）。"""
    reasonings = context["reasonings"]
    citations = context["citations"]

    body_lines = [f"【不開示事由】{context['ground_name']}（{context['ground_description']}）", "", "【反論】"]
    body_lines += [f"・{r}" for r in reasonings]

    return {
        "authority": context["authority"],
        "review_authority": context["review_authority"],
        "body": "\n".join(body_lines),
        "cited_citations": citations,
    }


def build_verification_code(draft: dict, allowed_citations: list[str]) -> str:
    """ドラフト本文中の判例引用がグラフ由来の許可リストに含まれるかを検証するコード。

    実運用では、LLMが生成した本文をここに渡し、正規表現で引用を抽出して
    グラフの許可リストと突き合わせる。ここではデモのため draft をそのまま埋め込む。
    """
    return f"""
import re
import json

draft_body = {json.dumps(draft["body"])}
allowed_citations = {json.dumps(allowed_citations)}

CITATION_RE = re.compile(r"[（(]([^（）()]*(?:判|決定)[^（）()]*)[）)]")
found = CITATION_RE.findall(draft_body)

unverified = [c for c in found if c not in allowed_citations]

result = {{
    "found_citations": found,
    "unverified_citations": unverified,
    "ok": len(unverified) == 0,
}}
print(json.dumps(result, ensure_ascii=False))
if unverified:
    raise SystemExit(1)
"""


def run_agent_loop(authority_key: str, article_number: str):
    graph = GraphContext()
    sandbox = SandboxRunner()

    try:
        context = graph.get_context_for(authority_key, article_number)
        if not context:
            print(f"[Graph] No data for {authority_key} / {article_number}")
            return {"status": "not_found"}

        print(f"[Graph] Context: 機関={context['authority']} 条文={context['ground_name']}")
        print(f"[Graph] 反論ロジック {len(context['reasonings'])}件, 判例 {len(context['citations'])}件")

        draft = build_draft(context)
        print("\n[Agent] 生成ドラフト:\n" + draft["body"] + "\n")

        code = build_verification_code(draft, context["citations"])
        print("[Sandbox] Daytonaサンドボックスで引用の整合性を検証中...")
        result = sandbox.run_code(code)
        print(f"[Sandbox] exit_code={result['exit_code']} result={result['result'].strip()}")

        status = "verified" if result["exit_code"] == 0 else "unverified_citation_detected"
        return {"status": status, "draft": draft}
    finally:
        sandbox.cleanup()
        graph.close()


if __name__ == "__main__":
    outcome = run_agent_loop("anjo-city", "第7条第4号")
    print("\n[Agent] Final outcome:", outcome["status"])

"""Neo4jから機関・条文・反論ロジック・判例のコンテキストを取得する。"""
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


class GraphContext:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )

    def close(self):
        self.driver.close()

    def list_authorities(self) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:機関)-[:規定する]->(g:非開示条文)
                RETURN a.key AS key, a.authority AS authority, g.number AS number, g.name AS name
                ORDER BY a.key, g.number
                """
            )
            return [dict(r) for r in result]

    def get_context_for(self, authority_key: str, article_number: str) -> dict:
        """指定機関・条文に対する反論ロジック・引用判例をグラフから取得する。"""
        with self.driver.session() as session:
            record = session.run(
                """
                MATCH (a:機関 {key: $key})-[:規定する]->
                      (g:非開示条文 {authority_key: $key, number: $number})
                OPTIONAL MATCH (g)-[:該当する]->(p:反論パターン)
                OPTIONAL MATCH (p)-[:主張]->(r:反論ロジック)
                OPTIONAL MATCH (p)-[:引用]->(c:判例)
                RETURN a.authority AS authority,
                       a.review_authority AS review_authority,
                       g.name AS ground_name,
                       g.description AS ground_description,
                       collect(DISTINCT r.text) AS reasonings,
                       collect(DISTINCT c.citation) AS citations
                """,
                key=authority_key,
                number=article_number,
            ).single()

            if record is None:
                return {}

            return {
                "authority": record["authority"],
                "review_authority": record["review_authority"],
                "ground_name": record["ground_name"],
                "ground_description": record["ground_description"],
                "reasonings": [r for r in record["reasonings"] if r],
                "citations": [c for c in record["citations"] if c],
            }


    def get_full_graph(self) -> dict:
        """可視化用に、グラフ全体をvis.js形式のnodes/edgesとして取得する。"""
        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        def add_node(node_id: str, label: str, group: str, detail: dict):
            if node_id not in nodes:
                nodes[node_id] = {"id": node_id, "label": label, "group": group, "detail": detail}

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:機関)-[:規定する]->(g:非開示条文)
                OPTIONAL MATCH (g)-[:該当する]->(p:反論パターン)
                OPTIONAL MATCH (p)-[:主張]->(r:反論ロジック)
                OPTIONAL MATCH (p)-[:引用]->(c:判例)
                RETURN a.key AS a_key, a.authority AS a_name, a.category AS a_category,
                       a.authority_type AS a_type, a.review_authority AS a_review,
                       g.authority_key AS g_key, g.number AS g_number, g.name AS g_name,
                       g.description AS g_description,
                       p.category AS p_category, p.number AS p_number,
                       r.text AS r_text, c.citation AS c_citation
                """
            )
            for row in result:
                a_id = f"機関:{row['a_key']}"
                add_node(a_id, row["a_name"], "機関", {
                    "種別": "機関",
                    "名称": row["a_name"],
                    "区分": row["a_category"],
                    "機関種別": row["a_type"],
                    "審査会（諮問先）": row["a_review"],
                })

                g_id = f"条文:{row['g_key']}:{row['g_number']}"
                add_node(g_id, f"{row['g_number']} {row['g_name']}", "非開示条文", {
                    "種別": "非開示条文",
                    "条項": row["g_number"],
                    "名称": row["g_name"],
                    "条文内容": row["g_description"],
                })
                edges.append({"from": a_id, "to": g_id})

                if row["p_number"]:
                    p_id = f"反論パターン:{row['p_category']}:{row['p_number']}"
                    add_node(p_id, f"{row['p_category']}/{row['p_number']}", "反論パターン", {
                        "種別": "反論パターン",
                        "区分": row["p_category"],
                        "条項": row["p_number"],
                        "説明": "同じ区分・条項の機関で共有される反論の型",
                    })
                    edges.append({"from": g_id, "to": p_id})

                    if row["r_text"]:
                        r_id = f"反論ロジック:{hash(row['r_text'])}"
                        add_node(r_id, row["r_text"][:20] + "…", "反論ロジック", {
                            "種別": "反論ロジック",
                            "全文": row["r_text"],
                        })
                        edges.append({"from": p_id, "to": r_id})

                    if row["c_citation"]:
                        c_id = f"判例:{row['c_citation']}"
                        add_node(c_id, row["c_citation"], "判例", {
                            "種別": "判例",
                            "引用表記": row["c_citation"],
                        })
                        edges.append({"from": p_id, "to": c_id})

        # 同一ペアの重複エッジを除去
        unique_edges = {(e["from"], e["to"]) for e in edges}
        return {
            "nodes": list(nodes.values()),
            "edges": [{"from": f, "to": t} for f, t in unique_edges],
        }


if __name__ == "__main__":
    ctx = GraphContext()
    for row in ctx.list_authorities()[:5]:
        print(row)
    print("---")
    print(ctx.get_context_for("anjo-city", "第7条第4号"))
    ctx.close()

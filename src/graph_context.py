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


if __name__ == "__main__":
    ctx = GraphContext()
    for row in ctx.list_authorities()[:5]:
        print(row)
    print("---")
    print(ctx.get_context_for("anjo-city", "第7条第4号"))
    ctx.close()

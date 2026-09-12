"""civic-lensの条例・反論ロジックデータをNeo4jのグラフスキーマに変換して投入する。

グラフスキーマ:
  (:機関 {key, authority, category, authority_type, review_authority})
      -[:規定する]->(:非開示条文 {authority_key, number, name, description})
      -[:該当する]->(:反論パターン {category, number})
      -[:主張]->(:反論ロジック {text})
      -[:引用]->(:判例 {citation})

同じ category+number の反論パターンは複数機関から共有されるため、
「この判例は複数機関の条文で共通して引用されている」といった
GraphRAG的な横断参照が可能になる。
"""
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from civic_lens_ordinance_logic import (  # noqa: E402
    COMMON_COUNTER_ARGUMENTS,
    COURT_COUNTER_ARGUMENTS,
    POLICE_COUNTER_ARGUMENTS,
)

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "civic_lens_data" / "authorities"

CATEGORY_ARGUMENT_MAP = {
    "自治体": COMMON_COUNTER_ARGUMENTS,
    "警察": POLICE_COUNTER_ARGUMENTS,
    "裁判所": COURT_COUNTER_ARGUMENTS,
}

# 「（最判平14.2.8）」のような判例引用を抽出する
CITATION_RE = re.compile(r"[（(]([^（）()]*(?:判|決定)[^（）()]*)[）)]")


def extract_citation(text: str):
    m = CITATION_RE.search(text)
    return m.group(1) if m else None


import os  # noqa: E402


class GraphLoader:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )

    def close(self):
        self.driver.close()

    def reset(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def load(self):
        authority_files = sorted(DATA_DIR.glob("*.json"))
        with self.driver.session() as session:
            for path in authority_files:
                data = json.loads(path.read_text(encoding="utf-8"))
                session.execute_write(self._load_authority, data)
        print(f"Loaded {len(authority_files)} authorities into Neo4j.")

    @staticmethod
    def _load_authority(tx, data: dict):
        tx.run(
            """
            MERGE (a:機関 {key: $key})
            SET a.authority = $authority,
                a.category = $category,
                a.authority_type = $authority_type,
                a.ordinance_name = $ordinance_name,
                a.review_authority = $review_authority
            """,
            key=data["key"],
            authority=data["authority"],
            category=data["category"],
            authority_type=data["authority_type"],
            ordinance_name=data["ordinance_name"],
            review_authority=data["review_authority"],
        )

        category = data["category"]
        argument_map = CATEGORY_ARGUMENT_MAP.get(category, {})

        for ground in data["non_disclosure_grounds"]:
            number = ground["number"]

            tx.run(
                """
                MATCH (a:機関 {key: $key})
                MERGE (g:非開示条文 {authority_key: $key, number: $number})
                SET g.name = $name, g.description = $description
                MERGE (a)-[:規定する]->(g)
                """,
                key=data["key"],
                number=number,
                name=ground["name"],
                description=ground["description"],
            )

            arguments = argument_map.get(number)
            if not arguments:
                continue

            tx.run(
                """
                MATCH (g:非開示条文 {authority_key: $key, number: $number})
                MERGE (p:反論パターン {category: $category, number: $number})
                MERGE (g)-[:該当する]->(p)
                """,
                key=data["key"],
                number=number,
                category=category,
            )

            for text in arguments:
                citation = extract_citation(text)
                tx.run(
                    """
                    MATCH (p:反論パターン {category: $category, number: $number})
                    MERGE (r:反論ロジック {text: $text})
                    MERGE (p)-[:主張]->(r)
                    """,
                    category=category,
                    number=number,
                    text=text,
                )
                if citation:
                    tx.run(
                        """
                        MATCH (p:反論パターン {category: $category, number: $number})
                        MERGE (c:判例 {citation: $citation})
                        MERGE (p)-[:引用]->(c)
                        """,
                        category=category,
                        number=number,
                        citation=citation,
                    )


if __name__ == "__main__":
    loader = GraphLoader()
    try:
        loader.reset()
        loader.load()
    finally:
        loader.close()

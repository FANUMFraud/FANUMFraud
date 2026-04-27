# Elasticsearch integration for company indexing and fuzzy search.

import json
import logging
import os

from elasticsearch import Elasticsearch, NotFoundError

logger = logging.getLogger(__name__)

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
INDEX_NAME = "companies"

_client: Elasticsearch | None = None


def get_es_client() -> Elasticsearch:
    # Return a module-level ES client, lazily initialised.
    global _client
    if _client is None:
        _client = Elasticsearch(ELASTICSEARCH_URL)
    return _client


# Index management

COMPANY_MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "polish_fuzzy": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "name": {"type": "text", "analyzer": "polish_fuzzy"},
            "nip": {"type": "keyword"},
            "aliases": {"type": "text", "analyzer": "polish_fuzzy"},
            "current_score": {"type": "float"},
        }
    },
}


def init_index() -> None:
    # Create the companies index if it doesn't exist.
    es = get_es_client()
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=COMPANY_MAPPING)
        logger.info("Created Elasticsearch index '%s'", INDEX_NAME)
    else:
        logger.info("Elasticsearch index '%s' already exists", INDEX_NAME)


# CRUD operations

def index_company(company) -> None:
    # Index (or re-index) a Company ORM object.
    es = get_es_client()
    aliases_raw = company.aliases or "[]"
    try:
        aliases_list = json.loads(aliases_raw) if isinstance(aliases_raw, str) else aliases_raw
    except (json.JSONDecodeError, TypeError):
        aliases_list = []

    doc = {
        "name": company.name,
        "nip": company.nip,
        "aliases": aliases_list,
        "current_score": company.current_score,
    }
    es.index(index=INDEX_NAME, id=str(company.id), document=doc)
    logger.debug("Indexed company id=%d name=%s", company.id, company.name)


def delete_company_doc(company_id: int) -> None:
    # Remove a company from the index.
    es = get_es_client()
    try:
        es.delete(index=INDEX_NAME, id=str(company_id))
    except NotFoundError:
        pass


def search_companies(query: str, size: int = 20) -> list[dict]:
    """
    Fuzzy search for companies by name, aliases, or NIP.

    Returns list of dicts with id, name, nip, current_score.
    """
    es = get_es_client()

    body = {
        "size": size,
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["name^3", "aliases^2"],
                            "fuzziness": "AUTO",
                        }
                    },
                    {
                        "term": {"nip": query},
                    },
                ],
                "minimum_should_match": 1,
            }
        },
    }

    resp = es.search(index=INDEX_NAME, body=body)
    results = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        results.append(
            {
                "id": int(hit["_id"]),
                "name": src.get("name"),
                "nip": src.get("nip"),
                "current_score": src.get("current_score"),
                "es_score": hit["_score"],
            }
        )
    return results

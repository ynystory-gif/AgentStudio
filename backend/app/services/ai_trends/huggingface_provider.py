from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
import re
import xml.etree.ElementTree as ET

import httpx

from app.services.active_ollama_model_service import current_runtime_ollama_model

SEOUL = ZoneInfo("Asia/Seoul")
HF = "https://huggingface.co"


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=SEOUL)
    except Exception:
        return None


def _human_repo_summary(row: dict[str, Any]) -> str:
    card = row.get("cardData") if isinstance(row.get("cardData"), dict) else {}
    description = str(card.get("description") or row.get("description") or "").strip()
    if description:
        return re.sub(r"\s+", " ", description)[:1200]
    facts: list[str] = []
    pipeline = str(row.get("pipeline_tag") or row.get("pipelineTag") or "").strip()
    library = str(row.get("library_name") or row.get("libraryName") or "").strip()
    tags = [str(x).strip() for x in (row.get("tags") or []) if str(x).strip()][:10]
    if pipeline:
        facts.append(f"task={pipeline}")
    if library:
        facts.append(f"library={library}")
    if tags:
        facts.append("tags=" + ", ".join(tags))
    return "; ".join(facts)


def _repo_item(row: dict[str, Any], category: str) -> dict[str, Any]:
    repo_id = str(row.get("id") or row.get("modelId") or "").strip()
    modified = row.get("lastModified") or row.get("last_modified") or ""
    likes = int(row.get("likes") or 0)
    downloads = int(row.get("downloads") or 0)
    trending = float(row.get("trendingScore") or row.get("trending_score") or 0)
    return {
        "id": repo_id,
        "source": "Hugging Face",
        "category": category,
        "title_original": repo_id,
        "title_ko": repo_id,
        "summary_original": _human_repo_summary(row),
        "summary_ko": "",
        "developer_point": "",
        "author": repo_id.split("/", 1)[0] if "/" in repo_id else "",
        "published_at": str(row.get("createdAt") or ""),
        "modified_at": str(modified),
        "url": f"{HF}/{'datasets/' if category=='datasets' else 'spaces/' if category=='spaces' else ''}{repo_id}",
        "likes": likes,
        "downloads": downloads,
        "ranking_score": trending or (likes * 100 + min(downloads, 10_000_000) / 1000),
        "tags": list(row.get("tags") or [])[:8],
        "pipeline_tag": str(row.get("pipeline_tag") or row.get("pipelineTag") or ""),
        "library_name": str(row.get("library_name") or row.get("libraryName") or ""),
    }


async def _trending_repos(client: httpx.AsyncClient, kind: str, limit: int) -> list[dict[str, Any]]:
    endpoint = {"models": "/api/models", "spaces": "/api/spaces"}[kind]
    params = {
        "limit": limit,
        "sort": "trendingScore",
        "direction": -1,
        "full": "true",
    }
    response = await client.get(HF + endpoint, params=params)
    response.raise_for_status()
    rows = response.json()
    return [_repo_item(row, kind) for row in rows if isinstance(row, dict)][:limit]


async def _model_datasets(client: httpx.AsyncClient, model_query: str, limit: int = 3) -> list[dict[str, Any]]:
    params = {
        "limit": limit,
        "sort": "trendingScore",
        "direction": -1,
        "full": "true",
        "search": model_query,
    }
    response = await client.get(HF + "/api/datasets", params=params)
    response.raise_for_status()
    rows = response.json()
    return [_repo_item(row, "datasets") for row in rows if isinstance(row, dict)][:limit]


async def _papers(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    response = await client.get(HF + "/api/daily_papers")
    response.raise_for_status()
    rows = response.json()
    items: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        paper = row.get("paper") if isinstance(row.get("paper"), dict) else row
        published = paper.get("publishedAt") or paper.get("published_at") or row.get("publishedAt")
        paper_id = str(paper.get("id") or paper.get("paperId") or "").strip()
        title = str(paper.get("title") or paper_id or "Hugging Face Paper")
        summary = str(paper.get("summary") or paper.get("abstract") or "").strip()
        upvotes = int(row.get("upvotes") or paper.get("upvotes") or 0)
        items.append({
            "id": paper_id or title,
            "source": "Hugging Face",
            "category": "papers",
            "title_original": title,
            "title_ko": title,
            "summary_original": summary[:1600],
            "summary_ko": "",
            "developer_point": "",
            "author": "",
            "published_at": str(published or ""),
            "modified_at": str(published or ""),
            "url": f"{HF}/papers/{paper_id}" if paper_id else f"{HF}/papers",
            "likes": upvotes,
            "downloads": 0,
            "ranking_score": upvotes,
            "tags": [],
        })
        if len(items) >= 3:
            break
    return items


async def _blog(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    response = await client.get(HF + "/blog/feed.xml")
    response.raise_for_status()
    root = ET.fromstring(response.text)
    items: list[dict[str, Any]] = []
    for entry in root.findall(".//item"):
        title = (entry.findtext("title") or "").strip()
        link = (entry.findtext("link") or "").strip()
        pub = (entry.findtext("pubDate") or "").strip()
        description = re.sub(r"<[^>]+>", " ", (entry.findtext("description") or "")).strip()
        description = re.sub(r"\s+", " ", description)
        items.append({
            "id": link or title,
            "source": "Hugging Face",
            "category": "news",
            "title_original": title,
            "title_ko": title,
            "summary_original": description[:1600],
            "summary_ko": "",
            "developer_point": "",
            "author": "",
            "published_at": pub,
            "modified_at": pub,
            "url": link or f"{HF}/blog",
            "likes": 0,
            "downloads": 0,
            "ranking_score": 0,
            "tags": [],
        })
        if len(items) >= 3:
            break
    return items


def _dataset_model_query() -> tuple[str, str]:
    active = str(current_runtime_ollama_model() or "qwen3.5:4b").strip()
    lowered = active.lower()
    # THEANOVA learned model is built from qwen3.5, so dataset discovery must use the base family.
    if lowered.startswith("theanova-learn"):
        query = "qwen3.5"
    else:
        query = active.split(":", 1)[0].strip() or "qwen3.5"
    return active, query


async def collect_huggingface_trends() -> dict[str, Any]:
    now = datetime.now(SEOUL)
    start_date = now.date() - timedelta(days=6)
    active_model, dataset_query = _dataset_model_query()

    timeout = httpx.Timeout(15.0, connect=5.0)
    headers = {"User-Agent": "THEANOVA-AgentStudio/5.577", "Accept": "application/json,text/xml,*/*"}
    categories: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        collectors = {
            "models": lambda: _trending_repos(client, "models", 5),
            "papers": lambda: _papers(client),
            "news": lambda: _blog(client),
            "spaces": lambda: _trending_repos(client, "spaces", 8),
            "datasets": lambda: _model_datasets(client, dataset_query, 3),
        }
        for key, collector in collectors.items():
            try:
                items = await collector()
                categories[key] = {"status": "OK", "items": items, "message": ""}
            except Exception as exc:
                categories[key] = {"status": "ERROR", "items": [], "message": str(exc)}

    return {
        "provider": "Hugging Face",
        "collection_date": now.date().isoformat(),
        "period": {"from": start_date.isoformat(), "to": now.date().isoformat()},
        "updated_at": now.isoformat(),
        "active_model": active_model,
        "dataset_query": dataset_query,
        "cache": {"hit": False, "daily": True},
        **categories,
    }

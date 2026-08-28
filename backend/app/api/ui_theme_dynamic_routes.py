from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.models.entities import UITheme
from app.services.ui_theme_service import analyze_theme_from_url, build_rules, merge_theme_analyses

router = APIRouter(prefix="/ui-themes", tags=["UI Theme Dynamic Import"])


class DynamicThemeImageReference(BaseModel):
    file_name: str = ""
    reference_role: str = "default"
    tokens: dict = {}
    component_rules: dict = {}
    layout_rules: dict = {}
    preview_colors: list[str] = []


class DynamicThemeImportRequest(BaseModel):
    name: str = ""
    urls: list[str] = []
    images: list[DynamicThemeImageReference] = []
    scope: str = "GLOBAL"


def _image_analysis(item: DynamicThemeImageReference) -> dict:
    tokens = dict(item.tokens or {})
    components = dict(item.component_rules or {})
    layout = dict(item.layout_rules or {})
    if not components or not layout:
        inferred_components, inferred_layout = build_rules(tokens)
        if not components:
            components = inferred_components
        if not layout:
            layout = inferred_layout
    return {
        "tokens": tokens,
        "component_rules": components,
        "layout_rules": layout,
        "preview_colors": list(item.preview_colors or []),
        "source_type": "IMAGE",
        "source_label": item.file_name,
        "reference_role": item.reference_role or "default",
    }


@router.post("/import-dynamic")
async def import_ui_theme_dynamic(req: DynamicThemeImportRequest):
    name = str(req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Theme 이름을 입력하세요.")

    urls: list[str] = []
    for raw in req.urls or []:
        value = str(raw or "").strip()
        if value and value not in urls:
            urls.append(value)
    if len(urls) > 20:
        raise HTTPException(status_code=400, detail="웹사이트 URL은 한 번에 최대 20개까지 분석할 수 있습니다.")

    images = list(req.images or [])
    if len(images) > 20:
        raise HTTPException(status_code=400, detail="화면 캡처 이미지는 한 번에 최대 20개까지 분석할 수 있습니다.")
    if not urls and not images:
        raise HTTPException(status_code=400, detail="웹사이트 URL 또는 화면 캡처 이미지를 하나 이상 추가하세요.")

    analyses: list[dict] = []
    warnings: list[str] = []
    for index, url in enumerate(urls, start=1):
        try:
            analyses.append(await analyze_theme_from_url(url))
        except Exception as exc:
            warnings.append(f"URL {index} 분석 실패: {url} · {str(exc) or type(exc).__name__}")

    for image in images:
        if image.tokens:
            analyses.append(_image_analysis(image))

    if not analyses:
        raise HTTPException(status_code=422, detail="추가한 참고 자료를 분석하지 못했습니다. " + " | ".join(warnings[:5]))

    merged = merge_theme_analyses(analyses)
    tokens = dict(merged.get("tokens") or {})
    component_rules = dict(merged.get("component_rules") or {})
    layout_rules = dict(merged.get("layout_rules") or {})
    preview_colors = list(merged.get("preview_colors") or [])
    if not component_rules or not layout_rules:
        inferred_components, inferred_layout = build_rules(tokens)
        component_rules = component_rules or inferred_components
        layout_rules = layout_rules or inferred_layout

    source_type = "COMBINED" if urls and images else ("URL" if urls else "IMAGE")
    source_parts = [*urls, *[str(item.file_name or "").strip() for item in images if str(item.file_name or "").strip()]]
    now = datetime.utcnow()
    row = UITheme(
        name=name,
        theme_type="IMPORTED",
        source_type=source_type,
        source_url="\n".join(urls),
        source_label=" · ".join(source_parts)[:1000],
        scope=str(req.scope or "GLOBAL").strip().upper() or "GLOBAL",
        tokens=tokens,
        component_rules=component_rules,
        layout_rules=layout_rules,
        preview_colors=preview_colors,
        created_at=now,
        updated_at=now,
    )
    async with SessionLocal() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)

    return {
        "ok": True,
        "theme": {
            "id": row.id,
            "name": row.name,
            "source_type": row.source_type,
            "source_url": row.source_url,
            "source_label": row.source_label,
            "scope": row.scope,
            "tokens": row.tokens or {},
            "component_rules": row.component_rules or {},
            "layout_rules": row.layout_rules or {},
            "preview_colors": row.preview_colors or [],
        },
        "url_count": len(urls),
        "image_count": len(images),
        "warnings": warnings,
        "message": f"URL {len(urls)}개 · 이미지 {len(images)}개 참고 자료를 통합 분석해 Theme을 저장했습니다.",
    }

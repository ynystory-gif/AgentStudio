from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.entities import MemoryRecord
from app.services.embedding_service import get_embedding_model
from app.services.memory_organizer import organize_memory

async def add_memory(
    content: str,
    memory_type: str = "PROJECT",
    key: str = "",
    project_id: int | None = None,
    metadata: dict | None = None,
):
    # Memory 정리는 Ollama가 담당
    try:
        organized_content = await organize_memory(content)
    except Exception:
        organized_content = content

    embedding = None
    try:
        embedding = await get_embedding_model().aembed_query(organized_content)
    except Exception:
        # Embedding 서비스가 꺼져 있어도 일반 Memory 저장은 유지
        embedding = None

    async with SessionLocal() as db:
        row = MemoryRecord(
            project_id=project_id,
            memory_type=memory_type,
            key=key or organized_content[:80],
            content=organized_content,
            metadata_json=metadata or {},
            embedding=embedding,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row.id

async def search_memory(
    query: str,
    project_id: int | None = None,
    memory_type: str | None = None,
    limit: int = 8,
):
    vector = await get_embedding_model().aembed_query(query)

    async with SessionLocal() as db:
        stmt = select(
            MemoryRecord,
            MemoryRecord.embedding.cosine_distance(vector).label("distance")
        ).where(MemoryRecord.embedding.is_not(None))

        if project_id is not None:
            stmt = stmt.where(MemoryRecord.project_id == project_id)
        if memory_type:
            stmt = stmt.where(MemoryRecord.memory_type == memory_type)

        stmt = stmt.order_by("distance").limit(limit)
        rows = (await db.execute(stmt)).all()
        return [
            {
                "id": rec.id,
                "memory_type": rec.memory_type,
                "key": rec.key,
                "content": rec.content,
                "metadata": rec.metadata_json,
                "distance": float(distance),
            }
            for rec, distance in rows
        ]

# Import additive AgentStudio ORM models that live outside entities.py so
# Base.metadata.create_all() registers them on local PostgreSQL and Supabase runtime DBs.
from app.models.learning_entities import (  # noqa: F401
    LlmLearningDataset,
    LlmLearningPcApplication,
    LlmMisjudgmentCase,
)
from app.models.auth_entities import (  # noqa: F401
    AgentStudioAuthSession,
    AgentStudioMember,
    AgentStudioMemberPc,
)

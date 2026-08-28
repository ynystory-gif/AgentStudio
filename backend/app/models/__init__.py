# Import additive AgentStudio ORM models that live outside entities.py so
# Base.metadata.create_all() registers them on local PostgreSQL and Supabase runtime DBs.
from app.models.learning_entities import LlmLearningDataset, LlmMisjudgmentCase  # noqa: F401

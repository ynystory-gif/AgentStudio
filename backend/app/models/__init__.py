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

from app.models.rag_entities import (  # noqa: F401
    RagStudioSetting,
    RagCollection,
    RagSource,
    RagCollectionSource,
    RagDocument,
    RagChunk,
    RagEmbedding,
    RagIndexJob,
    RagRetrievalSetting,
    RagSearchLog,
    RagIntelligenceSetting,
    RagRecommendationRun,
    RagAgentTool,
    RagWorkflowBinding,
    RagAgentTestLog,
    RagSourceOperationSetting,
    RagSyncJob,
    RagDocumentVersion,
    RagDocumentSecurity,
    RagAccessRule,
    RagSearchAuditLog,
    RagEvaluationCase,
    RagEvaluationRun,
)

from app.models.account_setting_entities import (  # noqa: F401
    AccountDatabaseProfile,
    AccountSettingProfile,
    AccountProjectSetting,
    ProjectSettingHistory,
)

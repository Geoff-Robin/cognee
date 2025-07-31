from typing import Any, Optional

from uuid import NAMESPACE_OID, uuid5, UUID
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.llm.get_llm_client import get_llm_client
from cognee.modules.engine.models import NodeSet
from cognee.shared.logging_utils import get_logger
from cognee.modules.retrieval.base_feedback import BaseFeedback
from cognee.modules.retrieval.utils.models import CogneeUserFeedback
from cognee.modules.retrieval.utils.models import UserFeedbackEvaluation
from cognee.tasks.storage import add_data_points

logger = get_logger("CompletionRetriever")


class UserQAFeedback(BaseFeedback):
    """
    Interface for handling user feedback queries.

    Public methods:
    - get_context(query: str) -> str
    - get_completion(query: str, context: Optional[Any] = None) -> Any
    """

    def __init__(self, last_k: Optional[int] = 5):
        """Initialize retriever with optional custom prompt paths."""
        self.last_k = last_k

    async def add_feedback(self, feedback_text: str) -> Any:
        llm_client = get_llm_client()
        feedback_sentiment = await llm_client.acreate_structured_output(
            feedback_text,
            "You are a sentiment analysis assistant. For each piece of user feedback you receive, return exactly one of: Positive, Negative, or Neutral classification",
            UserFeedbackEvaluation,
        )

        graph_engine = await get_graph_engine()
        last_interaction_ids = await graph_engine.get_last_user_interaction_ids(limit=self.last_k)

        nodeset_name = "UserQAFeedbacks"
        feedbacks_node_set = NodeSet(id=uuid5(NAMESPACE_OID, name=nodeset_name), name=nodeset_name)
        feedback_id = uuid5(NAMESPACE_OID, name=feedback_text)

        cognee_user_feedback = CogneeUserFeedback(
            id=feedback_id,
            feedback=feedback_text,
            sentiment=feedback_sentiment.evaluation.value,
            belongs_to_set=feedbacks_node_set,
        )

        await add_data_points(data_points=[cognee_user_feedback])

        relationships = []
        relationship_name = "gives_feedback_to"

        for interaction_id in last_interaction_ids:
            target_id_1 = feedback_id
            target_id_2 = UUID(interaction_id)

            if target_id_1 and target_id_2:
                relationships.append(
                    (
                        target_id_1,
                        target_id_2,
                        relationship_name,
                        {
                            "relationship_name": relationship_name,
                            "source_node_id": target_id_1,
                            "target_node_id": target_id_2,
                            "ontology_valid": False,
                        },
                    )
                )

        if len(relationships) > 0:
            graph_engine = await get_graph_engine()
            await graph_engine.add_edges(relationships)

        return [feedback_text]

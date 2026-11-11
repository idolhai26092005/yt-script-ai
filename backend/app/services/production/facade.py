from app.services.production.idea_suggester import IdeaSuggester
from app.services.production.topic_suggester import TopicSuggester
from app.services.production.producer import ScriptProducer

from app.core.repository import ScreenplayRepository, SQLAlchemyScreenplayRepository

class ProductionService(IdeaSuggester, TopicSuggester, ScriptProducer):
    def __init__(
        self,
        api_key: str,
        groq_api_key: str | None = None,
        db = None,
        api_key_id: int | None = None,
        repo: ScreenplayRepository | None = None
    ):
        super().__init__(api_key, groq_api_key, db, api_key_id)
        self._repo = repo or SQLAlchemyScreenplayRepository(db_session=db)

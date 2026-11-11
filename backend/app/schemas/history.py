import datetime
from typing import Literal

from pydantic import BaseModel, Field


HistoryFilter = Literal["all", "single", "series"]
HistoryItemKind = Literal["single", "series"]


# History totals guard: the unified archive renders filter badges without
# issuing extra count requests or leaking unrelated API-key ownership.
class HistoryTotals(BaseModel):
    all: int
    single: int
    series: int


# History row guard: the archive exposes only lightweight navigation metadata,
# never raw script outputs, prompt artifacts, series bibles, or season maps.
class HistoryItem(BaseModel):
    kind: HistoryItemKind
    id: int
    title: str
    status: str
    updated_at: datetime.datetime
    created_at: datetime.datetime
    preview: str
    meta: str


# History page guard: desktop numbered pagination and mobile load-more share
# the same stable server contract.
class HistoryPageResponse(BaseModel):
    items: list[HistoryItem] = Field(default_factory=list)
    total: int
    totals: HistoryTotals
    skip: int
    limit: int

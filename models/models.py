from enum import Enum
from typing import Dict, List

from pydantic import RootModel, BaseModel


class MatchType(Enum):
    LIKE = "like"
    MATCH = "match"
    CHATS = "chats"
    BLOCK = "block"


class Events(RootModel):
    root: List[Dict[str, List]]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class EventTimeStamp(BaseModel):
    timestamp: str


class Match(EventTimeStamp):
    type: str = MatchType.MATCH.value


class Like(EventTimeStamp):
    comment: str | None = None
    type: str = MatchType.LIKE.value


class Chats(EventTimeStamp):
    body: str | None = None
    type: str = MatchType.CHATS.value


class Block(EventTimeStamp):
    block_type: str
    type: str = MatchType.BLOCK.value


class BaseInfo(BaseModel):
    user_id: str | None = None
    match_count: int | None = None
    like_count: int | None = None
    total_chat_count: int | None = None

from datetime import datetime
from enum import Enum
from typing import Dict, List

from pydantic import RootModel, BaseModel
from sqlmodel import Field, SQLModel


class MatchType(Enum):
    LIKE = "like"
    MATCH = "match"
    CHATS = "chats"
    BLOCK = "block"


class Matches(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    type: int = Field(index=True)
    timestamp: datetime


class Likes(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    type: int = Field(index=True)
    timestamp: datetime


class Events(RootModel):
    root: List[Dict[str, List]]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class Token(BaseModel):
    id_token: str


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


class LikesReceivedPerDayForGivenRange(BaseModel):
    date_range: dict | None = None
    likes: float | None = None


class HingeStatsLikes(BaseModel):
    total_like_count: int | None = None
    they_liked_me_count: int | None = None
    i_liked_them_count: int | None = None
    likes_received_per_day_for_given_range: LikesReceivedPerDayForGivenRange | None = None


class HingeStats(BaseModel):
    match_count: int | None = None
    likes: HingeStatsLikes | None = None
    event_date_range: dict | None = None
    conversion_percentage: dict | None = None

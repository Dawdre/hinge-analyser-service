from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import RootModel, BaseModel
from sqlmodel import Field, SQLModel


class MatchType(Enum):
    LIKE = "like"
    MATCH = "match"
    CHATS = "chats"
    BLOCK = "block"


class WhoLiked(Enum):
    THEM = "Them"
    YOU = "You"


class Person(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    matched: Optional[bool] = None
    who_liked: str | None = None
    what_you_liked: Optional[str] = None
    photo_url: Optional[str] = None
    like_timestamp: Optional[datetime] = None
    match_timestamp: Optional[datetime] = None
    we_met: Optional[bool] = None
    blocked: Optional[str] = None
    # name_found: Optional[bool] = None
    # ghosted: bool | None = None


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


class MatchesPerDayForGivenRange(BaseModel):
    date_range: dict | None = None
    matches: float | None = None


class HingeStatsMatches(BaseModel):
    total_match_count: int | None = None
    they_liked_matched_count: int | None = None
    i_liked_matched_count: int | None = None
    matches_per_day_for_given_range: MatchesPerDayForGivenRange | None = None


class LikesReceivedPerDayForGivenRange(BaseModel):
    date_range: dict | None = None
    likes: float | None = None


class HingeStatsLikes(BaseModel):
    description: str | None = None
    total_like_count: int | None = None
    likes_received_per_day_for_given_range: LikesReceivedPerDayForGivenRange | None = None


class HingeStats(BaseModel):
    matches: HingeStatsMatches | None = None
    likes: HingeStatsLikes | None = None
    event_date_range: dict | None = None
    conversion_percentage: dict | None = None

import json
from datetime import datetime
from enum import Enum
from typing import List, Optional, Any

from pydantic import BaseModel, field_validator
from sqlmodel import Field, SQLModel


class MatchType(Enum):
    LIKE = "like"
    MATCH = "match"
    CHATS = "chats"
    BLOCK = "block"


class WhoLiked(Enum):
    THEM = "Them"
    YOU = "You"


class UserMetaData(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    created_timestamp: Optional[datetime] = Field(None)
    uuid: Optional[str] = Field()
    login_timestamp: Optional[datetime] = Field(None)
    start_range_timestamp: Optional[datetime] = None
    end_range_timestamp: Optional[datetime] = None


class Person(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(index=True)
    matched: Optional[bool] = Field(None)
    who_liked: Optional[str] = None
    what_you_liked_photo: Optional[str] = None
    what_you_liked_prompt: Optional[str] = None
    what_you_liked_video: Optional[str] = None
    like_timestamp: Optional[datetime] = None
    match_timestamp: Optional[datetime] = None
    we_met: Optional[bool] = None
    blocked: Optional[str] = None
    has_media: Optional[bool] = None
    thumbnail: Optional[str] = Field()
    # name_found: Optional[str] = None
    # ghosted: bool | None = None


class PersonTaskResult(BaseModel):
    status: str
    result: str
    message: str
    progress: float


class Matches(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    type: int = Field(index=True)
    timestamp: Optional[datetime] = Field(None)


class Likes(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    type: int = Field(index=True)
    timestamp: datetime


class FlexibleModel(BaseModel):
    """
    A recursive model that can parse nested JSON structures of unknown depth
    """
    data: Any = Field(default_factory=dict)

    @field_validator("data", mode="before")
    def parse_nested_json(cls, value):
        return cls.parse_nested(value)

    @staticmethod
    def parse_nested(value):
        def recursive_parse(item):
            if isinstance(item, str):
                try:
                    return recursive_parse(json.loads(item))
                except (json.JSONDecodeError, TypeError):
                    return item
            elif isinstance(item, dict):
                return {k: recursive_parse(v) for k, v in item.items()}
            elif isinstance(item, list):
                return [recursive_parse(i) for i in item]
            return item

        return recursive_parse(value)


class Events(BaseModel):
    root: List[FlexibleModel]


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

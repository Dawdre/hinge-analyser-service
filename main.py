from enum import Enum
from typing import List, Dict

from fastapi import FastAPI
from pydantic import BaseModel, RootModel
from starlette.middleware.cors import CORSMiddleware


class MatchType(Enum):
    LIKE = "like"
    MATCH = "match"
    CHATS = "chats"
    BLOCK = "block"


class Like(BaseModel):
    timestamp: str
    comment: str
    type: str = MatchType.LIKE.value


class Match(BaseModel):
    timestamp: str
    type: str = MatchType.MATCH.value


class Block(BaseModel):
    block_type: str
    timestamp: str
    type: str = MatchType.BLOCK.value


class Chats(BaseModel):
    body: str
    timestamp: str
    type: str = MatchType.CHATS.value


class Events(RootModel):
    root: List[Dict[str, List[Like | Match | Chats | Block]]]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


all_events = Events.model_validate([
    {
        "like": [{"timestamp": "2020-12-12", "comment": "test"}]
    },
    {
        "match": [{"timestamp": "2020-12-12"}]
    },
    {
        "chats": [{"body": "test", "timestamp": "2020-12-12"}]
    },
    {
        "block": [{"block_type": "test", "timestamp": "2020-12-12"}]
    },
])
print(all_events)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/matches")
async def read_matches():
    return all_events

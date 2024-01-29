from enum import Enum
from typing import List, Dict, Annotated

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, RootModel
from starlette.middleware.cors import CORSMiddleware

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


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


app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def fake_password(password: str):
    return "fakehashed" + password


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def fake_decode_token(token):
    user = get_user(fake_users_db, token)
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user_dict = fake_users_db.get(form_data.username)
    if not user_dict:
        raise HTTPException(
            status_code=400,
            detail="Incorrect username and password"
        )
    user = UserInDB(**user_dict)
    hashed_password = fake_password(form_data.password)
    if not hashed_password == user.hashed_password:
        raise HTTPException(
            status_code=400,
            detail="Incorrect username and password"
        )

    return {"access_token": user.username, "token_type": "bearer"}


@app.get("/users/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user


file = open("matches.json", "r")
all_events = Events.model_validate_json(file.read())


@app.get("/api/v1/matches/{matches_id}")
async def read_matches(matches_id: int):
    return {"matches_id": matches_id, "matches": all_events}

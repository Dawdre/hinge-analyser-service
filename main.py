import json
import math
import os
from typing import List, Annotated

from fastapi import FastAPI, Depends, HTTPException, status, Response, UploadFile
from fastapi.security import OAuth2PasswordBearer
from google.auth.transport import requests
from google.oauth2 import id_token
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from models.models import Events, Like, Match, BaseInfo, Chats

GOOGLE_CLIENT_ID = "551511732871-ktjlpdoukaemppa8ph2p12uofk23urs3.apps.googleusercontent.com"

SECRET_KEY = "05344ffa81ac1adad640701221700b92a48f43a7984b4d40f97ca64a29021c14"
ALGORITHM = "HS256"


class Token(BaseModel):
    id_token: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173',
                   'https://localhost:5173', 'https://127.0.0.1:5173'],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],

)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("user_id")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return payload


@app.post("/token")
async def login_for_access_token(token: Token, response: Response):
    try:
        idinfo = id_token.verify_oauth2_token(token.id_token, requests.Request(), GOOGLE_CLIENT_ID)

        user_details = {
            "user_id": idinfo["sub"],
            "email": idinfo["email"],
            "name": idinfo["given_name"],
            "picture": idinfo["picture"]
        }
        token = jwt.encode(user_details, SECRET_KEY, algorithm=ALGORITHM)
        return {"status": "success", "token": token}
    except ValueError as error:
        # Invalid ID token
        return {"status": "error", "message": str(error)}


local_file = open("matches.json")

all_events = Events(json.load(local_file))

base_info = BaseInfo()
all_matches = []
matches_i_liked = []
matches_they_liked = []
all_likes = []
all_chats = []

for event in all_events.root:

    if event.get('match') and event.get("like"):
        # I liked them and got a match
        matches_i_liked.append(event)
    elif event.get('match'):
        # They liked me and matched
        # if not event.get('chats'):
        #     print(event)
        matches_they_liked.append(event)

    for key, item in event.items():
        if key == "match":
            match = Match(**item[0])
            all_matches.append(match)
            base_info.match_count = len(all_matches)
        elif key == "like":
            like = Like(**item[0])
            all_likes.append(item)
            base_info.like_count = len(all_likes)
        elif key == "chats":
            chats = [Chats(**x) for x in item]
            if len(chats) > 1:
                all_chats.append(chats)
            base_info.total_chat_count = len(all_chats)


def per_day(data: List):
    return round((len(data) / 4) / 365, 2)


def per_month(data: List):
    return round((len(data) / 4) / 12, 2)


print("From Oct 19 to Jan 23")
print("Matches: {}".format(len(all_matches)), "Likes: {}".format(len(all_likes)),
      "Percentage: {}%".format(math.ceil(len(all_matches) / len(all_likes) * 100)))
print("Total conversations: {}".format(base_info.total_chat_count))
print("Likes per day: {}".format(per_day(all_likes)))
print("Matches per day: {}".format(per_day(all_matches)))
print("Matches where they liked me: {}".format(len(matches_they_liked)))
print("Matches where I liked them: {}".format(len(matches_i_liked)))

GetUserDep = Annotated[dict, Depends(get_current_user)]


@app.post("/api/v1/upload")
async def create_upload_file(file: UploadFile, user_data: GetUserDep):
    path = './uploads'

    # check whether directory already exists
    if not os.path.exists(path):
        os.mkdir(path)
        print("Folder %s created!" % path)
    else:
        print("Folder %s already exists" % path)

    file_dir_name = "{}/{}".format(path, file.filename)
    f = open(file_dir_name, "wb")
    content = await file.read(file.size)
    f.write(content)
    f.close()
    return {
        "file_size": file.size,
        "file_name": file.filename
    }


@app.get("/api/v1/matches")
async def read_matches(user_data: GetUserDep):
    return all_matches


@app.get("/api/v1/likes")
async def read_likes(user_data: GetUserDep):
    return all_likes


@app.get("/api/v1/base")
async def read_base(user_data: GetUserDep):
    return user_data

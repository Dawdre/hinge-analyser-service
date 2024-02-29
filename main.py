import json
import math
import os
from pathlib import Path
from typing import List, Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer
from google.auth.transport import requests
from google.oauth2 import id_token
from jose import jwt, JWTError
from sqlmodel import Session, select
from starlette.middleware.cors import CORSMiddleware

from db.session import create_db_and_tables, get_session
from models.models import Events, HingeStats, Matches, Likes, Token, HingeStatsLikes
from utils.dates import parse_timestamp, get_date_ranges

env_path = Path(".") / ".env"
load_dotenv(env_path)

local_file = open("matches-dawd2.json")
all_events = Events(json.load(local_file))
upload_date_range = get_date_ranges(all_events)

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
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")])
        username: str = payload.get("user_id")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return payload


def get_like_content(content: List):
    like_stuff = json.loads(content[0]["content"])[0]

    if like_stuff.get("photo") and like_stuff.get("photo").get("url"):
        return 1
    elif like_stuff.get("prompt") and like_stuff.get("prompt").get("question"):
        return 2
    elif like_stuff.get("video") and like_stuff.get("video").get("url"):
        return 3

    return 0


def save_hinge_data(events: Events, user_id: str, session: Session):
    for evt in events.root:
        if evt.get('match') and evt.get("like"):
            # I liked them and got a match
            event_timestamp = parse_timestamp(evt.get("match")[0])
            db_match = Matches(user_id=user_id, type=1, timestamp=event_timestamp)
            session.add(db_match)
        elif evt.get('match'):
            # They liked me and matched
            event_timestamp = parse_timestamp(evt.get("match")[0])
            db_match = Matches(user_id=user_id, type=2, timestamp=event_timestamp)
            session.add(db_match)
        elif evt.get("like"):
            # All likes
            event_timestamp = parse_timestamp(evt.get("like")[0])
            db_like = Likes(user_id=user_id, type=get_like_content(evt.get("like")), timestamp=event_timestamp)
            session.add(db_like)

    session.commit()


GetUserDep = Annotated[dict, Depends(get_current_user)]


@app.on_event("startup")
def on_startup(session: Session = Depends(get_session)):
    create_db_and_tables()


@app.post("/token")
async def login_for_access_token(token: Token, response: Response):
    try:
        id_info = id_token.verify_oauth2_token(
            token.id_token,
            requests.Request(),
            os.getenv("GOOGLE_CLIENT_ID")
        )

        user_details = {
            "user_id": id_info["sub"],
            "email": id_info["email"],
            "name": id_info["given_name"],
            "picture": id_info["picture"]
        }
        token = jwt.encode(user_details, os.getenv("SECRET_KEY"), algorithm=os.getenv("ALGORITHM"))
        return {"status": "success", "token": token}
    except ValueError as error:
        # Invalid ID token
        return {"status": "error", "message": str(error)}


@app.post("/api/v1/upload")
async def create_upload_file(file: UploadFile, user_data: GetUserDep, session: Session = Depends(get_session)):
    content = await file.read(file.size)

    try:
        content_json = jsonable_encoder(content)
    except ValueError:
        raise HTTPException(status_code=422,
                            detail="Unable to process file contents. Upload a valid 'matches' JSON file.")

    events = Events(json.loads(content_json))
    save_hinge_data(events, user_data.get("email"), session)

    return {
        "file_size": file.size,
        "file_name": file.filename,
        "hinge_date_range": get_date_ranges(events)
    }


@app.get("/api/v1/matches", response_model=List[Matches])
async def read_matches(user_data: GetUserDep, session: Session = Depends(get_session)):
    statement = (select(Matches)
                 .where(Matches.user_id == user_data.get("email"))
                 .order_by(Matches.timestamp))
    matches = session.exec(statement)
    if not matches:
        raise HTTPException(status_code=404, detail="Matches not found for that user")
    return matches


@app.get("/api/v1/likes", response_model=List[Likes])
async def read_likes(user_data: GetUserDep, session: Session = Depends(get_session)):
    statement = (select(Likes)
                 .where(Likes.user_id == user_data.get("email"))
                 .order_by(Likes.timestamp))
    likes = session.exec(statement)
    if not likes:
        raise HTTPException(status_code=404, detail="Likes not found for that user")
    return likes


@app.get("/api/v1/stats", response_model=HingeStats)
async def read_stats(user_data: GetUserDep, session: Session = Depends(get_session)):
    # statements
    matches_statement = (select(Matches)
                         .where(Matches.user_id == user_data.get("email"))
                         .order_by(Matches.timestamp))
    likes_statement = (select(Likes)
                       .where(Likes.user_id == user_data.get("email"))
                       .order_by(Likes.timestamp))

    they_liked_me_statement = (select(Likes)
                               .where(Likes.user_id == user_data.get("email"))
                               .where(Likes.type == 2)
                               .order_by(Likes.timestamp))
    i_liked_them_statement = (select(Likes)
                              .where(Likes.user_id == user_data.get("email"))
                              .where(Likes.type == 1)
                              .order_by(Likes.timestamp))

    # execute
    matches = len(session.exec(matches_statement).all())
    likes = len(session.exec(likes_statement).all())
    they_liked_me_likes = session.exec(they_liked_me_statement).all()
    i_liked_them_likes = session.exec(i_liked_them_statement).all()

    like_days_delta = (they_liked_me_likes[-1].timestamp - they_liked_me_likes[0].timestamp).days
    likes_per_day = {
        "date_range": upload_date_range,
        "likes": round(len(they_liked_me_likes) / like_days_delta, 2)
    }
    likes_stats = HingeStatsLikes(
        total_like_count=likes,
        they_liked_me_count=len(they_liked_me_likes),
        i_liked_them_count=len(i_liked_them_likes),
        likes_received_per_day_for_given_range=likes_per_day
    )

    stats = HingeStats(
        match_count=matches,
        likes=likes_stats,
        event_date_range=upload_date_range,
        conversion_percentage={
            "percentage": math.ceil((matches / likes) * 100),
            "description": "How many matches converted from total likes"
        }
    )

    return stats


@app.get("/api/v1/base")
async def read_base(user_data: GetUserDep):
    return user_data

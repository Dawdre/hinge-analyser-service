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
from db.statements import check_existing_and_delete
from models.models import Events, HingeStats, Matches, Likes, Token, HingeStatsLikes, HingeStatsMatches, Person, \
    WhoLiked
from utils.dates import parse_timestamp, get_date_ranges, calc_per_day

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


def save_person_data(events: Events, session: Session):
    for event in events.root:
        db_person = Person()
        if (event.get("match")
                and event.get("like")
                and event.get("chats")
                and event.get("we_met")):

            db_person.matched = True
            db_person.who_liked = WhoLiked.YOU.value
            db_person.match_timestamp = parse_timestamp(event.get("match")[0])
            db_person.like_timestamp = parse_timestamp(event.get("like")[0])
            # https://flairnlp.github.io/docs/tutorial-basics/tagging-entities
            # db_person.blocked = event.get("block")[0]["block_type"]

            if event.get("we_met")[0]["did_meet_subject"] == "Yes":
                db_person.we_met = True
            else:
                db_person.we_met = False
        elif event.get("match") and event.get("like"):
            db_person.matched = True
            db_person.who_liked = WhoLiked.YOU.value
            db_person.match_timestamp = parse_timestamp(event.get("match")[0])
            db_person.like_timestamp = parse_timestamp(event.get("like")[0])

            if get_like_content(event.get("like")) == 1:
                db_person.what_you_liked = "photo"
                like_stuff = json.loads(event.get("like")[0]["content"])[0]
                db_person.photo_url = like_stuff.get("photo").get("url")
            elif get_like_content(event.get("like")) == 2:
                db_person.what_you_liked = "prompt"
            else:
                db_person.what_you_liked = "video"

        elif event.get("match") and event.get("chats"):
            db_person.matched = True
            db_person.who_liked = WhoLiked.THEM.value
            db_person.match_timestamp = parse_timestamp(event.get("match")[0])

        elif event.get("like"):
            db_person.matched = False
            db_person.who_liked = WhoLiked.YOU.value
            db_person.like_timestamp = parse_timestamp(event.get("like")[0])

            if get_like_content(event.get("like")) == 1:
                db_person.what_you_liked = "photo"
                like_stuff = json.loads(event.get("like")[0]["content"])[0]
                db_person.photo_url = like_stuff.get("photo").get("url")
            elif get_like_content(event.get("like")) == 2:
                db_person.what_you_liked = "prompt"
            else:
                db_person.what_you_liked = "video"

        elif event.get("match") or event.get("block"):
            continue
            # db_person.matched = True
            # db_person.match_timestamp = parse_timestamp(event.get("match")[0])
            # db_person.who_liked = WhoLiked.THEM.value

        session.add(db_person)

    session.commit()


def save_hinge_data(events: Events, user_id: str, session: Session):
    check_existing_and_delete(user_id, session)

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
    save_person_data(events, session)

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

    they_liked_me_statement = (select(Matches)
                               .where(Matches.user_id == user_data.get("email"))
                               .where(Matches.type == 2)
                               .order_by(Matches.timestamp))
    i_liked_them_statement = (select(Matches)
                              .where(Matches.user_id == user_data.get("email"))
                              .where(Matches.type == 1)
                              .order_by(Matches.timestamp))

    # execute
    matches = session.exec(matches_statement).all()
    likes = session.exec(likes_statement).all()
    they_liked_me = session.exec(they_liked_me_statement).all()
    i_liked_them = session.exec(i_liked_them_statement).all()

    matches_per_day = {
        "date_range": upload_date_range,
        "matches": calc_per_day(matches)
    }
    matches_stats = HingeStatsMatches(
        total_match_count=len(matches),
        they_liked_matched_count=len(they_liked_me),
        i_liked_matched_count=len(i_liked_them),
        matches_per_day_for_given_range=matches_per_day
    )

    likes_per_day = {
        "date_range": upload_date_range,
        "likes": calc_per_day(they_liked_me)
    }
    likes_stats = HingeStatsLikes(
        description="Likes given and received. "
                    "There is no way of knowing whether "
                    "you liked someone or they liked you, unless there was a match involved.",
        total_like_count=len(likes),
        likes_received_per_day_for_given_range=likes_per_day
    )

    stats = HingeStats(
        matches=matches_stats,
        likes=likes_stats,
        event_date_range=upload_date_range,
        conversion_percentage={
            "percentage": math.ceil((len(matches) / len(likes)) * 100),
            "description": "How many matches converted from total likes"
        }
    )

    return stats


@app.get("/api/v1/base")
async def read_base(user_data: GetUserDep):
    return user_data

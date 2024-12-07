import base64
import io
import json
import math
import os
from pathlib import Path
from typing import List, Annotated

import httpx
import uvicorn
from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer
from google.auth.transport import requests
from google.oauth2 import id_token
from jose import jwt, JWTError
from sqlmodel import Session, select, delete, desc
from starlette.middleware.cors import CORSMiddleware

from db.session import create_db_and_tables, get_session
from db.writes.matches_likes import save_hinge_data
from db.writes.person import save_person_data
from images.thumbnails import resize_with_aspect_ratio
from models.image import ImageUrls, ThumbNailResponse
from models.models import Events, HingeStats, Matches, Likes, Token, HingeStatsLikes, HingeStatsMatches, Person, \
    UserMetaData, MatchesPerDayForGivenRange, LikesReceivedPerDayForGivenRange
from utils.dates import get_date_ranges, calc_per_day

# load_or_create_ner()

# load env variables
env_path = Path(".") / ".env"
load_dotenv(env_path)

# TODO: remove this
local_file = open("matches-dawd2.json")
all_events = Events(json.load(local_file))
upload_date_range = get_date_ranges(all_events)

# for evt in all_events.root:
#     if (evt.get("match")
#             and evt.get("like")
#             and evt.get("chats")):
#         for chat in evt.get("chats"):
#             if chat.get("body"):
#                 doc1 = nlp(chat.get("body"))
#                 for blah in doc1.ents:
#                     if blah.label_ == "PERSON":
#                         print(blah.text)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173',
                   'https://localhost:5173', 'https://127.0.0.1:5173'],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT"],
    allow_headers=["*"],

)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Verifies the given Bearer token and returns the associated user_id.

    :param token: The Bearer token to verify.
    :return: The user_id associated with the given token, or raises an HTTPException if the token is invalid.
    """
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


@app.delete("/api/v1/delete-all")
async def delete_table_data(user_data: GetUserDep, session: Session = Depends(get_session)):
    # dev endpoint to delete all table data
    session.exec(delete(Likes))
    session.exec(delete(Person))
    session.exec(delete(Matches))
    session.exec(delete(UserMetaData))

    session.commit()


@app.post("/api/v1/generate-thumbnails")
async def generate_thumbnails(image_urls: ImageUrls):
    thumbnails = []

    def make_base64(source, mime_type):
        return f"data:{mime_type};base64,{source}"

    async with httpx.AsyncClient() as client:
        for url in image_urls.urls:
            try:
                response = await client.get(url)
                response.raise_for_status()

                image = Image.open(io.BytesIO(response.content))

                thumbnail = image.copy()
                thumbnail = resize_with_aspect_ratio(thumbnail)

                thumbnail_io = io.BytesIO()
                thumbnail.save(thumbnail_io, format=image.format)
                thumbnail_io.seek(0)

                thumbnails.append({
                    "original_url": url,
                    "base64": make_base64(
                        base64.b64encode(thumbnail_io.read()).decode('utf-8'),
                        f"image/{image.format.lower()}"
                    ),
                    "size": thumbnail.size
                })
            except httpx.HTTPError as e:
                thumbnails.append({
                    "original_url": url,
                    "image_error": str(e)
                })

    return thumbnails


@app.post("/api/v1/upload")
async def create_upload_file(file: UploadFile, user_data: GetUserDep, session: Session = Depends(get_session)):
    content = await file.read(file.size)

    try:
        content_json = jsonable_encoder(content)
    except ValueError:
        raise HTTPException(status_code=422,
                            detail="Unable to process file contents. Upload a valid 'matches' JSON file.")

    events = Events(json.loads(content_json))

    date_range = get_date_ranges(events)
    db_user_metadata = UserMetaData(user_id=user_data.get("email"),
                                    start_range_timestamp=date_range["start_date"],
                                    end_range_timestamp=date_range["end_date"])
    session.add(db_user_metadata)
    session.commit()

    save_hinge_data(events, user_data.get("email"), session)
    save_person_data(events, user_data.get("email"), session)

    return {
        "file_size": file.size,
        "file_name": file.filename,
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


@app.get("/api/v1/persons")
async def read_person(page: int, user_data: GetUserDep, session: Session = Depends(get_session)):
    # SELECT * FROM person
    # WHERE like_timestamp IS NOT NULL
    # OR match_timestamp IS NOT NULL
    # ORDER BY has_media DESC, like_timestamp DESC, match_timestamp DESC;
    statement = (
        select(Person)
        .where(Person.user_id == user_data.get("email"))
        .where(Person.like_timestamp is not None or Person.match_timestamp is not None)
        .order_by(desc(Person.has_media), desc(Person.like_timestamp), desc(Person.match_timestamp))
    )

    list_of_persons = list(session.exec(statement).all())

    # Pagination
    page_size = 10
    page_count = math.ceil(len(list_of_persons) / page_size)
    page = min(page, page_count)

    start_index = (page - 1) * page_size
    end_index = start_index + page_size

    list_of_persons = list_of_persons[start_index:end_index]

    # Go and get original image and generate thumbnails
    generate_thumbnails_response = await generate_thumbnails(
        ImageUrls(
            urls=[person.what_you_liked_photo for person in list_of_persons if person.what_you_liked_photo is not None])
    )

    # Add the generated thumbnails to the person object
    for person, thumb in zip(list_of_persons, generate_thumbnails_response):
        person.what_you_liked_photo = ThumbNailResponse(**thumb)

    if not list_of_persons:
        raise HTTPException(status_code=404, detail="Persons not found for that user")
    return {
        "persons": list_of_persons,
        "current_page": page,
        "page_count": page_count
    }


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

    matches_per_day = MatchesPerDayForGivenRange(
        date_range=upload_date_range,
        matches=calc_per_day(matches)
    )
    matches_stats = HingeStatsMatches(
        total_match_count=len(matches),
        they_liked_matched_count=len(they_liked_me),
        i_liked_matched_count=len(i_liked_them),
        matches_per_day_for_given_range=matches_per_day
    )

    likes_per_day = LikesReceivedPerDayForGivenRange(
        date_range=upload_date_range,
        likes=calc_per_day(likes)
    )
    likes_stats = HingeStatsLikes(
        description="Every like I have sent",
        total_like_count=len(likes),
        likes_received_per_day_for_given_range=likes_per_day
    )

    stats = HingeStats(
        matches=matches_stats,
        likes=likes_stats,
        event_date_range=upload_date_range,
        conversion_percentage={
            "percentage": math.ceil((len(matches) / len(likes)) * 100),
            "description": "How many matches converted from total likes I sent"
        }
    )

    return stats


@app.get("/api/v1/base")
async def read_base(user_data: GetUserDep):
    return user_data


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

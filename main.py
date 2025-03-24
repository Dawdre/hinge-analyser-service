import json
import math
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Response, UploadFile, BackgroundTasks
from google.auth.transport import requests
from google.oauth2 import id_token
from jose import jwt
from sqlmodel import Session, select, delete
from starlette.middleware.cors import CORSMiddleware

from api.routes.person import router as all_routes
from auth.auth import get_user_dep
from core.session import create_db_and_tables, get_session
from models.models import Events, HingeStats, Matches, Likes, Token, HingeStatsLikes, HingeStatsMatches, Person, \
    UserMetaData, MatchesPerDayForGivenRange, LikesReceivedPerDayForGivenRange, FlexibleModel
from models.tasks import TaskManager, TaskStatus
from services.matches_likes import save_hinge_data
from services.person import save_person_data
from utils.dates import calc_per_day, get_date_ranges

# Initialise task state
task_manager = TaskManager()

# load env variables
env_path = Path(".") / ".env"
load_dotenv(env_path)

# Create app
app = FastAPI()
app.include_router(all_routes, prefix="/api/v1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173',
                   'https://localhost:5173', 'https://127.0.0.1:5173'],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT"],
    allow_headers=["*"],

)


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
async def delete_table_data(user_data: get_user_dep, session: Session = Depends(get_session)):
    # dev endpoint to delete all table data
    session.exec(delete(Likes))
    session.exec(delete(Person))
    session.exec(delete(Matches))
    session.exec(delete(UserMetaData))

    session.commit()


@app.post("/api/v1/upload")
async def create_upload_file(
        file: UploadFile,
        background_tasks: BackgroundTasks,
        user_data: get_user_dep,
        session: Session = Depends(get_session)
):
    """
    Uploads and processes a JSON file containing 'matches' data.

    This endpoint reads the uploaded file, decodes its JSON content, and processes
    the data to update user metadata and save matches information in the database.
    It also triggers background tasks for processing person data.

    Args:
        file (UploadFile): The uploaded JSON file containing matches data.
        background_tasks (BackgroundTasks): FastAPI background task manager for
            executing tasks asynchronously.
        user_data (get_user_dep): Dependency that fetches user data from the current
            token.
        session (Session): Database session dependency for executing database operations.

    Returns:
        dict: A dictionary containing the status of the operation, file size, file name,
        and the start and end date of the uploaded data.

    Raises:
        HTTPException: If the uploaded file content is not a valid JSON or cannot be
        processed.
    """
    content = await file.read(file.size)
    event_types = []

    try:
        raw_data = json.loads(content)

        # Preprocess each item, wrapping its entire content in FlexibleModel
        processed_data = [FlexibleModel(data=item) for item in raw_data]

        # Create Events Model
        events = Events(root=processed_data)

        # Get date ranges
        date_range = get_date_ranges(events)

        # Check if user exists in database
        statement = (select(UserMetaData)
                     .where(UserMetaData.user_id == user_data.get("email")))
        user_metadata = session.exec(statement).one_or_none()

        if user_metadata is None:
            uuid_capital = str(uuid.uuid4()).replace('-', '').upper()
            db_user_metadata = UserMetaData(user_id=user_data.get("email"),
                                            created_timestamp=datetime.now(),
                                            uuid=uuid_capital,
                                            login_timestamp=datetime.now(),
                                            start_range_timestamp=date_range.get("start_date"),
                                            end_range_timestamp=date_range.get("end_date"))

            session.add(db_user_metadata)
            session.commit()

        # Save matches and likes
        save_hinge_data(events, user_data.get("email"), session)

        # Trigger background task
        task_id = task_manager.create_task()
        task_manager.update_task(
            task_id,
            status=TaskStatus.PENDING,
            progress=0,
            message="Persons processing started"
        )

        background_tasks.add_task(save_person_data, events, user_data.get("email"), task_id, session)

        for event in events.root:
            for key, value in event.data.items():
                event_types.append(key)

    except (ValueError, TypeError, Exception) as e:
        raise e
        # raise HTTPException(status_code=422,
        #                     detail="Unable to process file contents. Upload a valid 'matches' JSON file.")

    return {
        "file_size": file.size,
        "file_name": file.filename,
        "hinge_event_types": set(event_types),
        "task_id": task_id,
    }


@app.get("/api/v1/matches", response_model=List[Matches])
async def read_matches(user_data: get_user_dep, session: Session = Depends(get_session)):
    statement = (select(Matches)
                 .where(Matches.user_id == user_data.get("email"))
                 .order_by(Matches.timestamp))
    matches = session.exec(statement)
    if not matches:
        raise HTTPException(status_code=404, detail="Matches not found for that user")
    return matches


@app.get("/api/v1/likes", response_model=List[Likes])
async def read_likes(user_data: get_user_dep, session: Session = Depends(get_session)):
    statement = (select(Likes)
                 .where(Likes.user_id == user_data.get("email"))
                 .order_by(Likes.timestamp))
    likes = session.exec(statement)
    if not likes:
        raise HTTPException(status_code=404, detail="Likes not found for that user")
    return likes


@app.get("/api/v1/stats", response_model=HingeStats)
async def read_stats(user_data: get_user_dep, session: Session = Depends(get_session)):
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

    date_ranges = session.exec(select(UserMetaData).where(UserMetaData.user_id == user_data.get("email"))).one()

    upload_date_range = {
        "start_date": date_ranges.start_range_timestamp,
        "end_date": date_ranges.end_range_timestamp
    }

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
async def read_base(user_data: get_user_dep):
    return user_data


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

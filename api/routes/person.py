import asyncio
import base64
import io
import math

import httpx
from PIL import Image
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, desc

from auth.auth import get_user_dep
from core.session import get_session
from images.thumbnails import resize_with_aspect_ratio
from models.image import ImageUrl
from models.models import Person
from models.tasks import TaskStatus

router = APIRouter()


@router.get("/persons")
async def read_person(page: int, user_data: get_user_dep, session: Session = Depends(get_session)):
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

    list_of_persons = session.exec(statement).all()

    # Pagination
    page_size = 10
    page_count = math.ceil(len(list_of_persons) / page_size)
    page = min(page, page_count)

    start_index = (page - 1) * page_size
    end_index = start_index + page_size

    list_of_persons = list_of_persons[start_index:end_index]

    if not list_of_persons:
        raise HTTPException(status_code=404, detail="Persons not found for that user")
    return {
        "persons": list_of_persons,
        "current_page": page,
        "page_count": page_count
    }


@router.get("/person/{task_id}")
async def get_task_id(task_id: str, user_data: get_user_dep):
    from models.tasks import task_manager

    if task_manager.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_manager.get_task(task_id)

    return task


@router.get("/persons/progress")
async def get_task_progress(task_id: str):
    """
    Server side event. Streams the progress of saving the Persons.

    This endpoint is used in the UI to display a progress bar
    for the task of saving the persons.

    The endpoint yields events in the Server-Sent Events format.
    The "event" field is always "Progress" and the "data" field
    is a JSON dump of the task object.

    The endpoint will keep yielding events until the task is
    finished, at which point it will stop yielding events.

    The task id is specified in the path as {task_id}.
    """
    from models.tasks import task_manager

    async def generate_events():
        if task_manager.get_task(task_id) is None:
            yield "event: taskError\n"
            yield "data: Task not found\n\n"
            return

        while task_manager.get_task(task_id).progress < 100:
            yield f"event: {TaskStatus.PROCESSING.value}\n"
            yield f"data: {task_manager.get_task(task_id).to_json()}\n\n"
            await asyncio.sleep(0.5)

        if task_manager.get_task(task_id).status == TaskStatus.FAILED:
            yield f"event: {TaskStatus.FAILED.value}\n"
            yield f"data: {task_manager.get_task(task_id).to_json()}\n\n"
            return

        if task_manager.get_task(task_id).status == TaskStatus.PENDING:
            yield f"event: {TaskStatus.PENDING.value}\n"
            yield f"data: {task_manager.get_task(task_id).to_json()}\n\n"

        if task_manager.get_task(task_id).progress == 100:
            yield f"event: {TaskStatus.COMPLETED.value}\n"
            yield f"data: {task_manager.get_task(task_id).to_json()}\n\n"

    return StreamingResponse(generate_events(), media_type="text/event-stream")


@router.post("/generate-thumbnail")
async def generate_thumbnail(image_url: ImageUrl):
    def make_base64(source, mime_type):
        base64_str = base64.b64encode(source).decode("utf-8")
        return f"data:{mime_type};base64,{base64_str}"

    async with httpx.AsyncClient() as client:
        url = image_url.url
        try:
            response = await client.get(url)
            response.raise_for_status()

            image = Image.open(io.BytesIO(response.content))

            # Declare thumbnail
            thumbnail = image.copy()
            thumbnail = resize_with_aspect_ratio(thumbnail)

            thumbnail_io = io.BytesIO()
            thumbnail.save(thumbnail_io, format=image.format)
            thumbnail_io.seek(0)

            thumbnail_bytes = make_base64(thumbnail_io.getvalue(), image.format)

            return thumbnail_bytes

        except httpx.HTTPError as e:
            return None

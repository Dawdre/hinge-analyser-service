import asyncio
import json

from sqlmodel import Session

from models.models import Events, WhoLiked, Person
from models.tasks import TaskStatus
from utils.dates import parse_timestamp
from utils.events import get_like_content


async def save_person_data(events: Events, user_id: str, task_id: str, session: Session):
    from models.tasks import task_manager
    """
    Iterate over the given events and save a Person object for each event that has a match and/or like.

    :param task_id:
    :param events: The events to save.
    :param user_id: The user_id to associate with the Person objects.
    :param session: The database session to use.
    """
    total_events = len(events.root)
    processed_events = 0

    try:
        for event in events.root:
            for key, value in event.data.items():
                if key == "match" and "like" and "chats" and "block" and "we_met" in event.data:
                    db_person = Person()
                    db_person.user_id = user_id
                    db_person.has_media = False

                    db_person.matched = True
                    db_person.who_liked = WhoLiked.YOU.value
                    db_person.blocked = True

                    if event.data.get("like") is not None:
                        db_person.like_timestamp = parse_timestamp(event.data["like"][0])
                        await build_like_content(event.data["like"][0], db_person)
                    if event.data.get("match") is not None:
                        db_person.match_timestamp = parse_timestamp(event.data["match"][0])

                    if event.data["we_met"][0].get("did_meet_subject") == "Yes":
                        db_person.we_met = True
                    else:
                        db_person.we_met = False

                    # TODO finish NLP
                    # for chat in event.get("chats"):
                    #     doc1 = nlp(chat.get("body"))
                    #     for blah in doc1.ents:
                    #         print(blah.text, blah.label_)

                    session.add(db_person)

                elif key == "match" and "like" and "chats" and "block" in event.data:
                    db_person = Person()

                    db_person.user_id = user_id
                    db_person.has_media = False

                    db_person.matched = True
                    db_person.who_liked = WhoLiked.YOU.value
                    db_person.blocked = True

                    if event.data.get("like") is not None:
                        db_person.like_timestamp = parse_timestamp(event.data["like"][0])
                        await build_like_content(event.data["like"][0], db_person)
                    if event.data.get("match") is not None:
                        db_person.match_timestamp = parse_timestamp(event.data["match"][0])

                    session.add(db_person)

                elif key == "match" and "like" and "we_met" in event.data:
                    db_person = Person()

                    db_person.user_id = user_id
                    db_person.has_media = False

                    db_person.matched = True
                    db_person.who_liked = WhoLiked.YOU.value

                    if event.data.get("like") is not None:
                        db_person.like_timestamp = parse_timestamp(event.data["like"][0])
                        await build_like_content(event.data["like"][0], db_person)
                    if event.data.get("match") is not None:
                        db_person.match_timestamp = parse_timestamp(event.data["match"][0])

                    if event.data["we_met"][0].get("did_meet_subject") == "Yes":
                        db_person.we_met = True
                    else:
                        db_person.we_met = False

                    session.add(db_person)

                elif key == "match" and "like" in event.data:
                    db_person = Person()

                    db_person.user_id = user_id
                    db_person.has_media = False

                    db_person.matched = True
                    db_person.who_liked = WhoLiked.YOU.value

                    if event.data.get("like") is not None:
                        db_person.like_timestamp = parse_timestamp(event.data["like"][0])
                        await build_like_content(event.data["like"][0], db_person)
                    if event.data.get("match") is not None:
                        db_person.match_timestamp = parse_timestamp(event.data["match"][0])

                    session.add(db_person)

                elif key == "match" and "chats" in event.data:
                    db_person = Person()

                    db_person.user_id = user_id
                    db_person.has_media = False

                    db_person.matched = True
                    db_person.who_liked = WhoLiked.THEM.value
                    db_person.match_timestamp = parse_timestamp(event.data["match"][0])

                    session.add(db_person)

                elif key == "match" and "we_met" in event.data:
                    db_person = Person()

                    db_person.user_id = user_id
                    db_person.has_media = False

                    db_person.matched = True
                    db_person.who_liked = WhoLiked.THEM.value
                    db_person.match_timestamp = parse_timestamp(event.data["match"][0])

                    if event.data["we_met"][0].get("did_meet_subject") == "Yes":
                        db_person.we_met = True
                    else:
                        db_person.we_met = False

                    session.add(db_person)

                elif key == "like" in event.data:
                    db_person = Person()

                    db_person.user_id = user_id
                    db_person.has_media = False

                    db_person.matched = False
                    db_person.who_liked = WhoLiked.YOU.value
                    db_person.like_timestamp = parse_timestamp(event.data["like"][0])

                    await build_like_content(event.data["like"][0], db_person)

                    session.add(db_person)

                elif key == "match" in event.data:
                    db_person = Person()

                    db_person.user_id = user_id
                    db_person.has_media = False

                    db_person.matched = True
                    db_person.who_liked = WhoLiked.THEM.value
                    db_person.match_timestamp = parse_timestamp(event.data["match"][0])

                    session.add(db_person)

                elif key == "we_met" or "block" in event.data:
                    continue

            processed_events += 1
            progress = (processed_events / total_events) * 100
            print(progress, "events processed", processed_events, "of", total_events)

            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=round(progress, 2),
                message=f"Working out who you matched with, from {total_events} Hinge events. "
                        f"{processed_events}/{total_events} complete."
            )

            await asyncio.sleep(0.1)

        session.commit()

        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message=f"{processed_events}/{total_events} completed"
        )

    except Exception as e:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            progress=0,
            message=str(e)
        )


async def build_like_content(item, db_person):
    like_content = item.get("content")[0]

    if get_like_content(item) in [1, 2, 3]:
        db_person.has_media = True

    if get_like_content(item) == 1:
        db_person.what_you_liked_photo = like_content.get("photo").get("url")

        # Generate photo thumbnail
        # db_person.thumbnail = await generate_thumbnail(
        #     ImageUrl(url=like_content.get("photo").get("url"))
        # )

    elif get_like_content(item) == 2:
        question_answer = {
            "question": like_content.get("prompt").get("question"),
            "answer": like_content.get("prompt").get("answer")
        }
        db_person.what_you_liked_prompt = json.dumps(question_answer)

    elif get_like_content(item) == 3:
        db_person.what_you_liked_video = like_content.get("video").get("url")

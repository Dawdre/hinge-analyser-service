import json

from sqlmodel import Session

from models.models import Events, WhoLiked, Person
from utils.dates import parse_timestamp
from utils.events import get_like_content


def save_person_data(events: Events, user_id: str, session: Session):
    """
    Iterate over the given events and save a Person object for each event that has a match and/or like.

    :param events: The events to save.
    :param user_id: The user_id to associate with the Person objects.
    :param session: The database session to use.
    """
    for event in events.root:
        db_person = Person(user_id=user_id)
        db_person.has_media = False

        if (event.get("match")
                and event.get("like")
                and event.get("chats")
                and event.get("we_met")):

            db_person.matched = True
            db_person.who_liked = WhoLiked.YOU.value
            db_person.match_timestamp = parse_timestamp(event.get("match")[0])
            db_person.like_timestamp = parse_timestamp(event.get("like")[0])

            # for chat in event.get("chats"):
            #     doc1 = nlp(chat.get("body"))
            #     for blah in doc1.ents:
            #         print(blah.text, blah.label_)

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
                like_stuff = json.loads(event.get("like")[0]["content"])[0]
                db_person.what_you_liked_photo = like_stuff.get("photo").get("url")

                if like_stuff is not None:
                    db_person.has_media = True
            elif get_like_content(event.get("like")) == 2:
                prompt_stuff = json.loads(event.get("like")[0]["content"])[0]
                db_person.what_you_liked_prompt = prompt_stuff.get("prompt").get("question")
            else:
                db_person.what_you_liked_video = "video"

        elif event.get("match") and event.get("chats"):
            db_person.matched = True
            db_person.who_liked = WhoLiked.THEM.value
            db_person.match_timestamp = parse_timestamp(event.get("match")[0])

        elif event.get("like"):
            db_person.matched = False
            db_person.who_liked = WhoLiked.YOU.value
            db_person.like_timestamp = parse_timestamp(event.get("like")[0])

            if get_like_content(event.get("like")) == 1:
                like_stuff = json.loads(event.get("like")[0]["content"])[0]
                db_person.what_you_liked_photo = like_stuff.get("photo").get("url")

                if like_stuff is not None:
                    db_person.has_media = True
            elif get_like_content(event.get("like")) == 2:
                prompt_stuff = json.loads(event.get("like")[0]["content"])[0]
                db_person.what_you_liked_prompt = prompt_stuff.get("prompt").get("question")
            else:
                db_person.what_you_liked_video = "video"

        elif event.get("match") or event.get("block"):
            continue
            # db_person.matched = True
            # db_person.match_timestamp = parse_timestamp(event.get("match")[0])
            # db_person.who_liked = WhoLiked.THEM.value

        session.add(db_person)

    session.commit()

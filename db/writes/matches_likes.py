from sqlmodel import Session

from db.statements import check_existing_and_delete
from models.models import Matches, Likes, Events
from utils.dates import parse_timestamp
from utils.events import get_like_content


def save_hinge_data(events: Events, user_id: str, session: Session):
    """
    Save the given events to the database.

    This function takes in an Events object and adds the various likes and matches to the database, with the associated user_id.

    :param events: The Events object to save.
    :param user_id: The user_id to associate with the created Likes and Matches.
    :param session: The session to use to communicate with the database.
    """
    check_existing_and_delete(user_id, session)

    for evt in events.root:
        if evt.get("match") and evt.get("like"):
            # I liked them and got a match
            event_timestamp = parse_timestamp(evt.get("match")[0])
            db_match = Matches(user_id=user_id, type=1, timestamp=event_timestamp)
            db_like = Likes(user_id=user_id, type=get_like_content(evt.get("like")), timestamp=event_timestamp)
            session.add(db_like)
            session.add(db_match)
        elif evt.get("match"):
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

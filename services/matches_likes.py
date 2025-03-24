from sqlmodel import Session

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
    for event in events.root:
        for key, value in event.data.items():
            if key == "match" and "like" in event.data:
                match_timestamp = parse_timestamp(event.data["match"][0])
                like_timestamp = parse_timestamp(event.data["like"][0])
                db_match = Matches(user_id=user_id, type=1, timestamp=match_timestamp)
                db_like = Likes(user_id=user_id, type=get_like_content(event.data["like"][0]),
                                timestamp=like_timestamp)
                session.add(db_match)
                session.add(db_like)

            elif key == "match" in event.data:
                match_timestamp = parse_timestamp(event.data["match"][0])
                db_match = Matches(user_id=user_id, type=2, timestamp=match_timestamp)
                session.add(db_match)

            elif key == "like" in event.data:
                like_timestamp = parse_timestamp(event.data["like"][0])
                db_like = Likes(user_id=user_id, type=get_like_content(event.data["like"][0]),
                                timestamp=like_timestamp)
                session.add(db_like)

    session.commit()

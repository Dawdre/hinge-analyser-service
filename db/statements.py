from sqlalchemy import delete
from sqlmodel import Session, select

from models.models import Matches, Likes


def check_existing_and_delete(user_id: str, session: Session):
    matches_statement = select(Matches).where(Matches.user_id == user_id)
    matches_results = session.exec(matches_statement).first()

    likes_statement = select(Likes).where(Likes.user_id == user_id)
    likes_results = session.exec(likes_statement).first()

    if matches_results and likes_results:
        delete_statement_matches = delete(Matches).where(Matches.user_id == user_id)
        session.exec(delete_statement_matches)

        delete_statement_likes = delete(Likes).where(Likes.user_id == user_id)
        session.exec(delete_statement_likes)

        session.commit()

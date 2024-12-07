from sqlmodel import Session, select, delete

from models.models import Matches, Likes, Person


def check_existing_and_delete(user_id: str, session: Session):
    matches_statement = select(Matches).where(Matches.user_id == user_id)
    matches_results = session.exec(matches_statement).first()

    likes_statement = select(Likes).where(Likes.user_id == user_id)
    likes_results = session.exec(likes_statement).first()

    persons_statement = select(Person).where(Person.user_id == user_id)
    persons_results = session.exec(persons_statement).first()

    if matches_results and likes_results and persons_results:
        delete_statement_matches = delete(Matches).where(Matches.user_id == user_id)
        session.exec(delete_statement_matches)

        delete_statement_likes = delete(Likes).where(Likes.user_id == user_id)
        session.exec(delete_statement_likes)

        delete_statement_persons = delete(Person).where(Person.user_id == user_id)
        session.exec(delete_statement_persons)

        session.commit()

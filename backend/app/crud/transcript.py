from sqlalchemy.orm import Session
from app.models.transcript import Transcript

def get_transcript_by_video_id(db: Session, video_id: str) -> Transcript | None:
    return db.query(Transcript).filter(Transcript.video_id == video_id).first()

def create_transcript(db: Session, video_id: str, url: str, transcript_text: str) -> Transcript:
    db_transcript = Transcript(
        video_id=video_id,
        url=url,
        transcript=transcript_text
    )
    db.add(db_transcript)
    db.commit()
    db.refresh(db_transcript)
    return db_transcript

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import csv
import enum

app = FastAPI()

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class EventStatus(enum.Enum):
    scheduled = "scheduled"
    ongoing = "ongoing"
    completed = "completed"
    canceled = "canceled"

class Event(Base):
    __tablename__ = "events"
    event_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    location = Column(String)
    max_attendees = Column(Integer)
    status = Column(Enum(EventStatus))

class Attendee(Base):
    __tablename__ = "attendees"
    attendee_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True, index=True)
    phone_number = Column(String)
    event_id = Column(Integer, ForeignKey("events.event_id"))
    checked_in = Column(Boolean, default=False)

    event = relationship("Event", back_populates="attendees")

Event.attendees = relationship("Attendee", back_populates="event")

Base.metadata.create_all(bind=engine)

class EventBase(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: str
    max_attendees: int
    status: EventStatus

class EventCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: str
    max_attendees: int

class EventUpdate(EventBase):
    pass

class EventInDB(EventBase):
    event_id: int

    class ConfigDict:
        orm_mode = True

class AttendeeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str

    @field_validator('first_name')
    def first_name_must_not_be_empty(cls, v):
        if not v:
            raise ValueError('first_name must not be empty')
        return v

class AttendeeCreate(AttendeeBase):
    event_id: int

class AttendeeInDB(AttendeeBase):
    attendee_id: int
    checked_in: bool

    class ConfigDict:
        orm_mode = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/events/", response_model=EventInDB)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    db_event = Event(**event.model_dump(), status=EventStatus.scheduled)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@app.get("/events/", response_model=List[EventInDB])
def read_events(status: Optional[EventStatus] = None, location: Optional[str] = None, date: Optional[datetime] = None, skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    query = db.query(Event)
    if status:
        query = query.filter(Event.status == status)
    if location:
        query = query.filter(Event.location == location)
    if date:
        query = query.filter(Event.start_time <= date, Event.end_time >= date)
    events = query.offset(skip).limit(limit).all()
    return events

@app.get("/events/{event_id}", response_model=EventInDB)
def read_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@app.put("/events/{event_id}", response_model=EventInDB)
def update_event(event_id: int, event: EventUpdate, db: Session = Depends(get_db)):
    db_event = db.query(Event).filter(Event.event_id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    for key, value in event.model_dump().items():
        setattr(db_event, key, value)
    db.commit()
    db.refresh(db_event)
    return db_event

@app.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(Event).filter(Event.event_id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(db_event)
    db.commit()
    return {"message": "Event deleted successfully"}

@app.post("/attendees/", response_model=AttendeeInDB)
def register_attendee(attendee: AttendeeCreate, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == attendee.event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if db.query(Attendee).filter(Attendee.event_id == attendee.event_id).count() >= event.max_attendees:
        raise HTTPException(status_code=400, detail="Event is full")
    db_attendee = Attendee(**attendee.model_dump())
    db.add(db_attendee)
    db.commit()
    db.refresh(db_attendee)
    return db_attendee

@app.put("/attendees/{attendee_id}/checkin", response_model=AttendeeInDB)
def checkin_attendee(attendee_id: int, db: Session = Depends(get_db)):
    attendee = db.query(Attendee).filter(Attendee.attendee_id == attendee_id).first()
    if attendee is None:
        raise HTTPException(status_code=404, detail="Attendee not found")
    attendee.checked_in = True
    db.commit()
    db.refresh(attendee)
    return attendee

@app.get("/events/{event_id}/attendees", response_model=List[AttendeeInDB])
def list_attendees(event_id: int, db: Session = Depends(get_db)):
    attendees = db.query(Attendee).filter(Attendee.event_id == event_id).all()
    return attendees

@app.post("/events/{event_id}/attendees/checkin")
async def bulk_checkin_attendees(event_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    content = await file.read()
    decoded_content = content.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded_content)

    for row in reader:
        attendee = db.query(Attendee).filter(Attendee.email == row['email'], Attendee.event_id == event_id).first()
        if attendee:
            attendee.checked_in = True
            db.commit()
            db.refresh(attendee)

    return {"message": "Attendees checked in successfully"}

def update_event_status():
    db = SessionLocal()
    try:
        events = db.query(Event).filter(Event.end_time < datetime.now(), Event.status != EventStatus.completed).all()
        for event in events:
            event.status = EventStatus.completed
            db.commit()
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(update_event_status, 'interval', minutes=1)
scheduler.start()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Event Management API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
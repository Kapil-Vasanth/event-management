import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, Base, get_db, Event, Attendee, EventStatus
from datetime import datetime, timedelta
import time

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(Event(
        name="Test Event",
        description="This is a test event",
        start_time=datetime(2023, 10, 10, 10, 0, 0),
        end_time=datetime(2023, 10, 10, 12, 0, 0),
        location="Test Location",
        max_attendees=2,
        status=EventStatus.scheduled
    ))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

def test_create_event(setup_database):
    response = client.post("/events/", json={
        "name": "Another Test Event",
        "description": "This is another test event",
        "start_time": "2023-10-11T10:00:00",
        "end_time": "2023-10-11T12:00:00",
        "location": "Another Test Location",
        "max_attendees": 100
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Another Test Event"

def test_create_event_invalid_data(setup_database):
    response = client.post("/events/", json={
        "name": "",
        "description": "This is another test event",
        "start_time": "2023-10-11T10:00:00",
        "end_time": "2023-10-11T12:00:00",
        "location": "Another Test Location",
        "max_attendees": 100
    })
    assert response.status_code == 422

def test_register_attendee(setup_database):
    response = client.post("/attendees/", json={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone_number": "1234567890",
        "event_id": 1
    })
    assert response.status_code == 200
    assert response.json()["email"] == "john.doe@example.com"

def test_register_attendee_invalid_data(setup_database):
    response = client.post("/attendees/", json={
        "first_name": "",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone_number": "1234567890",
        "event_id": 1
    })
    assert response.status_code == 422

def test_register_attendee_limit_reached(setup_database):
    client.post("/attendees/", json={
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "phone_number": "0987654321",
        "event_id": 1
    })
    response = client.post("/attendees/", json={
        "first_name": "Jim",
        "last_name": "Beam",
        "email": "jim.beam@example.com",
        "phone_number": "1122334455",
        "event_id": 1
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Event is full"

def test_checkin_attendee(setup_database):
    response = client.put("/attendees/1/checkin")
    assert response.status_code == 200
    assert response.json()["checked_in"] == True

def test_list_events(setup_database):
    response = client.get("/events/")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_list_attendees(setup_database):
    response = client.get("/events/1/attendees")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_delete_event(setup_database):
    response = client.delete("/events/1")
    assert response.status_code == 200
    assert response.json()["message"] == "Event deleted successfully"

def test_bulk_checkin(setup_database):
    # Clear the database
    db = TestingSessionLocal()
    db.query(Attendee).delete()
    db.query(Event).delete()
    db.commit()
    db.close()

    # Create event
    event_response = client.post("/events/", json={
        "name": "Bulk Check-in Event",
        "description": "This is a bulk check-in event",
        "start_time": "2023-10-11T10:00:00",
        "end_time": "2023-10-11T12:00:00",
        "location": "Bulk Check-in Location",
        "max_attendees": 100
    })
    event_id = event_response.json()["event_id"]
    
    # Register attendees with unique emails
    client.post("/attendees/", json={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.bulk@example.com",
        "phone_number": "1234567890",
        "event_id": event_id
    })
    client.post("/attendees/", json={
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.bulk@example.com",
        "phone_number": "0987654321",
        "event_id": event_id
    })

    # Perform bulk check-in with matching emails
    csv_content = "email\njohn.bulk@example.com\njane.bulk@example.com"
    response = client.post(f"/events/{event_id}/attendees/checkin", 
                         files={"file": ("attendees.csv", csv_content, "text/csv")})
    
    assert response.status_code == 200
    assert response.json()["message"] == "Attendees checked in successfully"

def test_event_status_updates():
    # Create an event that is currently ongoing
    event_response = client.post("/events/", json={
        "name": "Ongoing Event",
        "description": "This event is ongoing",
        "start_time": (datetime.now() - timedelta(minutes=10)).isoformat(),
        "end_time": (datetime.now() + timedelta(minutes=10)).isoformat(),
        "location": "Test Location",
        "max_attendees": 100
    })
    event_id = event_response.json()["event_id"]

    # Wait for the scheduler to update the status
    time.sleep(65)  # Wait a bit more than the scheduler interval

    # Check if the event status is updated to ongoing
    response = client.get(f"/events/{event_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "ongoing"

    # Create an event that has just ended
    event_response = client.post("/events/", json={
        "name": "Ended Event",
        "description": "This event has ended",
        "start_time": (datetime.now() - timedelta(minutes=20)).isoformat(),
        "end_time": (datetime.now() - timedelta(minutes=10)).isoformat(),
        "location": "Test Location",
        "max_attendees": 100
    })
    event_id = event_response.json()["event_id"]

    # Wait for the scheduler to update the status
    time.sleep(65)  # Wait a bit more than the scheduler interval

    # Check if the event status is updated to completed
    response = client.get(f"/events/{event_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
# Event Management API

This is a FastAPI-based Event Management API that allows you to create events, register attendees, and perform bulk check-ins. The API also includes automatic status updates for events.

## Features

- Create events
- Register attendees
- Bulk check-in attendees
- Automatic status updates for events

## Requirements

- Python 3.9+
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic
- APScheduler

## Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/yourusername/event-management.git
   cd event-management
   ```

2. Create and activate a virtual environment:

   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the dependencies:

   ```sh
   pip install -r requirements.txt
   ```

## Running the Application

1. Start the FastAPI application:

   ```sh
   uvicorn main:app --host 0.0.0.0 --port 10000
   ```

2. The API will be accessible at `http://localhost:10000`.

## API Endpoints

### Create Event

- **Endpoint**: `POST /events/`
- **Description**: Create a new event. The status is initialized as 'scheduled'.
- **Request Body**:

  ```json
  {
    "name": "Tech Conference 2025",
    "description": "A conference about the latest in technology.",
    "start_time": "2025-02-13T09:00:00Z",
    "end_time": "2025-02-13T17:00:00Z",
    "location": "Tech Park, Silicon Valley",
    "max_attendees": 500
  }
  ```

- **Response**:

  ```json
  {
    "event_id": 1,
    "name": "Tech Conference 2025",
    "description": "A conference about the latest in technology.",
    "start_time": "2025-02-13T09:00:00Z",
    "end_time": "2025-02-13T17:00:00Z",
    "location": "Tech Park, Silicon Valley",
    "max_attendees": 500,
    "status": "scheduled"
  }
  ```

### Register Attendee

- **Endpoint**: `POST /attendees/`
- **Description**: Register an attendee for an event.
- **Request Body**:

  ```json
  {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone_number": "1234567890",
    "event_id": 1
  }
  ```

- **Response**:

  ```json
  {
    "attendee_id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone_number": "1234567890",
    "event_id": 1,
    "checked_in": false
  }
  ```

### Bulk Check-in Attendees

- **Endpoint**: `POST /events/{event_id}/attendees/checkin`
- **Description**: Perform bulk check-in for attendees using a CSV file.
- **Request Body**: Multipart form-data with a CSV file containing attendee emails.

  Example CSV content:

  ```csv
  email
  john.doe@example.com
  jane.doe@example.com
  ```

- **Response**:

  ```json
  {
    "message": "Attendees checked in successfully"
  }
  ```

### List Attendees

- **Endpoint**: `GET /events/{event_id}/attendees`
- **Description**: List all attendees for a specific event.
- **Response**:

  ```json
  [
    {
      "attendee_id": 1,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john.doe@example.com",
      "phone_number": "1234567890",
      "event_id": 1,
      "checked_in": true
    },
    {
      "attendee_id": 2,
      "first_name": "Jane",
      "last_name": "Doe",
      "email": "jane.doe@example.com",
      "phone_number": "0987654321",
      "event_id": 1,
      "checked_in": true
    }
  ]
  ```

### Automatic Status Updates

The application includes a background scheduler that automatically updates the status of events based on their start and end times. The status transitions are as follows:

- From `scheduled` to `ongoing` when the event starts.
- From `ongoing` to `completed` when the event ends.

## Deployment

To deploy the application to Render, follow these steps:

1. Create a render.yaml
    file in the root of your project directory:
   ```yaml
   services:
     - type: web
       name: event-management-api
       env: python
       plan: free
       buildCommand: "pip install -r requirements.txt"
       startCommand: "uvicorn main:app --host 0.0.0.0 --port 10000"
   ```
2. Sign up for a Render account at [render.com](https://render.com/).

2. Push your code to a GitHub repository.


4. Create a new Web Service on Render, connect your GitHub repository, and deploy the application.

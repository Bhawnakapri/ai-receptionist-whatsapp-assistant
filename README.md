# AI Receptionist & WhatsApp Assistant — Salon Studio

An integrated AI receptionist system designed for salon businesses. It provides a shared backend for customer conversations, appointment booking, appointment management, WhatsApp messaging, and voice-based interactions.

This project is a functional learning MVP built using Python and FastAPI.

## Features

### 1. Conversational Assistant
- Rule-based responses for common customer enquiries.
- Answers questions about salon services, prices, and opening hours.
- Maintains conversation history.
- Supports multi-turn appointment booking.
- Optional OpenAI integration for AI-generated responses.

### 2. Appointment Management
- Book salon appointments through conversations.
- Check available appointment slots.
- Validate appointment dates and salon operating hours.
- Prevent overlapping bookings.
- Cancel existing appointments.
- Reschedule existing appointments.
- Store customer and appointment information in SQLite.

### 3. WhatsApp Integration
- Meta WhatsApp Cloud API webhook integration.
- Handles incoming text messages.
- Generates responses using the shared assistant and booking logic.
- Sends outbound WhatsApp messages when API credentials are configured.

### 4. Voice Receptionist
- Twilio voice webhook integration.
- Accepts incoming voice interactions.
- Uses speech input and generates spoken responses through TwiML.
- Connects voice conversations to the shared assistant and booking logic.

### 5. Appointment Reminders
- Scheduled daily reminder processing.
- Sends WhatsApp reminders for appointments scheduled for the following day.
- Includes a manual reminder trigger for demonstrations.
- Requires valid WhatsApp API credentials to send actual messages.

### 6. Web Dashboard
- Overview of services, customers, and appointments.
- Appointment status statistics.
- Customer directory.
- Salon service catalogue.
- Interactive chat interface.
- Appointment information and conversation access.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy |
| Data Validation | Pydantic |
| Frontend | HTML, CSS, JavaScript |
| AI Integration | OpenAI API (optional) |
| Messaging | Meta WhatsApp Cloud API |
| Voice Integration | Twilio |
| API Documentation | Swagger UI |

## Project Structure

```text
ai-receptionist-whatsapp-assistant/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   │
│   ├── services/
│   │   ├── assistant.py
│   │   ├── booking.py
│   │   ├── conversation_booking.py
│   │   ├── appointment_management.py
│   │   └── reminders.py
│   │
│   ├── integrations/
│   │   ├── whatsapp.py
│   │   └── voice.py
│   │
│   └── static/
│       └── index.html
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
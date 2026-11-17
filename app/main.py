import asyncio
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, text

from .services.reminders import send_appointment_reminders
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy.orm import Session
from sqlalchemy import select

from .database import Base, engine, get_db
from . import models, schemas

from .services.assistant import generate_reply
from .services.booking import create_booking, list_available_slots
from .services.conversation_booking import handle_booking
from .services.appointment_management import (
    find_customer_appointments,
    cancel_appointment as cancel_appointment_service,
    reschedule_appointment as reschedule_appointment_service
)
from .config import settings

from .integrations.whatsapp import send_whatsapp_message
from .integrations.voice import make_twiml_response


# Initialize database and default salon services
async def reminder_scheduler():

    timezone = ZoneInfo("Asia/Kolkata")

    while True:
        now = datetime.now(timezone)

        next_run = datetime.combine(
            now.date(),
            time(10, 0),
            tzinfo=timezone
        )

        if now >= next_run:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()

        await asyncio.sleep(wait_seconds)

        db = next(get_db())

        try:
            count = await send_appointment_reminders(db)
            print(f"Appointment reminders sent: {count}")

        except Exception as exc:
            print(f"Reminder scheduler error: {exc}")

        finally:
            db.close()
async def reminder_scheduler():

    timezone = ZoneInfo("Asia/Kolkata")

    while True:
        now = datetime.now(timezone)

        next_run = datetime.combine(
            now.date(),
            time(10, 0),
            tzinfo=timezone
        )

        if now >= next_run:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()

        await asyncio.sleep(wait_seconds)

        db = next(get_db())

        try:
            count = await send_appointment_reminders(db)
            print(f"Appointment reminders sent: {count}")

        except Exception as exc:
            print(f"Reminder scheduler error: {exc}")

        finally:
            db.close()


# Create FastAPI application
app = FastAPI(
    title="AI Receptionist & WhatsApp Assistant",
    description="Multi-channel AI receptionist starter for a salon studio.",
    version="1.0.0",
    lifespan=lifespan
)


# Dashboard
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return open(
        "app/static/index.html",
        encoding="utf-8"
    ).read()


# Health check
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "AI Receptionist"
    }


# Get all active services
@app.get("/api/services", response_model=list[schemas.ServiceOut])
def get_services(db: Session = Depends(get_db)):

    return db.scalars(
        select(models.Service).where(
            models.Service.is_active == True
        )
    ).all()


# Add a new service
@app.post("/api/services", response_model=schemas.ServiceOut)
def add_service(
    payload: schemas.ServiceCreate,
    db: Session = Depends(get_db)
):

    service = models.Service(**payload.model_dump())

    db.add(service)
    db.commit()
    db.refresh(service)

    return service


# Get all customers
@app.get("/api/customers", response_model=list[schemas.CustomerOut])
def get_customers(db: Session = Depends(get_db)):

    return db.scalars(
        select(models.Customer).order_by(
            models.Customer.created_at.desc()
        )
    ).all()


# Get all appointments
@app.get("/api/appointments", response_model=list[schemas.AppointmentOut])
def get_appointments(db: Session = Depends(get_db)):

    return db.scalars(
        select(models.Appointment).order_by(
            models.Appointment.start_at.desc()
        )
    ).all()


# Create appointment directly through API
@app.post("/api/appointments", response_model=schemas.AppointmentOut)
def book_appointment(
    payload: schemas.AppointmentCreate,
    db: Session = Depends(get_db)
):

    try:
        return create_booking(db, payload)

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        )


# Check available appointment slots
@app.get("/api/availability")
def availability(
    service_id: int,
    date: str,
    db: Session = Depends(get_db)
):

    try:
        return {
            "date": date,
            "slots": list_available_slots(
                db,
                service_id,
                date
            )
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# Chat endpoint
@app.post("/api/chat", response_model=schemas.ChatResponse)
def chat(
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db)
):

    # Find or create customer
    customer = None

    if payload.phone:

        customer = db.scalar(
            select(models.Customer).where(
                models.Customer.phone == payload.phone
            )
        )

        if not customer:

            customer = models.Customer(
                name=payload.name or "WhatsApp Customer",
                phone=payload.phone
            )

            db.add(customer)
            db.commit()
            db.refresh(customer)

    # Continue existing conversation or create a new one
    if payload.conversation_id:

        conversation = db.get(
            models.Conversation,
            payload.conversation_id
        )

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found."
            )

        if conversation.channel != payload.channel:
            raise HTTPException(
                status_code=400,
                detail="Conversation channel mismatch."
            )

        if customer and conversation.customer_id != customer.id:
            raise HTTPException(
                status_code=403,
                detail="This conversation belongs to another customer."
            )

    else:

        conversation = models.Conversation(
            channel=payload.channel,
            customer_id=customer.id if customer else None
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Save customer message
    user_message = models.Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message
    )

    db.add(user_message)
    db.commit()

    # Handle appointment booking conversation first
    booking_reply = handle_booking(
        payload.message,
        db,
        conversation.id,
        payload.phone
    )

    # If booking logic does not handle the message,
    # use the regular assistant
    if booking_reply is not None:

        reply = booking_reply

    else:

        reply = generate_reply(
            payload.message,
            db,
            conversation.id
        )

    # Save assistant response
    assistant_message = models.Message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply
    )

    db.add(assistant_message)
    db.commit()

    return {
        "reply": reply,
        "conversation_id": conversation.id,
        "ai_mode": "rule_based"
    }


# WhatsApp webhook verification
@app.get("/webhooks/whatsapp")
def whatsapp_verify(request: Request):

    params = request.query_params

    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.whatsapp_verify_token
    ):

        return PlainTextResponse(
            params.get("hub.challenge", "")
        )

    raise HTTPException(
        status_code=403,
        detail="Webhook verification failed"
    )


# Receive WhatsApp messages
@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()

    try:
        value = data["entry"][0]["changes"][0]["value"]
        message = value["messages"][0]

        phone = message["from"]
        text = message.get("text", {}).get("body", "").strip()

    except (KeyError, IndexError, TypeError):
        return {"status": "ignored"}

    if not text:
        return {"status": "ignored"}

    # Find or create customer
    customer = db.scalar(
        select(models.Customer).where(
            models.Customer.phone == phone
        )
    )

    if not customer:
        customer = models.Customer(
            name="WhatsApp Customer",
            phone=phone
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    # Find existing WhatsApp conversation
    conversation = db.scalar(
        select(models.Conversation)
        .where(
            models.Conversation.channel == "whatsapp",
            models.Conversation.customer_id == customer.id
        )
        .order_by(models.Conversation.id.desc())
    )

    # Create conversation if one doesn't exist
    if not conversation:
        conversation = models.Conversation(
            channel="whatsapp",
            customer_id=customer.id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Save incoming message
    user_message = models.Message(
        conversation_id=conversation.id,
        role="user",
        content=text
    )
    db.add(user_message)
    db.commit()

    # Handle booking, cancellation and rescheduling
    reply = handle_booking(
        text,
        db,
        conversation.id,
        phone
    )

    # Use general assistant if booking handler has no response
    if reply is None:
        reply = generate_reply(
            text,
            db,
            conversation.id
        )

    # Save assistant response
    assistant_message = models.Message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply
    )
    db.add(assistant_message)
    db.commit()

    # Send WhatsApp response
    await send_whatsapp_message(phone, reply)

    return {"status": "processed"}


# Twilio voice webhook
@app.post("/webhooks/twilio/voice")
async def twilio_voice(
    From: str = Form(default=""),
    SpeechResult: str = Form(default=""),
    db: Session = Depends(get_db)
):
    phone = From.strip()
    text = SpeechResult.strip()

    # Find or create caller
    customer = None

    if phone:
        customer = db.scalar(
            select(models.Customer).where(
                models.Customer.phone == phone
            )
        )

        if not customer:
            customer = models.Customer(
                name="Voice Customer",
                phone=phone
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)

    # Find or create voice conversation
    conversation = None

    if customer:
        conversation = db.scalar(
            select(models.Conversation)
            .where(
                models.Conversation.channel == "voice",
                models.Conversation.customer_id == customer.id
            )
            .order_by(models.Conversation.id.desc())
        )

    if not conversation:
        conversation = models.Conversation(
            channel="voice",
            customer_id=customer.id if customer else None
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    if not text:
        text = "Hello, I would like to know about salon services."

    # Save caller's message
    db.add(models.Message(
        conversation_id=conversation.id,
        role="user",
        content=text
    ))
    db.commit()

    # Process booking or general enquiry
    reply = handle_booking(
        text,
        db,
        conversation.id,
        phone
    )

    if reply is None:
        reply = generate_reply(
            text,
            db,
            conversation.id
        )

    # Save receptionist response
    db.add(models.Message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply
    ))
    db.commit()

    return PlainTextResponse(
        make_twiml_response(reply),
        media_type="application/xml"
    )

# Get appointments for a customer
@app.get("/api/customers/{phone}/appointments")
def get_customer_appointments(
    phone: str,
    db: Session = Depends(get_db)
):

    appointments = find_customer_appointments(
        db,
        phone
    )

    return appointments


# Cancel appointment
@app.post("/api/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: int,
    phone: str,
    db: Session = Depends(get_db)
):

    try:

        appointment = cancel_appointment_service(
            db,
            appointment_id,
            phone
        )

        return {
            "message": "Appointment cancelled successfully.",
            "appointment_id": appointment.id,
            "status": appointment.status
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )


# Reschedule appointment
@app.post("/api/appointments/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: int,
    phone: str,
    new_start: datetime,
    db: Session = Depends(get_db)
):

    try:

        appointment = reschedule_appointment_service(
            db,
            appointment_id,
            phone,
            new_start
        )

        return {
            "message": "Appointment rescheduled successfully.",
            "appointment_id": appointment.id,
            "new_start": appointment.start_at,
            "new_end": appointment.end_at,
            "status": appointment.status
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=409,
            detail=str(exc)
        )
    @app.post("/api/reminders/run")
async def run_reminders(db: Session = Depends(get_db)):
    try:
        count = await send_appointment_reminders(db)

        return {
            "message": "Reminder process completed.",
            "reminders_sent": count
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )
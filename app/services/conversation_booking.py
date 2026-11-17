from datetime import datetime, date, time, timedelta
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from .booking import create_booking, list_available_slots
from .appointment_management import (
    find_customer_appointments,
    cancel_appointment,
    reschedule_appointment
)

def get_booking_session(db: Session, conversation_id: int):
    return db.scalar(
        select(models.BookingSession).where(
            models.BookingSession.conversation_id == conversation_id
        )
    )


def start_booking(db: Session, conversation_id: int):
    session = get_booking_session(db, conversation_id)

    if not session:
        session = models.BookingSession(
            conversation_id=conversation_id
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    return session


def parse_date(text: str):
    text = text.lower().strip()
    today = date.today()

    if text == "today":
        return today

    if text == "tomorrow":
        return today + timedelta(days=1)

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %B",
        "%d %b"
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt).date()

            if "%Y" not in fmt:
                parsed = parsed.replace(year=today.year)

                if parsed < today:
                    parsed = parsed.replace(year=today.year + 1)

            return parsed

        except ValueError:
            continue

    return None


def parse_time(text: str):
    text = text.lower().strip().replace(".", "")

    formats = [
        "%I:%M %p",
        "%I %p",
        "%H:%M"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text.upper(), fmt).time()
        except ValueError:
            continue

    match = re.fullmatch(r"(\d{1,2})(am|pm)", text)

    if match:
        hour = int(match.group(1))
        period = match.group(2)

        if 1 <= hour <= 12:
            hour = hour % 12

            if period == "pm":
                hour += 12

            return time(hour, 0)

    return None


def handle_booking(
    message: str,
    db: Session,
    conversation_id: int,
    customer_phone: str | None = None
):
    text = message.lower().strip()
    session = get_booking_session(db, conversation_id)
    # APPOINTMENT MANAGEMENT

    # Start cancellation or rescheduling
    if "cancel" in text and (
        "appointment" in text or
        (session and session.status == "booked")
    ):
        if not session:
            session = start_booking(db, conversation_id)

        phone = customer_phone or session.phone

        if not phone:
            session.status = "manage_cancel_phone"
            db.commit()
            return "Please share the phone number used for your booking."

        appointments = find_customer_appointments(db, phone)

        if not appointments:
            return "You don't have any upcoming confirmed appointments."

        session.phone = phone
        session.status = "manage_cancel_select"
        db.commit()

        return "Which appointment would you like to cancel?\n" + "\n".join(
            f"Booking ID: {a.id} | {a.start_at}"
            for a in appointments
        ) + "\nPlease enter the Booking ID."

    if "reschedule" in text or "change my appointment" in text:
        if not session:
            session = start_booking(db, conversation_id)

        phone = customer_phone or session.phone

        if not phone:
            session.status = "manage_reschedule_phone"
            db.commit()
            return "Please share the phone number used for your booking."

        appointments = find_customer_appointments(db, phone)

        if not appointments:
            return "You don't have any upcoming confirmed appointments."

        session.phone = phone
        session.status = "manage_reschedule_select"
        db.commit()

        return "Which appointment would you like to reschedule?\n" + "\n".join(
            f"Booking ID: {a.id} | {a.start_at}"
            for a in appointments
        ) + "\nPlease enter the Booking ID."

    # Collect phone for appointment management
    if session and session.status in [
        "manage_cancel_phone",
        "manage_reschedule_phone"
    ]:
        phone_match = re.search(r"\+?\d{10,15}", message)

        if not phone_match:
            return "Please enter a valid phone number."

        phone = phone_match.group()
        appointments = find_customer_appointments(db, phone)

        if not appointments:
            return "No upcoming confirmed appointments found for this number."

        session.phone = phone

        if session.status == "manage_cancel_phone":
            session.status = "manage_cancel_select"
            action = "cancel"
        else:
            session.status = "manage_reschedule_select"
            action = "reschedule"

        db.commit()

        return f"Which appointment would you like to {action}?\n" + "\n".join(
            f"Booking ID: {a.id} | {a.start_at}"
            for a in appointments
        ) + "\nPlease enter the Booking ID."

    # Select appointment for cancellation
    if session and session.status == "manage_cancel_select":
        if not text.isdigit():
            return "Please enter a valid Booking ID."

        try:
            appointment = cancel_appointment(
                db,
                int(text),
                session.phone
            )

            session.status = "booked"
            db.commit()

            return (
                f"Your appointment #{appointment.id} "
                "has been cancelled successfully."
            )

        except ValueError as exc:
            return str(exc)

    # Select appointment for rescheduling
    if session and session.status == "manage_reschedule_select":
        if not text.isdigit():
            return "Please enter a valid Booking ID."

        appointment_id = int(text)

        appointments = find_customer_appointments(
            db,
            session.phone
        )

        appointment = next(
            (a for a in appointments if a.id == appointment_id),
            None
        )

        if not appointment:
            return "I couldn't find that active appointment. Please enter a valid Booking ID."

        session.customer_name = str(appointment.id)
        session.service_id = appointment.service_id
        session.status = "manage_reschedule_date"
        db.commit()

        return "What new date would you prefer?"

    # Select new appointment date
    if session and session.status == "manage_reschedule_date":
        selected_date = parse_date(text)

        if not selected_date:
            return "Please enter a valid date, such as 25 November."

        if selected_date <= date.today():
            return "Please choose a future date."

        if selected_date.weekday() == 0:
            return "We're closed on Mondays. Please choose another date."

        session.appointment_date = selected_date.isoformat()
        session.status = "manage_reschedule_time"
        db.commit()

        return "What time would you prefer? For example, 3 PM."

    # Select new appointment time and complete rescheduling
    if session and session.status == "manage_reschedule_time":
        selected_time = parse_time(text)

        if not selected_time:
            return "Please enter a valid time, such as 3 PM."

        if selected_time.hour < 10 or selected_time.hour >= 20:
            return "Our working hours are 10 AM to 8 PM. Please choose another time."

        appointment_id = int(session.customer_name)

        new_start = datetime.combine(
            date.fromisoformat(session.appointment_date),
            selected_time
        )

        try:
            appointment = reschedule_appointment(
                db,
                appointment_id,
                session.phone,
                new_start
            )

            session.status = "booked"
            session.customer_name = None
            session.appointment_date = None
            session.appointment_time = None
            db.commit()

            return (
                "Your appointment has been rescheduled successfully!\n"
                f"Booking ID: {appointment.id}\n"
                f"New date: {appointment.start_at.date()}\n"
                f"New time: {appointment.start_at.strftime('%I:%M %p')}"
            )

        except ValueError as exc:
            return f"{exc} Please choose another date or time."
    if not session:
        if not any(word in text for word in ["book", "appointment", "booking"]):
            return None

        session = start_booking(db, conversation_id)

        return (
            "I'd be happy to help you book an appointment! "
            "Which service would you like?"
        )

    if text in ["cancel", "stop booking", "exit"]:
        session.status = "cancelled"
        db.commit()
        return "Your booking process has been cancelled."

    if session.status == "awaiting_confirmation":
        if text in ["yes", "y", "confirm", "confirm booking"]:
            service = db.get(models.Service, session.service_id)

            start_at = datetime.combine(
                date.fromisoformat(session.appointment_date),
                time.fromisoformat(session.appointment_time)
            )

            payload = schemas.AppointmentCreate(
                customer_name=session.customer_name,
                phone=session.phone,
                service_id=session.service_id,
                start_at=start_at
            )

            try:
                appointment = create_booking(db, payload)
            except ValueError as exc:
                session.status = "in_progress"
                session.appointment_time = None
                db.commit()
                return f"{exc} Please choose another appointment time."

            session.status = "booked"
            db.commit()

            return (
                "Your appointment has been successfully confirmed!\n"
                f"Booking ID: {appointment.id}\n"
                f"Service: {service.name}\n"
                f"Date: {session.appointment_date}\n"
                f"Time: {session.appointment_time}\n"
                "Thank you for choosing our salon!"
            )

        if text in ["no", "n"]:
            session.status = "cancelled"
            db.commit()
            return "Your booking has been cancelled. Feel free to book again anytime."

        return "Please reply YES to confirm your appointment or NO to cancel."

    if session.status != "in_progress":
        return None

    # STEP 1: Select service
    if not session.service_id:
        services = db.scalars(
            select(models.Service).where(
                models.Service.is_active == True
            )
        ).all()

        for service in services:
            if service.name.lower() in text:
                session.service_id = service.id
                db.commit()

                return (
                    f"Great! {service.name} costs ₹{service.price:g} "
                    f"and takes {service.duration_minutes} minutes. "
                    "What date would you prefer?"
                )

        available_services = ", ".join(s.name for s in services)
        return f"Please select one of our services: {available_services}."

    # STEP 2: Select date
    if not session.appointment_date:
        selected_date = parse_date(text)

        if not selected_date:
            return "Please provide a valid date, such as 20 November or 2026-11-20."

        if selected_date.weekday() == 0:
            return "We're closed on Mondays. Please choose another date."

        if selected_date <= date.today():
            return "Please choose a future date."

        session.appointment_date = selected_date.isoformat()
        db.commit()
        return "What time would you prefer? For example, 3 PM."

    # STEP 3: Select time
    if not session.appointment_time:
        selected_time = parse_time(text)

        if not selected_time:
            return "Please provide a valid time, such as 3 PM or 15:00."

        # Check salon working hours
        if selected_time.hour < 10 or selected_time.hour >= 20:
            return (
                "Our salon operates between 10:00 AM and 8:00 PM. "
                "Please choose a time within our working hours."
            )

        slots = list_available_slots(
            db,
            session.service_id,
            session.appointment_date
        )

        if selected_time.strftime("%H:%M") not in slots:
            return "Sorry, that time isn't available. Please choose another time."

        session.appointment_time = selected_time.strftime("%H:%M")
        db.commit()

        return "Please share your full name and phone number so I can prepare your booking."

    # STEP 4: Collect customer details
    if not session.customer_name or not session.phone:
        phone_match = re.search(r"\+?\d{10,15}", message)

        if phone_match:
            session.phone = phone_match.group()
        elif customer_phone:
            session.phone = customer_phone

        name = re.sub(r"\+?\d{10,15}", "", message).strip()

        name = re.sub(
            r"\b(my name is|i am|i'm)\b",
            "",
            name,
            flags=re.I
        ).strip(" ,.")

        if name and not session.customer_name:
            session.customer_name = name

        db.commit()

        if not session.customer_name:
            return "Please share your name."

        if not session.phone:
            return "Please share your phone number."

        service = db.get(models.Service, session.service_id)

        session.status = "awaiting_confirmation"
        db.commit()

        return (
            "Please confirm your appointment:\n"
            f"Name: {session.customer_name}\n"
            f"Service: {service.name}\n"
            f"Date: {session.appointment_date}\n"
            f"Time: {session.appointment_time}\n"
            f"Price: ₹{service.price:g}\n\n"
            "Reply YES to confirm or NO to cancel."
        )

    return None
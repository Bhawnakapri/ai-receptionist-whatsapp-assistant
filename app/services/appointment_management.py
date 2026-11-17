from datetime import datetime, timedelta, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models


def find_customer_appointments(db: Session, phone: str):
    """Find upcoming confirmed appointments using customer phone."""

    customer = db.scalar(
        select(models.Customer).where(
            models.Customer.phone == phone
        )
    )

    if not customer:
        return []

    appointments = db.scalars(
        select(models.Appointment)
        .where(
            models.Appointment.customer_id == customer.id,
            models.Appointment.status == "confirmed",
            models.Appointment.start_at >= datetime.now()
        )
        .order_by(models.Appointment.start_at)
    ).all()

    return appointments


def cancel_appointment(
    db: Session,
    appointment_id: int,
    phone: str
):
    """Cancel an existing appointment."""

    customer = db.scalar(
        select(models.Customer).where(
            models.Customer.phone == phone
        )
    )

    if not customer:
        raise ValueError("Customer not found.")

    appointment = db.get(
        models.Appointment,
        appointment_id
    )

    if not appointment or appointment.customer_id != customer.id:
        raise ValueError("Appointment not found.")

    if appointment.status != "confirmed":
        raise ValueError("This appointment is not active.")

    appointment.status = "cancelled"

    db.commit()
    db.refresh(appointment)

    return appointment


def reschedule_appointment(
    db: Session,
    appointment_id: int,
    phone: str,
    new_start: datetime
):
    """Move an appointment to a new available time."""

    customer = db.scalar(
        select(models.Customer).where(
            models.Customer.phone == phone
        )
    )

    if not customer:
        raise ValueError("Customer not found.")

    appointment = db.get(
        models.Appointment,
        appointment_id
    )

    if not appointment or appointment.customer_id != customer.id:
        raise ValueError("Appointment not found.")

    if appointment.status != "confirmed":
        raise ValueError("This appointment is not active.")

    service = db.get(
        models.Service,
        appointment.service_id
    )

    if not service:
        raise ValueError("Service not found.")

    new_start = new_start.replace(tzinfo=None)

    new_end = new_start + timedelta(
        minutes=service.duration_minutes
    )

    if new_start <= datetime.now():
        raise ValueError("Please choose a future appointment time.")

    if new_start.weekday() == 0:
        raise ValueError("The salon is closed on Mondays.")

    if (
        new_start.time() < time(10, 0)
        or new_end.time() > time(20, 0)
    ):
        raise ValueError(
            "Appointments are available between 10:00 AM and 8:00 PM."
        )

    conflict = db.scalar(
        select(models.Appointment).where(
            models.Appointment.id != appointment.id,
            models.Appointment.status == "confirmed",
            models.Appointment.start_at < new_end,
            models.Appointment.end_at > new_start
        )
    )

    if conflict:
        raise ValueError(
            "That time is already booked. Please choose another slot."
        )

    appointment.start_at = new_start
    appointment.end_at = new_end

    db.commit()
    db.refresh(appointment)

    return appointment
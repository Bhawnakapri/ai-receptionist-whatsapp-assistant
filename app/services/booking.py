from datetime import datetime, time, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import models, schemas
def create_booking(db: Session, payload: schemas.AppointmentCreate):
    service = db.get(models.Service, payload.service_id)
    if not service or not service.is_active: raise ValueError("Selected service is unavailable.")
    start = payload.start_at.replace(tzinfo=None)
    end = start + timedelta(minutes=service.duration_minutes)
    if start <= datetime.now(): raise ValueError("Please choose a future appointment time.")
    if start.weekday() == 0: raise ValueError("The salon is closed on Mondays.")
    if start.time() < time(10, 0) or end.time() > time(20, 0):
        raise ValueError("Appointments are available between 10:00 AM and 8:00 PM.")
    conflict = db.scalar(select(models.Appointment).where(
        models.Appointment.status == "confirmed",
        models.Appointment.start_at < end, models.Appointment.end_at > start))
    if conflict: raise ValueError("That time is already booked. Please choose another slot.")
    customer = db.scalar(select(models.Customer).where(models.Customer.phone == payload.phone))
    if not customer:
        customer = models.Customer(name=payload.customer_name, phone=payload.phone)
        db.add(customer); db.flush()
    else: customer.name = payload.customer_name
    appt = models.Appointment(customer_id=customer.id, service_id=service.id,
                              start_at=start, end_at=end, notes=payload.notes)
    db.add(appt); db.commit(); db.refresh(appt)
    return appt
def list_available_slots(db: Session, service_id: int, date_str: str):
    service = db.get(models.Service, service_id)
    if not service: raise ValueError("Service not found.")
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    if day.weekday() == 0: return []
    slots, current = [], datetime.combine(day, time(10, 0))
    closing = datetime.combine(day, time(20, 0))
    while current + timedelta(minutes=service.duration_minutes) <= closing:
        end = current + timedelta(minutes=service.duration_minutes)
        conflict = db.scalar(select(models.Appointment).where(
            models.Appointment.status == "confirmed",
            models.Appointment.start_at < end, models.Appointment.end_at > current))
        if not conflict and current > datetime.now(): slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return slots

from datetime import datetime, timedelta, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..integrations.whatsapp import send_whatsapp_message


async def send_appointment_reminders(db: Session):

    tomorrow = datetime.now().date() + timedelta(days=1)

    start = datetime.combine(tomorrow, time.min)
    end = datetime.combine(tomorrow + timedelta(days=1), time.min)

    appointments = db.scalars(
        select(models.Appointment).where(
            models.Appointment.status == "confirmed",
            models.Appointment.reminder_sent == False,
            models.Appointment.start_at >= start,
            models.Appointment.start_at < end
        )
    ).all()

    sent_count = 0

    for appointment in appointments:

        customer = db.get(
            models.Customer,
            appointment.customer_id
        )

        service = db.get(
            models.Service,
            appointment.service_id
        )

        if not customer:
            continue

        message = (
            f"Hello {customer.name}!\n\n"
            f"This is a reminder from The Salon Studio.\n"
            f"Your {service.name if service else 'salon'} appointment "
            f"is scheduled for tomorrow at "
            f"{appointment.start_at.strftime('%I:%M %p')}.\n\n"
            f"We look forward to seeing you!"
        )

        try:
            await send_whatsapp_message(
                customer.phone,
                message
            )

            appointment.reminder_sent = True
            db.commit()

            sent_count += 1

        except Exception as exc:
            print(
                f"Reminder failed for appointment "
                f"{appointment.id}: {exc}"
            )

    return sent_count
import logging

from sqlalchemy import select
from .. import models
from ..config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the friendly virtual receptionist for {salon}.
Be concise, warm and professional.
Explain salon services and prices.
Never invent prices or availability.
Never claim an appointment is booked unless confirmed.
Hours: Tuesday-Sunday, 10 AM-8 PM.
Closed Mondays.
""".format(salon=settings.salon_name)


def generate_reply(
    message: str,
    db=None,
    conversation_id: int | None = None
) -> str:

    # Get active salon services
    services = (
        db.scalars(
            select(models.Service).where(
                models.Service.is_active == True
            )
        ).all()
        if db is not None else []
    )

    catalogue = "\n".join(
        f"- {s.name}: ₹{s.price:g} ({s.duration_minutes} min)"
        for s in services
    )

    # Retrieve previous user messages
    previous_messages = []

    if db is not None and conversation_id is not None:

        history = db.scalars(
            select(models.Message)
            .where(
                models.Message.conversation_id == conversation_id,
                models.Message.role == "user"
            )
            .order_by(models.Message.id.desc())
            .limit(6)
        ).all()

        previous_messages = [
            item.content.lower()
            for item in history
        ]

        # Remove the current message from previous history
        if previous_messages and previous_messages[0] == message.lower():
            previous_messages.pop(0)

    text = message.lower()
    context = " ".join(previous_messages)

    # 1. Greeting
    if text.strip() in {
    "hello",
    "hi",
    "hey",
    "hello!",
    "good morning",
    "good afternoon",
    "good evening"
}:
        return (
            f"Hello! Welcome to {settings.salon_name}. "
            "How can I help you today?"
        )

    # 2. Service and price enquiries
    if any(w in text for w in ["price", "service", "offer", "cost", "rate"]):
        return (
            "Here are our current services:\n"
            + catalogue
            + "\nWhich service would you like to know more about?"
        )

    # 3. Hair care recommendations
    if any(w in text for w in [
        "healthy", "shiny", "smooth", "dry hair",
        "damaged hair", "hair care"
    ]):
        return (
            "For healthier, shinier and smoother-looking hair, "
            "I'd recommend considering our Hair Spa. "
            "It may help improve hair softness and manageability. "
            "Would you like to know its price and duration?"
        )

    # 4. Contextual follow-up
    if any(w in context for w in ["hair", "salon", "service"]):
        if any(w in text for w in ["recommend", "suggest", "which", "best"]):
            return (
                "I'd be happy to recommend a service. "
                "Are you looking for hair care, hair styling, "
                "or a facial treatment?"
            )

    # 5. Appointment booking
    if any(w in text for w in [
        "book", "appointment", "slot", "available"
    ]):
        return (
            "I'd be happy to help you book an appointment. "
            "Please share your name, phone number, preferred "
            "service, and requested date and time."
        )

    # 6. Cancellation and rescheduling
    if any(w in text for w in ["cancel", "reschedule", "change"]):
        return (
            "Please share the phone number used for your booking "
            "and the appointment date so we can locate it."
        )

    # 7. Opening hours
    if any(w in text for w in ["hour", "open", "timing", "when"]):
        return (
            "We're open Tuesday to Sunday, 10:00 AM to 8:00 PM. "
            "We're closed on Mondays."
        )

    # 8. Default response
    return (
        f"Welcome to {settings.salon_name}! "
        "I can help you with services, prices, hair care "
        "recommendations and appointments. What would you like to know?"
    )
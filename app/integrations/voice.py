from xml.sax.saxutils import escape
def make_twiml_response(message: str) -> str:
    safe = escape(message)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Say voice="Polly.Aditi" language="en-IN">' + safe +
            '</Say><Gather input="speech" action="/webhooks/twilio/voice" method="POST" speechTimeout="auto">'
            '<Say voice="Polly.Aditi" language="en-IN">How else may I help you?</Say>'
            '</Gather></Response>')

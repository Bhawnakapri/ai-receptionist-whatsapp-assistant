import httpx
from ..config import settings
async def send_whatsapp_message(to: str, text: str):
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return {"sent": False, "reason": "WhatsApp credentials are not configured"}
    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"}
    payload = {"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text}}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

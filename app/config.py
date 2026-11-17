from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_name: str = "AI Receptionist & WhatsApp Assistant"
    database_url: str = "sqlite:///./salon_assistant.db"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    salon_name: str = "The Salon Studio"
    salon_timezone: str = "Asia/Kolkata"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "change-this-token"
    whatsapp_api_version: str = "v22.0"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()

from dataclasses import dataclass


@dataclass
class AngelOneConfig:
    api_key: str
    client_id: str
    client_pin: str
    totp_secret: str | None = None

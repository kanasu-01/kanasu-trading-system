import os
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class AngelOneConfig:
    api_key: str
    client_id: str
    client_pin: str
    totp_secret: str | None = None
    
    # --- REQUIRED for historical API ---
    exchange: str = "NSE"
    symbol_token_map: Dict[str, str] | None = None
    
    @classmethod
    def load_from_env(cls) -> "AngelOneConfig":
        """
        Load AngelOne credentials from environment variables.
        """
        return cls(
            api_key=os.environ["ANGELONE_API_KEY"],
            client_id=os.environ["ANGELONE_CLIENT_ID"],
            client_pin=os.environ["ANGELONE_CLIENT_PIN"],
            totp_secret=os.environ.get("ANGELONE_TOTP_SECRET"),
            exchange=os.environ.get("ANGELONE_EXCHANGE", "NSE"),
            symbol_token_map={
                # TEMP: hardcoded for now (we will improve later)
                "RELIANCE": "2885",
                },
            )
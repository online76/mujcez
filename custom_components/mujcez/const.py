"""Konstanty integrace Můj ČEZ."""

DOMAIN = "mujcez"
PLATFORMS = ["sensor"]

# OAuth2 (WSO2) – stejné hodnoty používá webový portál muj.cez.cz (veřejný klient s PKCE)
AUTHORIZE_URL = "https://auth.cez.cz/oauth2/authorize"
TOKEN_URL = "https://api.cez.cz/token"
CLIENT_ID = "wu2tPrszYcFOKPAA2DUdDehONGAa"
REDIRECT_URI = "https://muj.cez.cz/col/auth-callback"
API_URL = "https://muj.cez.cz/col-api/prod/1.0"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_DEVICE_ID = "device_id"

DATA_INTERVAL_H = 24          # stažení dat z portálu (1× denně, a po startu HA)
TOKEN_INTERVAL_MIN = 10      # udržování přihlášení (access token platí 15 min)

CARD_URL = "/mujcez/mujcez-card.js"
VERSION = "0.1.1"

COMMODITY = {"E1": "elektrina", "P1": "plyn"}

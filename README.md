# BestChoice PC Backend

Projeto inicial em FastAPI para a migracao do backend.

## Requisitos

- Python 3.12+
- `pip`

## Instalar

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Rodar

```bash
uvicorn app.main:app --reload
```

## Variaveis de ambiente

Copie `.env.example` para `.env` e ajuste se necessario.

Variaveis usadas pelo backend:

- `DB_URI`
- `MONGODB_DATABASE`
- `BUSINESS_TIMEZONE`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_DEFAULT_CHANNEL`
- `TELEGRAM_SESSION_PATH`

## Testar

```bash
pytest
```

## Seeder

```bash
python -m app.scripts.seed_cpus
```

## Telegram

```bash
python -m app.scripts.telegram_login
python -m app.scripts.telegram_search "Ryzen 7 9800X3D"
python -m app.scripts.telegram_search "Kabum" --channel @pcbuildwizard --json
python -m app.scripts.sync_daily_offers
```

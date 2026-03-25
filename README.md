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

## Testar

```bash
pytest
```

## Seeder

```bash
python -m app.scripts.seed_cpus
```

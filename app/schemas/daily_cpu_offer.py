from pydantic import BaseModel


class DailyCpuOffer(BaseModel):
    business_date: str
    cpu_sku: str
    cpu_name: str
    store: str
    store_display_name: str
    price_card: float
    installments: int | None = None
    source_url: str | None = None
    telegram_message_id: int | None = None
    telegram_message_url: str | None = None
    posted_at: str | None = None
    lowest_price_90d: float | None = None
    median_price_90d: float | None = None
    raw_text: str

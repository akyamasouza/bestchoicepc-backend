from pydantic import BaseModel


class MotherboardCompatibility(BaseModel):
    desktop: bool
    cpu_brands: list[str]
    sockets: list[str]
    memory_generations: list[str]


class MotherboardListItem(BaseModel):
    id: str
    name: str
    sku: str
    brand: str
    cpu_brand: str | None = None
    socket: str | None = None
    chipset: str | None = None
    form_factor: str | None = None
    memory_generation: str | None = None
    wifi: bool | None = None
    bluetooth: bool | None = None
    compatibility: MotherboardCompatibility


class MotherboardListResponse(BaseModel):
    items: list[MotherboardListItem]
    page: int
    limit: int
    total: int

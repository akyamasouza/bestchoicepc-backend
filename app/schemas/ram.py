from pydantic import BaseModel


class RamCompatibility(BaseModel):
    desktop: bool
    notebook: bool
    platforms: list[str]


class RamListItem(BaseModel):
    id: str
    name: str
    sku: str
    brand: str
    generation: str | None = None
    form_factor: str | None = None
    capacity_gb: int | None = None
    module_count: int | None = None
    capacity_per_module_gb: int | None = None
    speed_mhz: int | None = None
    cl: int | None = None
    rgb: bool | None = None
    profile: str | None = None
    device: str | None = None
    compatibility: RamCompatibility


class RamListResponse(BaseModel):
    items: list[RamListItem]
    page: int
    limit: int
    total: int

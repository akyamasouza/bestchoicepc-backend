import re
from typing import Any

from app.repositories.paged_query import PagedQueryStrategy, execute_paged_query
from app.repositories.protocols import ASCENDING, CollectionProtocol
from app.schemas.ram import RamCompatibility, RamListItem, RamListResponse


class RamRepository:
    def __init__(self, collection: CollectionProtocol) -> None:
        self.collection = collection
        self.list_strategy = PagedQueryStrategy[RamListItem, RamListResponse](
            projection={
                "name": 1,
                "sku": 1,
                "brand": 1,
                "generation": 1,
                "form_factor": 1,
                "capacity_gb": 1,
                "module_count": 1,
                "capacity_per_module_gb": 1,
                "speed_mhz": 1,
                "cl": 1,
                "rgb": 1,
                "profile": 1,
                "device": 1,
                "compatibility": 1,
            },
            build_query_fn=self._build_query,
            map_item_fn=self._to_list_item,
            build_response_fn=self._build_list_response,
            sort_fields="name",
            sort_direction=ASCENDING,
        )

    def list_rams(
        self,
        *,
        brand: str | None = None,
        generation: str | None = None,
        form_factor: str | None = None,
        device: str | None = None,
        capacity_gb: int | None = None,
        module_count: int | None = None,
        speed_mhz: int | None = None,
        profile: str | None = None,
        rgb: bool | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> RamListResponse:
        return execute_paged_query(
            self.collection,
            self.list_strategy,
            filters={
                "brand": brand,
                "generation": generation,
                "form_factor": form_factor,
                "device": device,
                "capacity_gb": capacity_gb,
                "module_count": module_count,
                "speed_mhz": speed_mhz,
                "profile": profile,
                "rgb": rgb,
                "q": q,
            },
            page=page,
            limit=limit,
        )

    def _build_query(
        self,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        brand = filters.get("brand")
        generation = filters.get("generation")
        form_factor = filters.get("form_factor")
        device = filters.get("device")
        capacity_gb = filters.get("capacity_gb")
        module_count = filters.get("module_count")
        speed_mhz = filters.get("speed_mhz")
        profile = filters.get("profile")
        rgb = filters.get("rgb")
        q = filters.get("q")
        query: dict[str, Any] = {}

        if brand is not None:
            query["brand"] = {"$regex": f"^{re.escape(brand.strip())}$", "$options": "i"}
        if generation is not None:
            query["generation"] = generation.strip().upper()
        if form_factor is not None:
            query["form_factor"] = {"$regex": f"^{re.escape(form_factor.strip())}$", "$options": "i"}
        if device is not None:
            query["device"] = {"$regex": f"^{re.escape(device.strip())}$", "$options": "i"}
        if capacity_gb is not None:
            query["capacity_gb"] = capacity_gb
        if module_count is not None:
            query["module_count"] = module_count
        if speed_mhz is not None:
            query["speed_mhz"] = speed_mhz
        if profile is not None:
            query["profile"] = {"$regex": f"^{re.escape(profile.strip())}$", "$options": "i"}
        if rgb is not None:
            query["rgb"] = rgb
        if q is not None and q.strip():
            normalized_query = re.escape(q.strip())
            query["$or"] = [
                {"name": {"$regex": normalized_query, "$options": "i"}},
                {"sku": {"$regex": normalized_query, "$options": "i"}},
            ]

        return query

    @staticmethod
    def _build_list_response(
        items: list[RamListItem],
        page: int,
        limit: int,
        total: int,
    ) -> RamListResponse:
        return RamListResponse(items=items, page=page, limit=limit, total=total)

    def _to_list_item(self, document: dict[str, Any]) -> RamListItem:
        compatibility = document.get("compatibility") or {}
        return RamListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            brand=document["brand"],
            generation=document.get("generation"),
            form_factor=document.get("form_factor"),
            capacity_gb=document.get("capacity_gb"),
            module_count=document.get("module_count"),
            capacity_per_module_gb=document.get("capacity_per_module_gb"),
            speed_mhz=document.get("speed_mhz"),
            cl=document.get("cl"),
            rgb=document.get("rgb"),
            profile=document.get("profile"),
            device=document.get("device"),
            compatibility=RamCompatibility(
                desktop=bool(compatibility.get("desktop")),
                notebook=bool(compatibility.get("notebook")),
                platforms=list(compatibility.get("platforms") or []),
            ),
        )

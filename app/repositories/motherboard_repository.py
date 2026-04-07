import re
from typing import Any

from app.repositories.paged_query import PagedQueryStrategy, execute_paged_query
from app.repositories.protocols import ASCENDING, CollectionProtocol
from app.schemas.motherboard import (
    MotherboardCompatibility,
    MotherboardListItem,
    MotherboardListResponse,
)


class MotherboardRepository:
    def __init__(self, collection: CollectionProtocol) -> None:
        self.collection = collection
        self.list_strategy = PagedQueryStrategy[MotherboardListItem, MotherboardListResponse](
            projection={
                "name": 1,
                "sku": 1,
                "brand": 1,
                "cpu_brand": 1,
                "socket": 1,
                "chipset": 1,
                "form_factor": 1,
                "memory_generation": 1,
                "wifi": 1,
                "bluetooth": 1,
                "compatibility": 1,
            },
            build_query_fn=self._build_query,
            map_item_fn=self._to_list_item,
            build_response_fn=self._build_list_response,
            sort_fields="name",
            sort_direction=ASCENDING,
        )

    def list_motherboards(
        self,
        *,
        brand: str | None = None,
        cpu_brand: str | None = None,
        socket: str | None = None,
        chipset: str | None = None,
        form_factor: str | None = None,
        memory_generation: str | None = None,
        wifi: bool | None = None,
        bluetooth: bool | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> MotherboardListResponse:
        return execute_paged_query(
            self.collection,
            self.list_strategy,
            filters={
                "brand": brand,
                "cpu_brand": cpu_brand,
                "socket": socket,
                "chipset": chipset,
                "form_factor": form_factor,
                "memory_generation": memory_generation,
                "wifi": wifi,
                "bluetooth": bluetooth,
                "q": q,
            },
            page=page,
            limit=limit,
        )

    def _build_query(self, filters: dict[str, Any]) -> dict[str, Any]:
        brand = filters.get("brand")
        cpu_brand = filters.get("cpu_brand")
        socket = filters.get("socket")
        chipset = filters.get("chipset")
        form_factor = filters.get("form_factor")
        memory_generation = filters.get("memory_generation")
        wifi = filters.get("wifi")
        bluetooth = filters.get("bluetooth")
        q = filters.get("q")
        query: dict[str, Any] = {}

        if brand is not None:
            query["brand"] = {"$regex": f"^{re.escape(brand.strip())}$", "$options": "i"}
        if cpu_brand is not None:
            query["cpu_brand"] = {"$regex": f"^{re.escape(cpu_brand.strip())}$", "$options": "i"}
        if socket is not None:
            query["socket"] = {"$regex": f"^{re.escape(socket.strip())}$", "$options": "i"}
        if chipset is not None:
            query["chipset"] = {"$regex": f"^{re.escape(chipset.strip())}$", "$options": "i"}
        if form_factor is not None:
            query["form_factor"] = {"$regex": f"^{re.escape(form_factor.strip())}$", "$options": "i"}
        if memory_generation is not None:
            query["memory_generation"] = memory_generation.strip().upper()
        if wifi is not None:
            query["wifi"] = wifi
        if bluetooth is not None:
            query["bluetooth"] = bluetooth
        if q is not None and q.strip():
            normalized_query = re.escape(q.strip())
            query["$or"] = [
                {"name": {"$regex": normalized_query, "$options": "i"}},
                {"sku": {"$regex": normalized_query, "$options": "i"}},
            ]

        return query

    @staticmethod
    def _build_list_response(
        items: list[MotherboardListItem],
        page: int,
        limit: int,
        total: int,
    ) -> MotherboardListResponse:
        return MotherboardListResponse(items=items, page=page, limit=limit, total=total)

    def _to_list_item(self, document: dict[str, Any]) -> MotherboardListItem:
        compatibility = document.get("compatibility") or {}
        return MotherboardListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            brand=document["brand"],
            cpu_brand=document.get("cpu_brand"),
            socket=document.get("socket"),
            chipset=document.get("chipset"),
            form_factor=document.get("form_factor"),
            memory_generation=document.get("memory_generation"),
            wifi=document.get("wifi"),
            bluetooth=document.get("bluetooth"),
            compatibility=MotherboardCompatibility(
                desktop=bool(compatibility.get("desktop")),
                cpu_brands=list(compatibility.get("cpu_brands") or []),
                sockets=list(compatibility.get("sockets") or []),
                memory_generations=list(compatibility.get("memory_generations") or []),
            ),
        )

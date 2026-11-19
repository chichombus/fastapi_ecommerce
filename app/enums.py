from enum import Enum

class ProductSortField(str, Enum):
    id = "id"
    created_at = "created_at"
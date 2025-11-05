from pydantic import BaseModel, Field


class DataRequest(BaseModel):
    """Product Data request model"""

    product_identifier: str = Field(..., description="Product Identifier")

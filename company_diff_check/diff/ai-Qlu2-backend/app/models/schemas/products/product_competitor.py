from pydantic import BaseModel, Field


class CompetitorRequest(BaseModel):
    """Product Data request model"""

    product_name: str = Field(..., description="Product Name")
    product_identifier: str = Field(..., description="Product Identifier")
    company_name: str = Field(..., description="Company Name")
    company_identifier: str = Field(..., description="Company Identifier")

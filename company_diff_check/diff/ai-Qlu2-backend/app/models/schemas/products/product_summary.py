from pydantic import BaseModel, Field


class SummaryRequest(BaseModel):
    """Summary request model"""

    product_identifier: str = Field(..., description="Product Identifier")
    product_name: str = Field(..., description="Product Name")
    company_identifier: str = Field(..., description="Company Identifier")
    company_name: str = Field(..., description="Company Name")

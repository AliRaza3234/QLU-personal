from pydantic import BaseModel, Field, model_validator
from typing import Optional, Union


class FinancialSummaryRequest(BaseModel):
    """Request body for the company financial summary"""

    id: str = Field(..., min_length=1)
    return_currency: bool = Field(False)


class FinancialSummaryResponse(BaseModel):
    """Response body for the company financial summary"""

    output: Optional[dict] = None


class CompanyOwnershipFilterRequest(BaseModel):
    """Request body for the company financial summary"""

    status: Optional[str] = Field(None, min_length=1)
    filter: Optional[str] = Field(..., min_length=1)


class CompanyOwnershipFilterResponse(BaseModel):
    """Response body for the company financial summary"""

    output: Optional[dict] = None


class FundingFilterRequest(BaseModel):
    """Request body for the company financial summary"""

    founded_date_from: Optional[str] = Field(None)
    founded_date_to: Optional[str] = Field(None)

    last_funding_date_from: Optional[str] = Field(None)
    last_funding_date_to: Optional[str] = Field(None)

    last_funding_type: Optional[str] = Field(None)

    total_funding_amount_from: Optional[int] = Field(None)
    total_funding_amount_to: Optional[int] = Field(None)

    last_funding_amount_from: Optional[int] = Field(None)
    last_funding_amount_to: Optional[int] = Field(None)


class FundingFilterResponse(BaseModel):
    """Response body for the company financial summary"""

    output: Optional[dict] = None


class FinancialDataRequest(BaseModel):
    """Request body for the financial data"""

    id: str = Field(..., min_length=1)
    financial_type: str = Field(..., min_length=3)
    type: str = Field(..., min_length=3)
    return_currency: bool = Field(False)

    @model_validator(mode="after")
    def financial_type_must_be_valid(self):
        """Validate financial type"""
        if self.financial_type not in ["cashflow", "balancesheet", "incomestatement"]:
            raise ValueError(
                "financial_type must be cashflow, balancesheet or incomestatement"
            )
        return self

    @model_validator(mode="after")
    def financial_must_be_valid(self):
        """Validate financial type"""
        if self.type not in ["yearly", "quarterly"]:
            raise ValueError("type must be yearly or quarterly")
        return self


class FinancialDataResponse(BaseModel):
    """Response body for the financial data"""

    output: Optional[dict] = None


class CompanyStocksRequest(BaseModel):
    """Request body for the company stocks"""

    id: str = Field(..., min_length=1)
    return_currency: bool = Field(False)


class CompanyStocksResponse(BaseModel):
    """Response body for the company stocks"""

    output: Optional[dict] = None


class MergerAcquisitionsRequest(BaseModel):
    """Request body for the company stocks"""

    cb_url: str = Field(..., min_length=1)


class MergerAcquisitionsResponse(BaseModel):
    """Response body for the company stocks"""

    output: Optional[list] = None


class CompanyNewsRequest(BaseModel):
    """Request body for the company news"""

    id: str = Field(..., min_length=1)


class CompanyNewsResponse(BaseModel):
    """Response body for the company news"""

    output: Optional[list] = None


class CbUrlResponse(BaseModel):
    """Response body for the company news"""

    cb_url: Optional[str] = None


class CompanyReportLinkInput(BaseModel):
    """Request body for the company report link"""

    universalName: str


class CompanyReportLinkOutput(BaseModel):
    """Response body for the company report link"""

    def_14: Optional[str] = None
    k_10: Optional[str] = None
    q_10: Optional[str] = None
    k_8: Optional[str] = None


class ProductsRequest(BaseModel):
    """Request body for products generation"""

    universalName: str


class ProductsResponse(BaseModel):
    """Response body for products generation"""

    products: Optional[list] = None


class ProductInfoRequest(BaseModel):
    """Request body for products generation"""

    universalName: str
    product_name: str


class ProductInfoResponse(BaseModel):
    """Response body for products generation"""

    info: Optional[str] = None
    market_orientation: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None


class PrivateCompaniesRequest(BaseModel):

    cb_url: str


class PrivateCompaniesResponse(BaseModel):
    output: Union[dict, list]

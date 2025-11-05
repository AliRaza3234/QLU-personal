from pydantic import BaseModel


class FinancialFiltersRequest(BaseModel):
    """Request body for company financial filters"""

    payload: dict


class FinancialFiltersResponse(BaseModel):
    """Response body for company financial filters"""

    isSuccess: bool
    result: dict

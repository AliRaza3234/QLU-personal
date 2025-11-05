from pydantic import BaseModel, Field, model_validator


class AICompanySearchRequest(BaseModel):
    """Request body for the ai Company search"""

    text: str = Field(..., min_length=5)
    filter_type: str

    @model_validator(mode="after")
    def validate_filter_type(self):
        allowed_values = set(
            [
                "industry",
                "headquarters",
                "company_size",
                "m_and_a",
                "ownership_status",
                "market_cap",
                "revenue",
                "revenueGrowth",
                "earnings",
                "stock_filter",
                "last_funding_date",
                "last_funding_type",
                "last_funding_amount",
                "total_funding_amount",
                "investors",
                "estimated_revenue",
                "shared_investors",
            ]
        )
        if self.filter_type.lower() not in allowed_values:
            raise ValueError(f"filter_type must be one of {allowed_values}")
        return self


class AICompanyIdRequest(BaseModel):
    """Request body for the IDs of ai search of Companies"""

    text: str = Field(..., min_length=5)

    def validate_filter_type(self):
        return self


class CompanyIdOutput(BaseModel):
    entity_list: list

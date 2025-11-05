from pydantic import BaseModel


class CompanyAndOrRequest(BaseModel):
    """Class for input payload"""

    userquery: str
    companies: list


class CompanyAndOrResponse(BaseModel):
    """Class for output payload"""

    decision: str

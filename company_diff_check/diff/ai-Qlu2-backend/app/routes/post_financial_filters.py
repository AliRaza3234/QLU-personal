# from fastapi import APIRouter
# from fastapi.responses import JSONResponse
# import traceback
# from qutils.slack.notifications import send_slack_notification

# from app.utils.financials.financials_query import main as financial_filters_query
# from app.models.schemas.financial_filters import (
#     FinancialFiltersRequest,
#     FinancialFiltersResponse,
# )

# router = APIRouter()


# @router.post("/financial_filters", response_model=FinancialFiltersResponse)
# async def financial_filters(request: FinancialFiltersRequest):
#     payload = request.payload
#     try:
#         result = await financial_filters_query(payload)
#         result = {"isSuccess": True, "result": result}
#         output = FinancialFiltersResponse(**result)
#         return output
#     except Exception as e:
#         print("Exception: ", e)
#         traceback.print_exc()
#         error_trace = traceback.format_exc()
#         await send_slack_notification(
#             traceback=error_trace,
#             payload=request,
#             route="financial_filters",
#             service_name="FINANCIAL FILTERS",
#         )
#         return JSONResponse(status_code=500, content={"message": f"Error {e}"})

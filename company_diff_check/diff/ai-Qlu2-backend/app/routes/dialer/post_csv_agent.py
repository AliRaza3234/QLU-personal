import traceback
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.csv_agent import CSVProcessingResponse
from app.utils.dialer.services.csv_agents import processing_csv
from qutils.slack.notifications import send_slack_notification
import csv
import io

router = APIRouter()


@router.post("/process-csv/", response_model=CSVProcessingResponse)
async def process_csv(file: UploadFile = File(...)):
    try:
        result = await processing_csv(file)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        file_content = await file.read()
        file.seek(0)
        csv_reader = csv.reader(io.StringIO(file_content.decode("utf-8")))
        first_5_rows = [row for _, row in zip(range(5), csv_reader)]

        await send_slack_notification(
            traceback=error_trace,
            payload=first_5_rows,
            route="process-csv",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})

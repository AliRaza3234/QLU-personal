import json
import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.core.database import postgres_fetch, postgres_insert
from app.utils.dialer.services.generate_metrics.get_metrics import getMetrics
from app.utils.dialer.services.generate_threshold.gen_threshold import getThresholds
from app.utils.dialer.utils.metric_utils.metric_utils import (
    getFinalMetrics,
    compareMetrics,
    parsing_metrics,
)
from app.models.schemas.dialer.generate_metrics import (
    GenerateMetricsRequest,
    GenerateMetricsResponse,
)
from qutils.slack.notifications import send_slack_notification

TABLE_NAME = "cached_dialer_metrics"

router = APIRouter()


@router.post("/gen_metrics", response_model=GenerateMetricsResponse)
async def generate_metrics(req: GenerateMetricsRequest):
    try:
        msg = req.text
        category = req.category
        category = category.strip()
        isUpdated = True
        updateThreshold = False

        globalMetrics = await postgres_fetch(
            f"SELECT metric from {TABLE_NAME} where label ilike '{category}'"
        )
        if globalMetrics:
            globalMetrics = globalMetrics[0]
            if len(globalMetrics) == 6:
                isUpdated = False
                metrics = parsing_metrics(globalMetrics, True)
                thresholds = await postgres_fetch(
                    f"SELECT metric_thresholds from {TABLE_NAME} where label ilike '{category}'"
                )
                if thresholds:
                    thresholds = thresholds[0]
                    thresholds = parsing_metrics(thresholds, True)
                else:
                    thresholds = await getThresholds(category, metrics)
                    try:
                        thresholds = thresholds.replace("'", '"')
                        await postgres_insert(
                            f"UPDATE {TABLE_NAME} SET metric_thresholds = '{thresholds}' WHERE label ilike '{category}'"
                        )
                    except Exception as e:
                        print("Threshold Insertion Failed: {e}")
            else:
                fetchedMetrics = parsing_metrics(globalMetrics, True)
                metrics = await getMetrics(category)

                metrics = json.loads(metrics)
                dct = {metric: metrics[metric] for metric in metrics}
                for metric in globalMetrics:
                    dct[metric] = globalMetrics[metric]
                metricsNames = await compareMetrics(fetchedMetrics, str(metrics))
                metricsNames = json.loads(metricsNames)
                finalDct = {}
                for metric in metricsNames["Metrics"]:
                    finalDct[metric] = dct[metric]
                metrics = await getFinalMetrics(msg, category, str(finalDct))
                metrics = json.loads(metrics)
                dct = {}
                for metric in metrics["Metrics"]:
                    dct[metric] = finalDct[metric]
                metrics = dct
            if isUpdated:
                if len(metrics) == 6:
                    updateThreshold = True
                metrics = parsing_metrics(metrics, False)
                thresholds = await getThresholds(category, metrics)
                if updateThreshold:
                    thresholds = thresholds.replace("'", '"')
                    await postgres_insert(
                        f"UPDATE {TABLE_NAME} SET metric_thresholds = '{thresholds}' WHERE label ilike '{category}'"
                    )

                await postgres_insert(
                    f"UPDATE {TABLE_NAME} SET metric = '{metrics}' WHERE label ilike '{category}'"
                )
                isUpdated = False
        else:
            metrics = await getMetrics(category)
            metrics = json.loads(metrics)
            finalDct = {metric: metrics[metric] for metric in metrics}
            metrics = await getFinalMetrics(msg, category, str(metrics))
            metrics = json.loads(metrics)
            dct = {}
            for metric in metrics["Metrics"]:
                dct[metric] = finalDct[metric]
            metrics = dct
        if isUpdated:
            if len(metrics) == 6:
                updateThreshold = True
            metrics = parsing_metrics(metrics, False)
            thresholds = await getThresholds(category, metrics)
            if updateThreshold:
                thresholds = thresholds.replace("'", '"')
                await postgres_insert(
                    f"INSERT INTO {TABLE_NAME} (label, metric, metric_thresholds) VALUES ('{category}', '{metrics}', '{thresholds}')"
                )
            else:
                await postgres_insert(
                    f"INSERT INTO {TABLE_NAME} (label, metric) VALUES ('{category}', '{metrics}')"
                )
        if isinstance(metrics, str):
            metrics = json.loads(metrics)
        if isinstance(thresholds, str):
            thresholds = json.loads(thresholds)
        for key in thresholds:
            if thresholds[key] < 1:
                thresholds[key] = thresholds[key] * 100

        return JSONResponse(
            status_code=200, content={"metrics": metrics, "thresholds": thresholds}
        )
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=req,
            route="gen_metrics",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})

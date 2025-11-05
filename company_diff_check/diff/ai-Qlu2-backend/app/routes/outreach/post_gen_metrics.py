import json
import asyncio
from fastapi import APIRouter, HTTPException
import traceback

from qutils.slack.notifications import send_slack_notification
from fastapi.responses import JSONResponse

from app.core.database import postgres_fetch, postgres_insert
from app.utils.outreach.services.generate_metrics.get_metrics import getMetrics
from app.utils.outreach.services.generate_threshold.gen_threshold import getThresholds
from app.utils.outreach.utils.metric_utils.metric_utils import (
    getFinalMetrics,
    compareMetrics,
    parsing_metrics,
    thresholdValidate,
    getToolTip,
)
from app.models.schemas.outreach.generate_metrics import (
    GenerateMetricsRequest,
    GenerateMetricsResponse,
)

TABLE_NAME = "cached_outreach_metrics"

router = APIRouter()


@router.post("/gen_metrics", response_model=GenerateMetricsResponse)
async def generate_metrics(req: GenerateMetricsRequest):
    try:
        msg = req.text
        category = req.category
        category = category.strip()
        isUpdated = True
        updateThreshold = False
        # start = time.time()
        # print("HERE")
        globalMetrics = await postgres_fetch(
            f"SELECT metric from {TABLE_NAME} where label ilike '{category}'"
        )
        # print("FETCHING", time.time() - start)
        if globalMetrics:
            globalMetrics = globalMetrics[0]
            # print(globalMetrics)
            # print(type(globalMetrics))
            if len(globalMetrics) == 6:
                # print("TAKING FROM CACHE")
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
                        # start = time.time()
                        await postgres_insert(
                            f"UPDATE {TABLE_NAME} SET metric_thresholds = '{thresholds}' WHERE label ilike '{category}'"
                        )
                    except Exception as e:
                        print("Threshold Insertion Failed: {e}")
            else:
                fetchedMetrics = parsing_metrics(globalMetrics, True)
                # start = time.time()
                metrics = await getMetrics(category)
                # print("Generating", time.time() - start)
                # print(metrics)
                metrics = json.loads(metrics)
                dct = {metric: metrics[metric] for metric in metrics}
                for metric in globalMetrics:
                    dct[metric] = globalMetrics[metric]
                # start = time.time()
                metricsNames = await compareMetrics(fetchedMetrics, str(metrics))
                # print("Comparison", time.time() - start)
                metricsNames = json.loads(metricsNames)
                finalDct = {}
                for metric in metricsNames["Metrics"]:
                    finalDct[metric] = dct[metric]
                # start = time.time()
                metrics = await getFinalMetrics(msg, category, str(finalDct))
                # print("Final Metrics", time.time() - start)
                metrics = json.loads(metrics)
                dct = {}
                for metric in metrics["Metrics"]:
                    dct[metric] = finalDct[metric]
                metrics = dct
                # print("TAKING FROM CACHE AND GENERATING")
            if isUpdated:
                if len(metrics) == 6:
                    updateThreshold = True
                metrics = parsing_metrics(metrics, False)
                # start = time.time()
                thresholds = await getThresholds(category, metrics)
                # print("Gen Thresholds", time.time() - start)
                if updateThreshold:
                    thresholds = thresholds.replace("'", '"')
                    # start = time.time()
                    await postgres_insert(
                        f"UPDATE {TABLE_NAME} SET metric_thresholds = '{thresholds}' WHERE label ilike '{category}'"
                    )
                    # print("thresholds update", time.time() - start)
                # start = time.time()
                await postgres_insert(
                    f"UPDATE {TABLE_NAME} SET metric = '{metrics}' WHERE label ilike '{category}'"
                )
                # print("Metrics update", time.time() - start)
                isUpdated = False
                # print("TABLE UPDATED")
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
            # print("GENERATING")
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
            # print("TABLE POPULATED")
        if isinstance(metrics, str):
            metrics = json.loads(metrics)
            # print("HERE")
        if isinstance(thresholds, str):
            # print(thresholds)
            thresholds = json.loads(thresholds)
        for key in thresholds:
            if thresholds[key] < 1:
                thresholds[key] = thresholds[key] * 100
        for key in thresholds:
            if thresholds[key] > 35:
                thresholds[key] = thresholdValidate(thresholds[key])
        tasks = []
        for metric in metrics:
            tasks.append(getToolTip(category, metric))
        toolTips = await asyncio.gather(*tasks)
        toolTips = {i: j for i, j in zip(metrics, toolTips)}
        # print("HERE2")
        # metrics = [metric for metric in metrics]
        # print("DONE")
        return JSONResponse(
            status_code=200,
            content={
                "metrics": metrics,
                "thresholds": thresholds,
                "definition": toolTips,
            },
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=req,
            route="gen_metrics",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})

from bs4 import BeautifulSoup
from fastapi import HTTPException
from app.core.database import postgres_fetch
from app.utils.company.business_units.utils import (
    get_sec_bucket,
    label_reports_with_quarters,
    generate_all_comma_formats,
    extract_content_from_text,
)


async def get_sec_doc_from_doc_store(cik, year, period):

    bucket = await get_sec_bucket()

    report_type = None
    if period == 0:
        report_type = "10-K"
    elif period in [1, 2, 3, 4]:
        report_type = "10-Q"
    else:
        raise HTTPException(status_code=400, detail="Invalid period")

    if report_type == "10-K":
        years_temp_list = [1, 2, 0]
        for i in years_temp_list:
            gcs_folder_path = f"{cik}/{year + (i)}/"
            blobs = bucket.list_blobs(prefix=gcs_folder_path)
            for blob in blobs:
                file_name = blob.name
                if f"-{report_type}-" in file_name:
                    blob = bucket.blob(blob.name)
                    contents = blob.download_as_bytes()
                    if "ix:resources" in str(contents.decode("utf-8")):
                        return contents.decode("utf-8")
    else:
        for i in range(2):
            doc_names = []
            gcs_folder_path = f"{cik}/{year + i}/"
            blobs = bucket.list_blobs(prefix=gcs_folder_path)
            for blob in blobs:
                file_name = blob.name
                if f"-{report_type}-" in file_name:
                    doc_names.append(file_name)

            quarter_labelled_docs = label_reports_with_quarters(doc_names)

            if doc_names:
                download_doc = quarter_labelled_docs.get(period)
                if download_doc:
                    blob = bucket.blob(download_doc)
                    contents = blob.download_as_bytes()
                    if "ix:resources" in str(contents.decode("utf-8")):
                        return contents.decode("utf-8")

    raise HTTPException(status_code=404, detail="SEC DOC not found")


def extract_tables(form, label, value, bu_name, consolidated=False):

    possible_formats_with_commas = generate_all_comma_formats(value)

    soup = BeautifulSoup(form, "xml")

    tag = soup.find("ix:resources")
    if not tag:
        raise HTTPException(
            status_code=404,
            detail="Couldn't find tag: ix:resources for the requested parameters",
        )

    context_tags = tag.find_all("xbrli:context")
    if not context_tags:
        raise HTTPException(
            status_code=404,
            detail="Couldn't find tag: xbrli:context for the requested parameters",
        )

    context_ids = []
    sub_labels = label.split(",")
    for tag in context_tags:
        append_flag = True
        for label in sub_labels:
            if f"{label}" not in tag.text:
                append_flag = False
        if append_flag:
            context_ids.append(tag["id"])

    tables = []
    for ind, id in enumerate(context_ids):

        non_fraction_tag = soup.find("ix:nonFraction", contextRef=id)
        if non_fraction_tag:
            table_tag = non_fraction_tag.find_parent("table")
            table_text = str(table_tag)
            if (
                any(format in table_text for format in possible_formats_with_commas)
                or consolidated
            ):
                if str(table_tag) not in tables:
                    tables.append(str(table_tag))
    payload = {"tables": [], "paragraphs": []}
    if tables:
        payload["tables"] = tables

    p_list = extract_content_from_text(soup, bu_name, value)
    if p_list:
        payload["paragraphs"] = p_list

    if payload["tables"] or payload["paragraphs"]:
        return payload
    else:
        raise HTTPException(
            status_code=404,
            detail="Couldn't find the matching value for the requested revenue",
        )


async def trace_bu(li_universal_name, bu_name, year, period, value, container):
    fetch_query = f"""
        select stock_symbol from bu_revenue_all bra where universal_name = '{li_universal_name}'
    """
    response = await postgres_fetch(fetch_query)
    if response:
        stock_symbol = response[0]
    else:
        raise HTTPException(
            status_code=404, detail="Stock Sybmol not found for this universal name"
        )

    fetch_query = f"""
        SELECT cik from stocksciks where stocksymbol = '{stock_symbol}'
    """
    response = await postgres_fetch(fetch_query)
    if response:
        cik = response[0]
    else:
        raise HTTPException(
            status_code=404, detail="CIK not found for this universal name"
        )

    form = await get_sec_doc_from_doc_store(
        cik,
        year,
        period,
    )
    if len(container) == 1:
        label = container[0]["label"]
        payload = extract_tables(form, label, value, bu_name)

    else:
        payload = {"tables": [], "paragraphs": []}
        for element in container:
            label = element["label"]
            result = extract_tables(form, label, value, bu_name, consolidated=True)
            if result["tables"] and result["tables"] not in payload["tables"]:
                payload["tables"].append(result["tables"])

            if (
                result["paragraphs"]
                and result["paragraphs"] not in payload["paragraphs"]
            ):
                payload["paragraphs"].append(result["paragraphs"])

    return payload

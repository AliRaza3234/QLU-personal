import json, re
from itertools import product


def build_all_search_strings(data):
    return None
    names = data.get("names", [])
    titles = data.get("titles", [])
    companies = data.get("companies", [])
    locations = data.get("locations", [])

    # Replace empty lists with empty string for product to work correctly
    names = names or [""]
    titles = titles or [""]
    companies = companies or [""]
    locations = locations or [""]

    results = []

    for name, title, company, location in product(names, titles, companies, locations):
        parts = []

        if name:
            parts.append(name)
        if title:
            parts.append(title)
        if company:
            parts.append(f"at {company}")
        if location:
            parts.append(f"in {location}")

        search_string = " ".join(parts)
        if search_string:  # ignore completely empty combinations
            results.append(search_string)

    return results


def context_transformation(response, demoBlocked=False):
    key_mapping = {
        "job_role": "jobRole",
        "company_industry_product": "companyProduct",
        "company_product": "companyProduct",
        "total_working_years": "totalYears",
        "name": "educName",
        "education": "educName",
        "skills": "skill",
    }

    allowed_filters = [
        "jobRole",
        "companyProduct",
        "totalYears",
        "educName",
        "skill",
        "industry",
        "location",
        "name",
        "ownership",
    ]
    if not demoBlocked:
        allowed_filters.append("demographics")

    if "attributes" in response:
        filters = [
            key_mapping[key] if key in key_mapping else key
            for key in response["attributes"]
        ]

        response["attributes"] = [item for item in filters if item in allowed_filters]

        response["attributes"] = list(set(response["attributes"]))

        return response


def group_entity_steps(steps):
    plan = []
    current_entity = []

    for step in steps:
        if step["step"] == "entity_complete":
            if current_entity:
                plan.append(current_entity)
                current_entity = []
        else:
            current_entity.append(step)

    if current_entity:
        if plan[-1]:
            plan[-1] += current_entity
        else:
            plan.append(current_entity)
    return plan


def transform_context(context, flag=False, demoBlocked=False):
    """
    Transforms a context dictionary into a human-readable string format.

    Args:
        context (dict): The context dictionary containing various attributes.
        flag (bool, optional): Flag to enable industry processing. Defaults to False.
        demoBlocked (bool, optional): Flag to disable demographics processing. Defaults to False.

    Returns:
        str: A formatted string representing the context data.
    """
    total_text_to_generate = ""
    if not isinstance(context, dict):
        return ""

    transformed = {}

    # Transform title

    title_data = context.get("title", {})
    if isinstance(title_data, dict):
        transformed["title"] = {
            "event": title_data.get("event", ""),
            "filter": list(title_data.get("filter", {}).keys()),
        }
    else:
        transformed["title"] = {"event": "", "filter": []}

    # Transform management_level
    mgmt_data = context.get("management_level", {})
    if isinstance(mgmt_data, dict) and mgmt_data.get("filter"):
        transformed["management_level"] = {
            "event": mgmt_data.get("event", ""),
            "filter": list(mgmt_data.get("filter", {}).keys()),
        }
    else:
        transformed["management_level"] = {}

    total_text_to_generate += f"""job_role Attribute == title: {transformed.get("title")}, management_level: {transformed.get("management_level")}\n"""

    # if flag:
    industry = context.get("industry", {})
    if isinstance(industry, dict) and industry.get("filter"):
        transformed["industry"] = {"event": industry.get("event", "")}
        transformed["industry"]["excluded"] = [
            item
            for item in industry.get("filter", {}).keys()
            if industry.get("filter", {}).get(item, {}).get("exclusion")
        ]
        transformed["industry"]["included"] = [
            item
            for item in industry.get("filter", {}).keys()
            if item not in transformed["industry"]["excluded"]
        ]
    else:
        transformed["industry"] = {}

    if flag:
        total_text_to_generate += (
            f"""industry Attribute: {transformed.get("industry")}\n"""
        )

    simple_fields = ["name", "education", "school", "ownership"]
    for field in simple_fields:
        value = context.get(field, [])
        transformed[field] = value if isinstance(value, list) else []

    total_text_to_generate += f"""name attribute == {transformed.get("name")}\n"""
    total_text_to_generate += (
        f"""ownership attribute == {transformed.get("ownership")}\n"""
    )
    total_text_to_generate += f"""education attribute == School: {transformed.get("school")}, educ: {transformed.get("education")}\n"""

    # Transform numeric range fields
    range_fields = ["experience", "role_tenure", "company_tenure"]
    for field in range_fields:
        field_data = context.get(field, {})
        if isinstance(field_data, dict) and "min" in field_data and "max" in field_data:
            try:
                transformed[field] = f"{field_data['min']}-{field_data['max']}"
            except (TypeError, ValueError):
                transformed[field] = {}
        else:
            transformed[field] = {}

    total_text_to_generate += f"""total_working_years Attribute == experience: {transformed.get("experience")}, role tenure: {transformed.get("role_tenure")}, company tenure: {transformed.get("company_tenure")}\n"""
    # Transform location
    location_data = context.get("location", {})
    transformed["location"] = location_data if isinstance(location_data, dict) else {}
    total_text_to_generate += (
        f"""location Attribute = {transformed.get("location")}\n"""
    )
    # Transform skills
    skill_data = context.get("skill", {})
    if isinstance(skill_data, dict) and isinstance(skill_data.get("filter"), dict):
        transformed["skill"] = {}
        transformed["skill"]["Included skills"] = list(
            key
            for key, value in skill_data.get("filter", {}).items()
            if value.get("state", "") == "include"
        )
        # transformed["skill"]["Must have skills"] = list(
        #     key
        #     for key, value in skill_data.get("filter", {}).items()
        #     if value.get("state", "") == "must-include"
        # )
        transformed["skill"]["Excluded skills"] = list(
            key
            for key, value in skill_data.get("filter", {}).items()
            if value.get("state", "") == "exclude"
        )
    else:
        transformed["skill"] = []

    total_text_to_generate += f"""skill Attribute = {transformed.get("skill")}\n"""

    # Add gender if present ,
    # Transform simple list fields
    if not demoBlocked:
        simple_fields_demo = ["age", "ethnicity"]
        for field in simple_fields_demo:
            value = context.get(field, [])
            transformed[field] = value if isinstance(value, list) else []

        gender = context.get("gender")
        if gender:
            transformed["gender"] = gender

        total_text_to_generate += f"""demographics Attribute == gender: {transformed.get("gender")}, age: {transformed.get("age")}, ethnicity: {transformed.get("ethnicity")}\n"""

    companies = context.get("companies")
    transformed["companies"] = {"current": [], "past": [], "event": ""}
    if companies:
        current_prompts = []
        past_prompts = []

        for item in companies["current"]:
            # transformed["companies"]["current"] += item["prompt"]
            if any(comp.get("state") == "selected" for comp in item.get("pills")):
                current_prompts.append(item["prompt"])
        for item in companies["past"]:
            # transformed["companies"]["past"] += item["prompt"]
            if any(comp.get("state") == "selected" for comp in item.get("pills")):
                past_prompts.append(item["prompt"])

        transformed["companies"]["event"] = companies["event"]
        transformed["companies"]["current"] = "".join(current_prompts)
        transformed["companies"]["past"] = "".join(past_prompts)

    products = context.get("products")
    transformed["products"] = {"current": [], "past": [], "event": ""}
    if products:
        transformed["products"]["current"] = ""
        transformed["products"]["past"] = ""

        for item in products["current"]:
            transformed["products"]["current"] += (
                item["prompt"]
                if any(prod.get("state") == "selected" for prod in item.get("pills"))
                else ""
            )
        for item in products["past"]:
            transformed["products"]["past"] += (
                item["prompt"]
                if any(prod.get("state") == "selected" for prod in item.get("pills"))
                else ""
            )
        transformed["products"]["event"] = products["event"]

    if flag:
        total_text_to_generate += "company_product Attribute"
    else:
        total_text_to_generate += "company_industry_product Attribute"
    total_text_to_generate += f""" == companies: {transformed.get("companies")}, products: {transformed.get("products")}"""
    if not flag and transformed.get("industry"):
        total_text_to_generate += f""", industries: {transformed.get("industry")}\n"""

    return total_text_to_generate


def convert_companies(
    companiesCurrent=[], companiesPast=[], previous_companies={}, event="AND"
):
    def extract_pills(company_list):
        pills = []
        for item in company_list:
            es_data = item.get("es_data", {})
            pills.append(
                {
                    "id": str(es_data["es_id"]) if es_data.get("es_id") else "",
                    "name": es_data["name"] if es_data.get("name") else "",
                    "industry": es_data["industry"] if es_data.get("industry") else "",
                    "universalName": (
                        es_data["universalName"] if es_data.get("universalName") else ""
                    ),
                    "urn": es_data["urn"] if es_data.get("urn") else None,
                    "employCount": (
                        int(float(es_data["employCount"]))
                        if es_data.get("employCount")
                        else 0
                    ),
                    "state": "selected",
                }
            )

        return pills

    if event.lower() == "past":
        companiesCurrent = companiesPast
        companiesPast = []
    elif event.lower() == "or":
        companiesCurrent += companiesPast
        companiesPast = []

    current_formatted = extract_pills(companiesCurrent)
    past_formatted = extract_pills(companiesPast)

    if previous_companies.get("current"):
        current_pills = previous_companies["current"][-1].get("pills", [])
        current_pills = [
            item for item in current_pills if item.get("state", "") == "selected"
        ]
        current_pills += current_formatted
        previous_companies["current"][-1]["pills"] = current_pills

    if previous_companies.get("past"):
        past_pills = previous_companies["past"][-1].get("pills", [])
        past_pills = [
            item for item in past_pills if item.get("state", "") == "selected"
        ]
        past_pills += past_formatted
        previous_companies["past"][-1]["pills"] = past_pills

    return previous_companies


def last_converter(payload):
    last = f"data: {json.dumps({'event': payload}, ensure_ascii=False)}\n\n"
    return last


def extract_generic(start: str, end: str, text: str):
    match = re.search(rf"{start}(.*?){end}", text, re.DOTALL)
    return match.group(1) if match else None

import asyncio
from app.utils.search.aisearch.company.generation.elastic import (
    get_company_source,
)


async def get_companies_by_industry(
    industries: dict[str, list[str]],
    industry_keywords: list[str],
    locations: list[dict[str, str]],
    employee_lower: int,
    employee_upper: int,
    company_ownership_status: list[str],
    generated_companies: list[str],
    es_client,
):
    """
    Fetch companies from Elasticsearch matching:
      - At least two different industry terms, each matched in at least two of:
        li_industries, li_specialties, li_description.
      - Any of the provided locations (country/state/city), matching all non-empty
        fields per location.
      - Staff count between employee_lower and employee_upper (with a min of 10 if
        upper > 50 and lower == 0).
      - Excluding any in generated_companies.
      - Optionally filtering by ownership status via a post_filter lookup.
    """
    must_clauses: list[dict] = []

    if industries:
        higher_level = [i.lower() for i in industries.keys()]
    else:
        higher_level = []
    industry_keywords = list(set(industry_keywords + higher_level))

    if industry_keywords:
        per_industry_clauses = []
        for term in industry_keywords:
            per_industry_clauses.append(
                {
                    "bool": {
                        "should": [
                            {"match_phrase": {"li_industries": term}},
                            {"match_phrase": {"li_specialties": term}},
                            {"match_phrase": {"li_description": term}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )

        must_clauses.append(
            {"bool": {"should": per_industry_clauses, "minimum_should_match": 2}}
        )

    location_clauses = []
    locations = locations.get("location", [])

    for loc in locations:
        locality = loc.get("locality", "")

        if locality == "H":
            sub_clauses = []
            if loc.get("country"):
                sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.country.keyword": {"query": loc["country"]}
                        }
                    }
                )
            if loc.get("state"):
                sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.geographicArea.keyword": {
                                "query": loc["state"]
                            }
                        }
                    }
                )
            if loc.get("city"):
                sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.city.keyword": {"query": loc["city"]}
                        }
                    }
                )

            if sub_clauses:
                location_clauses.append(
                    {
                        "nested": {
                            "path": "li_headquarter",
                            "query": {"bool": {"must": sub_clauses}},
                        }
                    }
                )

        elif locality == "B":
            headquarter_sub_clauses = []
            confirmed_sub_clauses = []

            if loc.get("country"):
                headquarter_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.country.keyword": {"query": loc["country"]}
                        }
                    }
                )
                confirmed_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.country": {"query": loc["country"]}
                        }
                    }
                )

            if loc.get("state"):
                headquarter_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.geographicArea.keyword": {
                                "query": loc["state"]
                            }
                        }
                    }
                )
                confirmed_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.geographicArea": {
                                "query": loc["state"]
                            }
                        }
                    }
                )

            if loc.get("city"):
                headquarter_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.city.keyword": {"query": loc["city"]}
                        }
                    }
                )
                confirmed_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.city": {"query": loc["city"]}
                        }
                    }
                )

            location_should_clauses = []

            if headquarter_sub_clauses:
                location_should_clauses.append(
                    {
                        "nested": {
                            "path": "li_headquarter",
                            "query": {"bool": {"must": headquarter_sub_clauses}},
                        }
                    }
                )

            if confirmed_sub_clauses:
                location_should_clauses.append(
                    {
                        "nested": {
                            "path": "li_confirmedlocations",
                            "query": {"bool": {"must": confirmed_sub_clauses}},
                        }
                    }
                )

            if location_should_clauses:
                location_clauses.append(
                    {
                        "bool": {
                            "should": location_should_clauses,
                            "minimum_should_match": 1,
                        }
                    }
                )

        else:
            sub_clauses = []
            if loc.get("country"):
                sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.country": {"query": loc["country"]}
                        }
                    }
                )
            if loc.get("state"):
                sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.geographicArea": {
                                "query": loc["state"]
                            }
                        }
                    }
                )
            if loc.get("city"):
                sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.city": {"query": loc["city"]}
                        }
                    }
                )

            if sub_clauses:
                location_clauses.append(
                    {
                        "nested": {
                            "path": "li_confirmedlocations",
                            "query": {"bool": {"must": sub_clauses}},
                        }
                    }
                )

    if location_clauses:
        if len(location_clauses) == 1:
            must_clauses.append(location_clauses[0])
        else:
            must_clauses.append(
                {"bool": {"should": location_clauses, "minimum_should_match": 1}}
            )
    else:
        must_clauses.append(
            {
                "nested": {
                    "path": "li_confirmedlocations",
                    "query": {
                        "bool": {
                            "should": [
                                {
                                    "match_phrase": {
                                        "li_confirmedlocations.country": {"query": "US"}
                                    }
                                }
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                }
            }
        )

    if employee_upper > 50 and employee_lower == 0:
        employee_lower = 10

    if employee_lower or employee_upper:
        must_clauses.append(
            {
                "range": {
                    "li_staffcount": {
                        "gte": employee_lower,
                        "lte": employee_upper,
                    }
                }
            }
        )

    if generated_companies:
        must_clauses.append(
            {"bool": {"must_not": {"terms": {"li_universalname": generated_companies}}}}
        )

    if len(company_ownership_status) == 4:
        company_ownership_status = []
    else:
        company_ownership_status.sort()
        company_ownership_status = "_".join(company_ownership_status)

    es_query = {
        "query": {"bool": {"must": must_clauses}},
        "_source": [
            "li_universalname",
            "li_industries",
            "li_name",
            "li_urn",
            "li_staffcount",
            "li_size",
        ],
        "sort": [{"li_staffcount": {"order": "desc"}}],
        "size": max(0, 50 - len(generated_companies)),
    }

    if company_ownership_status:
        es_query["post_filter"] = {
            "terms": {
                "li_universalname": {
                    "index": "company_ownership",
                    "id": company_ownership_status,
                    "path": "company_universal_name",
                }
            }
        }

    es_res = await es_client.search(index="company", body=es_query)
    companies = []

    if es_res and es_res.get("hits", {}).get("hits"):
        tasks = [
            get_company_source(item["_id"], item["_source"])
            for item in es_res["hits"]["hits"]
        ]
        sources = await asyncio.gather(*tasks)
        companies = [
            {
                "es_data": source,
                "list": source["name"],
                "excluded": False,
                "type": "",
            }
            for source in sources
        ]

    return companies

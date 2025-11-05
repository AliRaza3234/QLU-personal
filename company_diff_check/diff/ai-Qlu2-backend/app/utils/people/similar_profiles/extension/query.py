import os


def company_keywords_clauses(keywords):
    keywords = list(set(keywords))
    words = []
    for key in keywords:
        words.append({"match": {"experience.title": {"query": key, "operator": "or"}}})
        words.append({"match": {"headline": {"query": key, "operator": "or"}}})
    return words


def get_exclude_queries():
    exclude_queries = []

    exclude_queries.append({"exists": {"field": "experience.end"}})
    exclude_queries.append({"match_phrase": {"experience.title": "to the"}})
    exclude_queries.append({"match_phrase": {"experience.title": "assistant to"}})
    exclude_queries.append({"match_phrase": {"experience.title": "assistant to the"}})
    exclude_queries.append({"match_phrase": {"experience.title": "of the"}})
    exclude_queries.append({"match_phrase": {"experience.title": "office of"}})
    exclude_queries.append({"match_phrase": {"experience.title": "office of the"}})

    return exclude_queries


def split_title(title):
    return [{"span_term": {"experience.title": word.lower()}} for word in title.split()]


def construct_elasticsearch_query(
    titles, universal_names, keywords, functional_keywords, countries
):
    exclusion_presidents = [
        "Executive Vice President",
        "Senior Vice President",
        "Vice President",
        "Corporate Vice President",
        "Associate Vice President",
        "Regional Vice President",
        "Group Vice President",
    ]

    exclusion_chairmen = [
        "Vice Chairmen",
        "Non Executive Chairmen",
        "Executive Chairmen",
    ]

    if not isinstance(titles, list):
        raise ValueError("Titles should be a list. Got: {}".format(type(titles)))

    if not all(isinstance(title, str) for title in titles):
        raise ValueError("Titles should be a list of strings. Got: {}".format(titles))

    if not isinstance(countries, list):
        raise ValueError("Countries should be a list. Got: {}".format(type(countries)))

    must_clauses = []
    exclude_queries = get_exclude_queries()

    if any(title in titles for title in ["President", "Presidents"]):
        exclude_queries.extend(
            [
                {"match_phrase": {"experience.title": title}}
                for title in exclusion_presidents
            ]
        )

    if any(title in titles for title in ["Chairman", "Chairmen"]):
        exclude_queries.extend(
            [
                {"match_phrase": {"experience.title": title}}
                for title in exclusion_chairmen
            ]
        )

    title_matches = [split_title(title) for title in titles]
    title_queries = [
        {"span_near": {"clauses": clause, "slop": 1, "in_order": True, "boost": 2}}
        for clause in title_matches
    ]

    core_function_clauses = []
    for core in functional_keywords[0]:
        core_function_clauses.append(
            {
                "match": {
                    "experience.title": {
                        "query": core,
                        "operator": "and",
                    }
                }
            }
        )

        core_function_clauses.append(
            {
                "match": {
                    "headline": {
                        "query": core,
                        "operator": "and",
                    }
                }
            }
        )

    secondary_functional_areas = []
    for secondary in functional_keywords[1]:
        secondary_functional_areas.append(
            {
                "match": {
                    "experience.title": {
                        "query": secondary,
                        "operator": "or",
                    }
                }
            }
        )

        secondary_functional_areas.append(
            {
                "match": {
                    "headline": {
                        "query": secondary,
                        "operator": "or",
                    }
                }
            }
        )

    must_clauses.append(
        {
            "nested": {
                "path": "experience",
                "query": {
                    "bool": {
                        "should": secondary_functional_areas
                        + company_keywords_clauses(keywords),
                        "must": [
                            {
                                "terms": {
                                    "experience.company_universal_name": universal_names
                                }
                            },
                            {
                                "bool": {
                                    "should": title_queries,
                                    "minimum_should_match": 1,
                                }
                            },
                            {
                                "bool": {
                                    "should": core_function_clauses,
                                    "minimum_should_match": 1,
                                }
                            },
                        ],
                        "must_not": exclude_queries,
                    }
                },
                "inner_hits": {
                    "name": "experience_match",
                    "size": 1,
                    "_source": False,
                    "docvalue_fields": ["experience"],
                },
            }
        }
    )

    country_boosts = [
        {"match": {"country": {"query": country, "boost": 5}}}
        for index, country in enumerate(countries)
    ]

    query = {
        "_source": ["experience.title"],
        "query": {"bool": {"must": must_clauses, "should": country_boosts}},
        "stored_fields": ["_id"],
        "size": 50,
    }
    return query


async def execute_query(titles, competitors_dict, functional_keywords, country, client):
    current_title = titles[-1]
    titles = titles[:-1]
    universal_names = list(competitors_dict.keys())

    keyword_list = []
    for key in universal_names:
        keyword_list.extend(competitors_dict[key])

    company_keywords = list(set(keyword_list))

    query = construct_elasticsearch_query(
        titles,
        universal_names,
        company_keywords,
        functional_keywords,
        country,
    )
    query["size"] = 50
    query["query"]["bool"]["must"][0]["nested"]["query"]["bool"]["must"][1]["bool"][
        "should"
    ].append(
        {
            "span_near": {
                "clauses": split_title(current_title),
                "slop": 1,
                "in_order": True,
                "boost": 4,
            }
        }
    )

    index = os.environ.get("ES_PROFILES_INDEX", "profiles")
    data = await client.search(index=index, body=query)

    esIds_indexes = {}
    titles = {}
    for d in data["hits"]["hits"]:
        if "inner_hits" in d:
            experience_match = d["inner_hits"]["experience_match"]["hits"]["hits"]
            if experience_match:
                experience_index = experience_match[0]["_nested"]["offset"]
                titles[d["_id"]] = d["_source"]["experience"][experience_index]["title"]
                esIds_indexes[d["_id"]] = experience_index
            else:
                esIds_indexes[d["_id"]] = None
                titles[d["_id"]] = None
        else:
            esIds_indexes[d["_id"]] = None
    return esIds_indexes, titles

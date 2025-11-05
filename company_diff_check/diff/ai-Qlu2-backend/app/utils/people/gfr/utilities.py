import os


def get_exclude_queries():
    exclude_queries = []

    exclude_queries.append({"exists": {"field": "experience.end"}})


ranking_data = {
    "Chairmen": ["Chairman", "Chairman of the Board", "Chair"],
    "Executive Chairmen": ["Executive Chairman", "Exec Chairman"],
    "Vice Chairmen": ["Vice Chairman", "Vice Chair"],
    "Non Executive Chairmen": ["Non-Executive Chairman", "Non-Exec Chairman"],
    "Board Members": ["Board Member"],
    "Presidents": ["President"],
    "C-suites": [
        "Chief Executive Officer",
        "CEO",
        "Chief Operating Officer",
        "COO",
        "Chief Financial Officer",
        "CFO",
        "Chief Information Officer",
        "CIO",
        "Chief Technology Officer",
        "CTO",
        "Chief Marketing Officer",
        "CMO",
        "Chief Human Resources Officer",
        "CHRO",
        "Chief Compliance Officer",
        "CCO",
        "Chief Risk Officer",
        "CRO",
        "Chief Strategy Officer",
        "CSO",
        "Chief Innovation Officer",
        "CINO",
        "Chief Data Officer",
        "CDO",
        "Chief Product Officer",
        "CPO",
        "Chief Revenue Officer",
        "CRO",
        "Chief Customer Officer",
        "CCO",
        "Chief Legal Officer",
        "CLO",
        "Chief Administrative Officer",
        "CAO",
        "Chief Communications Officer",
        "CCO",
        "Chief Diversity Officer",
        "CDO",
        "Chief Investment Officer",
        "CIO",
        "Chief Development Officer",
        "CDO",
        "Chief Privacy Officer",
        "CPO",
        "Chief Ethics Officer",
        "CEO",
        "Chief Digital Officer",
        "CDO",
        "Chief Sustainability Officer",
        "CSO",
        "Chief Business Officer",
    ],
    "Founders": ["Founder"],
    "Executive Vice Presidents": ["Executive Vice President", "EVP", "Executive VP"],
    "Senior Vice Presidents": ["Senior Vice President", "SVP", "Senior VP", "Sr. VP"],
    "Corporate Vice Presidents": ["Corporate Vice President", "CVP", "Corporate VP"],
    "Vice Presidents": ["Vice President", "VP"],
    "Group Vice Presidents": ["Group Vice President", "GVP", "Group VP"],
    "Regional Vice Presidents": ["Regional Vice President", "RVP", "Regional VP"],
    "Associate Vice Presidents": ["Associate Vice President", "AVP", "Associate VP"],
    "Partners": ["Partner"],
    "General Managers": ["General Manager", "GM"],
    "Executive Directors": ["Executive Director", "Exec Director"],
    "Managing Directors": ["Managing Director", "MD"],
    "Senior Directors": ["Senior Director", "Sr. Director"],
    "Corporate Directors": ["Corporate Director"],
    "Directors": ["Director"],
    "Regional Directors": ["Regional Director", "Area Director"],
    "Non Executive Directors": ["Non Executive Director"],
    "Associate Directors": ["Associate Director"],
    "Heads": ["Head"],
}


def get_included_excluded(dictionary, key):
    included = dictionary.get(key, [])
    excluded = [
        value for k, values in dictionary.items() if k != key for value in values
    ]
    return included, excluded


def split_title(title):
    return [{"span_term": {"experience.title": word.lower()}} for word in title.split()]


def generate_ngrams(text):
    words = text.split()
    unigrams = words
    bigrams = [" ".join(words[i : i + 2]) for i in range(len(words) - 1)]
    trigrams = [" ".join(words[i : i + 3]) for i in range(len(words) - 2)]
    all_ngrams = unigrams + bigrams + trigrams
    return all_ngrams


def refine_exclusion(titles, rank):
    ngrams = generate_ngrams(rank)
    intersection = list(set(titles) & set(ngrams))
    return [title for title in titles if title not in intersection]


async def get_ranked_esIds(
    data,
    rank,
    universal_name,
    client,
    function=None,
    counter=None,
    offset=None,
    limit=None,
):
    include_titles = get_included_excluded(data, rank)[0]

    exclude_titles = []

    exclusion_presidents = [
        "Presidents",
        "Executive Vice Presidents",
        "Senior Vice Presidents",
        "Vice Presidents",
        "Corporate Vice Presidents",
        "Associate Vice Presidents",
        "Regional Vice Presidents",
        "Group Vice Presidents",
    ]
    exclusion_directors = [
        "Senior Directors",
        "Executive Directors",
        "Corporate Directors",
        "Managing Directors",
        "Regional Directors",
        "Directors",
        "Associate Directors",
        "Non Executive Directors",
    ]
    exclusion_chairmen = [
        "Chairmen",
        "Vice Chairmen",
        "Non Executive Chairmen",
        "Executive Chairmen",
    ]
    outliers = ["Presidents", "Chairmen", "Directors"]

    if rank in exclusion_presidents:
        exclusion_presidents = refine_exclusion(exclusion_presidents, rank)
        for key, value in data.items():
            if (key in exclusion_presidents) and (key not in outliers):
                for exclusion_title in value:
                    exclude_titles.append(exclusion_title)

    if rank in exclusion_directors:
        exclusion_directors = refine_exclusion(exclusion_directors, rank)
        for key, value in data.items():
            if (key in exclusion_directors) and (key not in outliers):
                for exclusion_title in value:
                    exclude_titles.append(exclusion_title)

    if rank in exclusion_chairmen:
        exclusion_chairmen = refine_exclusion(exclusion_chairmen, rank)
        for key, value in data.items():
            if (key in exclusion_chairmen) and (key not in outliers):
                for exclusion_title in value:
                    exclude_titles.append(exclusion_title)

    include_clauses = [split_title(title) for title in include_titles]
    exclude_clauses = [split_title(title) for title in exclude_titles]

    include_queries = [
        {"span_near": {"clauses": clause, "slop": 1, "in_order": True}}
        for clause in include_clauses
    ]

    if rank == "C-suites":
        include_queries.append(
            {
                "span_near": {
                    "clauses": [
                        {"span_term": {"experience.title": "chief"}},
                        {"span_term": {"experience.title": "officer"}},
                    ],
                    "slop": 3,
                    "in_order": True,
                }
            }
        )

    exclude_queries = [
        {
            "match_phrase": {
                "experience.title": " ".join(
                    [word["span_term"]["experience.title"] for word in clause]
                )
            }
        }
        for clause in exclude_clauses
    ]

    for title in include_titles:
        exclude_queries.append(
            {"match_phrase": {"experience.title": f"to {title.lower()}"}}
        )
        exclude_queries.append(
            {"match_phrase": {"experience.title": f"of {title.lower()}"}}
        )
        exclude_queries.append(
            {"match_phrase": {"experience.title": f"to the {title.lower()}"}}
        )
        exclude_queries.append(
            {"match_phrase": {"experience.title": f"of the {title.lower()}"}}
        )
    exclude_queries.append({"match_phrase": {"experience.title": "office of the"}})
    exclude_queries.append({"exists": {"field": "experience.end"}})

    query = {
        "query": {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "match_phrase": {
                                                "experience.company_universal_name": universal_name
                                            }
                                        },
                                        {"bool": {"should": include_queries}},
                                    ],
                                    "must_not": exclude_queries,
                                }
                            },
                        }
                    }
                ]
            }
        },
    }

    if counter:
        counts = await client.count(
            index=os.environ.get("ES_PROFILES_INDEX", "profiles"), body=query
        )
        return counts["count"]
    else:
        query["size"] = 10000
        query["_source"] = False

    if limit:
        query["size"] = limit
        query["from"] = offset

    if function:
        query["query"]["bool"]["must"][0]["nested"]["query"]["bool"]["must"].append(
            {"terms": {"experience.functional_area": function}}
        )

    data = await client.search(
        index=os.environ.get("ES_PROFILES_INDEX", "profiles"), body=query
    )

    ids = []
    for profile in data["hits"]["hits"]:
        ids.append(profile["_id"])
    return ids


def search_query_generator(universalname, search_strings, es_ids=[]):
    should_clauses = []
    for search_string in search_strings:
        should_clauses.extend(
            [
                {
                    "nested": {
                        "path": "experience",
                        "query": {
                            "bool": {
                                "must": [
                                    {
                                        "match": {
                                            "experience.title": {
                                                "query": search_string,
                                                "operator": "and",
                                                "boost": 3,
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                    }
                },
                {
                    "nested": {
                        "path": "experience",
                        "query": {
                            "bool": {
                                "must": [
                                    {
                                        "match": {
                                            "experience.job_summary": {
                                                "query": search_string,
                                                "operator": "and",
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                    }
                },
                {"match": {"summary": {"query": search_string, "operator": "and"}}},
                # {"match": {"skills.keyword": {"query": search_string}}},
                {
                    "match": {
                        "headline": {
                            "query": search_string,
                            "operator": "and",
                            "boost": 1.5,
                        }
                    }
                },
            ]
        )

    query = {
        "query": {
            "bool": {
                "minimum_should_match": 1,
                "must": [
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "match_phrase": {
                                                "experience.company_universal_name": universalname
                                            }
                                        }
                                    ],
                                    "must_not": [
                                        {"exists": {"field": "experience.end"}}
                                    ],
                                    "must_not": [
                                        {"exists": {"field": "experience.end"}}
                                    ],
                                }
                            },
                        }
                    },
                ],
                "should": should_clauses,
            }
        }
    }

    query["query"]["bool"]["must"].append({"terms": {"_id": es_ids}})
    return query


async def counter(universalname, search_strings, client, es_ids=[]):
    data = await client.count(
        index=os.environ.get("ES_PROFILES_INDEX", "profiles"),
        body=search_query_generator(universalname, search_strings, es_ids),
    )
    return dict(data)["count"]


async def get_profiles_by_function(
    universal_name, function, client, limit=None, offset=None
):
    query = {
        "_source": False,
        "query": {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "match_phrase": {
                                                "experience.functional_area": function
                                            }
                                        },
                                        {"match_phrase": {"experience.index": "0"}},
                                        {
                                            "match_phrase": {
                                                "experience.company_universal_name": universal_name
                                            }
                                        },
                                    ]
                                }
                            },
                        }
                    }
                ]
            }
        },
    }

    if limit:
        query["size"] = limit
        query["from"] = offset
    else:
        query["size"] = 10000

    data = await client.search(
        index=os.environ.get("ES_PROFILES_INDEX", "profiles"), body=query
    )
    ids = []
    for profile in data["hits"]["hits"]:
        ids.append(profile["_id"])
    return ids


async def get_search_strings(universal_name, sub_group_name, client):
    data = await client.search(
        index="groups_company",
        body={"query": {"term": {"li_universalname": {"value": universal_name}}}},
    )
    groups_data = data["hits"]["hits"][0]["_source"]["groups"]
    search_strings = []
    condition = False
    for group in groups_data:
        for sg in group["sub_groups"]:
            if sub_group_name == sg["name"]:
                search_strings.append(sg["name"])
                if sg["sub_sub_groups"]:
                    search_strings.extend(sg["sub_sub_groups"])
                condition = True
                break
        if condition == True:
            break
    return search_strings

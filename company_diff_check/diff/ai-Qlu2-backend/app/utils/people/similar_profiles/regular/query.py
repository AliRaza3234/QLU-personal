import os
import re
from collections import Counter
from app.utils.people.similar_profiles.regular.country_codes import (
    codes_to_country,
    country_to_codes,
    european_countries,
)


def company_keywords_clauses(keywords):
    keywords = list(set(keywords))
    words = []
    for key in keywords:
        words.append({"match": {"experience.title": {"query": key, "operator": "or"}}})
        words.append({"match": {"headline": {"query": key, "operator": "or"}}})
    return words


def get_exclude_queries(type):
    exclude_queries = []

    exclusion_queries = [
        {"match_phrase": {"experience.title": "to the"}},
        {"match_phrase": {"experience.title": "assistant to"}},
        {"match_phrase": {"experience.title": "asst. to"}},
        {"match_phrase": {"experience.title": "asst. of"}},
        {"match_phrase": {"experience.title": "asst."}},
        {"match_phrase": {"experience.title": "assistant of"}},
        {"match_phrase": {"experience.title": "assistant of the"}},
        {"match_phrase": {"experience.title": "assistant to the"}},
        {"match_phrase": {"experience.title": "of the"}},
        {"match_phrase": {"experience.title": "ea to"}},
        {"match_phrase": {"experience.title": "ea of"}},
        {"match_phrase": {"experience.title": "ea to the"}},
        {"match_phrase": {"experience.title": "ea of the"}},
        {"match_phrase": {"experience.title": "office"}},
        {"match_phrase": {"experience.title": "retired"}},
        {"match_phrase": {"experience.title": "retire"}},
        {"match": {"experience.title": {"query": "ceo office", "operator": "and"}}},
        {
            "match": {
                "experience.title": {
                    "query": "chief executive officer office",
                    "operator": "and",
                }
            }
        },
        {"match": {"experience.title": {"query": "ceo award", "operator": "and"}}},
        {
            "match": {
                "experience.title": {
                    "query": "chief executive officer award",
                    "operator": "and",
                }
            }
        },
        {"match": {"experience.title": {"query": "ceo advisor", "operator": "and"}}},
        {
            "match": {
                "experience.title": {
                    "query": "chief executive officer advisor",
                    "operator": "and",
                }
            }
        },
        {"match": {"experience.title": {"query": "ceo assistant", "operator": "and"}}},
        {"match": {"experience.title": {"query": "pa to", "operator": "and"}}},
        {
            "match": {
                "experience.title": {
                    "query": "personal assistant to",
                    "operator": "and",
                }
            }
        },
        {"match": {"experience.title": {"query": "pa", "operator": "and"}}},
        {
            "match": {
                "experience.title": {"query": "personal assistant", "operator": "and"}
            }
        },
        {"match": {"experience.title": {"query": "secretary", "operator": "and"}}},
        {
            "match": {
                "experience.title": {
                    "query": "chief executive officer assistant",
                    "operator": "and",
                }
            }
        },
    ]

    present_queries = [{"exists": {"field": "experience.end"}}]

    if type == "Present":
        exclude_queries.extend(present_queries)
        exclude_queries.extend(exclusion_queries)

    elif type == "Past":
        exclude_queries.extend(exclusion_queries)

    return exclude_queries


def split_title(title):
    return [
        {"span_term": {"experience.title": word.lower()}}
        for word in re.findall(r"\b[a-zA-Z0-9]+\b", title)
        if word.lower()
        not in {
            "a",
            "an",
            "and",
            "the",
            "or",
            "but",
            "of",
            "in",
            "on",
            "for",
            "to",
            "with",
            "is",
            "by",
        }
    ]


def should_clause(keywords, company_keywords=[]):
    def create_keyword_query(keyword):
        return {
            "bool": {
                "should": [
                    {
                        "match": {
                            "skills": {
                                "query": keyword,
                                "operator": "and",
                                "analyzer": "standard",
                            }
                        }
                    },
                    {
                        "match": {
                            "summary": {
                                "query": keyword,
                                "operator": "and",
                                "analyzer": "standard",
                            }
                        }
                    },
                    {
                        "match": {
                            "headline": {
                                "query": keyword,
                                "operator": "and",
                                "analyzer": "standard",
                            }
                        }
                    },
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "should": [
                                        {
                                            "match": {
                                                "experience.title": {
                                                    "query": keyword,
                                                    "operator": "and",
                                                    "analyzer": "standard",
                                                }
                                            }
                                        },
                                        {
                                            "match": {
                                                "experience.job_description": {
                                                    "query": keyword,
                                                    "operator": "and",
                                                    "analyzer": "standard",
                                                }
                                            }
                                        },
                                    ]
                                }
                            },
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        }

    def create_company_keyword_query(keyword):
        return {
            "bool": {
                "should": [
                    {
                        "match": {
                            "skills": {
                                "query": keyword,
                                "operator": "and",
                                "analyzer": "standard",
                                "boost": 5,
                            }
                        }
                    },
                    {
                        "match": {
                            "summary": {
                                "query": keyword,
                                "operator": "and",
                                "analyzer": "standard",
                                "boost": 5,
                            }
                        }
                    },
                    {
                        "match": {
                            "headline": {
                                "query": keyword,
                                "operator": "and",
                                "analyzer": "standard",
                                "boost": 5,
                            }
                        }
                    },
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "should": [
                                        {
                                            "match": {
                                                "experience.title": {
                                                    "query": keyword,
                                                    "operator": "and",
                                                    "analyzer": "standard",
                                                    "boost": 5,
                                                }
                                            }
                                        },
                                        {
                                            "match": {
                                                "experience.job_description": {
                                                    "query": keyword,
                                                    "operator": "and",
                                                    "analyzer": "standard",
                                                    "boost": 5,
                                                }
                                            }
                                        },
                                    ]
                                }
                            },
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        }

    return [create_keyword_query(keyword) for keyword in keywords] + [
        create_company_keyword_query(keyword) for keyword in company_keywords
    ]


async def construct_elasticsearch_query(
    title_keyword_dict,
    location_dict,
    filter_type,
    client,
    competitors_dict=None,
    current_title=None,
    service_flags=None,
):

    ranks = title_keyword_dict.get("ranks", [])
    current_titles_from_service = title_keyword_dict.get("current_titles", [])
    universal_names = list(competitors_dict.keys()) if competitors_dict else []
    company_keywords = list(competitors_dict.values()) if competitors_dict else []
    company_keywords = [item for sublist in company_keywords for item in sublist]

    location = location_dict.get("location", "")
    metro_area = location_dict.get("metro_area", "")
    country = location_dict.get("country", "")

    status_flag = title_keyword_dict.get("flag", "")
    status_flag = status_flag.lower()

    if status_flag == "ceo/chairman":
        titles_dict = title_keyword_dict.get("title_dict", "")
        current_title_lower = current_title.lower()

        titles_dict[current_title_lower] = 6
        base_should_clause = []

    elif status_flag == "executive":
        titles_dict = title_keyword_dict.get("title_dict", "")
        skills = title_keyword_dict.get("skills", [])
        current_title_lower = current_title.lower()
        if service_flags == "external":
            titles_dict[current_title_lower] = 6
        base_should_clause = should_clause(skills, company_keywords)

    elif status_flag == "non-executive":
        titles_dict = title_keyword_dict.get("title_dict", "")
        skills = title_keyword_dict.get("skills", [])
        current_title_lower = current_title.lower()
        if service_flags == "external":
            titles_dict[current_title_lower] = 6
        base_should_clause = should_clause(skills, company_keywords)
    else:
        print("Invalid status flag")
        raise Exception("Invalid status flag")

    titles_clauses = titles_dict

    if country is None:
        profile_dataset = await client.search(
            index=os.environ.get("ES_PROFILES_INDEX", "profiles"),
            body={
                "size": 1000,
                "_source": ["country"],
                "query": {
                    "bool": {
                        "must": [
                            {"match_phrase": {"location": location}},
                            {"exists": {"field": "country"}},
                        ],
                        "must_not": [{"match": {"country": location}}],
                    }
                },
            },
        )

        elements = []
        for i in profile_dataset["hits"]["hits"]:
            elements.append(i["_source"]["country"])

        country = Counter(elements).most_common(1)[0][0] if elements else None

    country_key_words = [country] if country else []
    code = country_to_codes.get(country, None)
    if code:
        country_key_words.append(code)
    country_ = codes_to_country.get(country, None)
    if country_:
        country_key_words.append(country_)
    country_key_words = list(set(k for k in country_key_words if k))

    base_eu_country = []
    if country in european_countries:
        base_eu_country = country_key_words[:]

        for european_country in european_countries:
            code = country_to_codes.get(european_country, None)
            if code:
                country_key_words.append(code)
            country_key_words.append(european_country)

    exclusion_presidents = [
        "Retired President",
        "Executive Vice President",
        "Senior Vice President",
        "Vice President",
        "Corporate Vice President",
        "Associate Vice President",
        "Regional Vice President",
        "Group Vice President",
    ]

    exclusion_presidents_acronyms = ["EVP", "SVP", "VP", "CVP", "AVP", "RVP", "GVP"]

    exclusion_chairmen = [
        "Vice Chairmen",
        "Non Executive Chairmen",
        "Executive Chairmen",
        "Vice Chairman",
        "Non Executive Chairman",
        "Executive Chairman",
    ]

    ceo_exclusion = [
        "Director of CEO",
        "Director, CEO",
        "Manager",
        "Director of CEO",
        "Mind of a CEO",
        "Mind of CEO",
        "CEO Keynote",
        "CEO, Keynote",
        "CEO Chief of",
        "Developer",
        "Engineer",
        "Analyst",
        "Consultant",
        "Advisor",
        "Specialist",
        "Coordinator",
        "Administrator",
        "Assistant",
        "Associate",
    ]

    lower_president_exclusion = [
        "Senior VP",
        "Senior Vice President",
        "SVP",
        "Executive VP",
        "Executive Vice President",
        "EVP",
        "CVP",
        "Corporate VP",
        "Corporate Vice President",
    ]

    lower_executive_vp_exclusion = [
        "Executive VP",
        "Executive Vice President",
        "EVP",
        "CVP",
        "Corporate VP",
        "Corporate Vice President",
    ]

    # executive_exclusion = [
    #     "Assistant to",
    #     "Office of",
    #     "Developer",
    #     "Engineer",
    #     "Analyst",
    #     "Consultant",
    #     "Advisor",
    #     "Specialist",
    #     "Coordinator",
    #     "Administrator",
    #     "Assistant",
    #     "Associate",
    # ]
    exclude_queries = get_exclude_queries(filter_type)

    # if any(t in ranks for t in ["President", "Presidents"]):
    #     exclude_queries.extend(
    #         [
    #             {
    #                 "match": {
    #                     "experience.title": {
    #                         "query": ex_pres.lower(),
    #                         "operator": "and",
    #                     }
    #                 }
    #             }
    #             for ex_pres in exclusion_presidents
    #         ]
    #         + [
    #             {"match_phrase": {"experience.title": ex_pres_ac.lower()}}
    #             for ex_pres_ac in exclusion_presidents_acronyms
    #         ]
    #     )

    if any(t in ranks for t in ["Chairman", "Chairmen", "Chair"]):
        exclude_queries.extend(
            [
                {
                    "match": {
                        "experience.title": {"query": ex_ch.lower(), "operator": "and"}
                    }
                }
                for ex_ch in exclusion_chairmen
            ]
        )

    if service_flags == "internal":
        if any(
            t in current_titles_from_service
            for t in [
                "Senior VP",
                "Senior Vice President",
                "SVP",
            ]
        ):
            exclude_queries.extend(
                [
                    {
                        "match": {
                            "experience.title": {
                                "query": ex_pres.lower(),
                                "operator": "and",
                            }
                        }
                    }
                    for ex_pres in lower_president_exclusion
                ]
            )

    if service_flags == "internal":
        if any(
            t in current_titles_from_service
            for t in [
                "Executive VP",
                "Executive Vice President",
                "EVP",
                "CVP",
                "Corporate VP",
                "Corporate Vice President",
            ]
        ):
            exclude_queries.extend(
                [
                    {
                        "match": {
                            "experience.title": {
                                "query": ex_pres.lower(),
                                "operator": "and",
                            }
                        }
                    }
                    for ex_pres in lower_executive_vp_exclusion
                ]
            )

        president_titles = ["President", "Presidents"]
        vp_titles = [
            "Executive Vice President",
            "Senior Vice President",
            "EVP",
            "SVP",
        ]

        if any(t in ranks for t in president_titles) and not any(
            t in ranks for t in vp_titles
        ):
            exclude_queries.extend(
                [
                    {
                        "match": {
                            "experience.title": {
                                "query": ex_pres.lower(),
                                "operator": "and",
                            }
                        }
                    }
                    for ex_pres in exclusion_presidents
                ]
                + [
                    {"match_phrase": {"experience.title": ex_pres_ac.lower()}}
                    for ex_pres_ac in exclusion_presidents_acronyms
                ]
            )

    if any(t in ranks for t in ["CEO", "Chief Executive Officer"]):
        exclude_queries.extend(
            [
                {
                    "match": {
                        "experience.title": {
                            "query": ex_ceo.lower(),
                            "operator": "and",
                        }
                    }
                }
                for ex_ceo in ceo_exclusion
            ]
        )

    # if status_flag == "executive":
    #     exclude_queries.extend(
    #         [
    #             {
    #                 "match": {
    #                     "experience.title": {
    #                         "query": ex_exec.lower(),
    #                         "operator": "and",
    #                     }
    #                 }
    #             }
    #             for ex_exec in executive_exclusion
    #         ]
    #     )

    title_queries = []
    for title, boost_value in titles_clauses.items():
        split_title_clauses = split_title(title)
        title_queries.append(
            {
                "span_near": {
                    "clauses": split_title_clauses,
                    "slop": 1,
                    "boost": boost_value,
                }
            }
        )

    country_matching = []
    for country_key_word in country_key_words:
        if country_key_word in base_eu_country:
            country_matching.append(
                {
                    "match": {
                        "location_full_path": {
                            "query": country_key_word,
                            "operator": "and",
                            "analyzer": "standard",
                            "boost": 3,
                        }
                    }
                }
            )
        else:
            country_matching.append(
                {
                    "match": {
                        "location_full_path": {
                            "query": country_key_word,
                            "operator": "and",
                            "analyzer": "standard",
                        }
                    }
                }
            )

    must_clauses = []
    must_clauses.append(
        {"bool": {"should": country_matching, "minimum_should_match": 1}}
    )

    companies_with_boost = []
    if universal_names:
        for company, company_score in universal_names:
            companies_with_boost.append(
                {
                    "term": {
                        "experience.company_universal_name": {
                            "value": company,
                            "boost": company_score,
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
                        "must": [
                            {
                                "bool": {
                                    "should": companies_with_boost,
                                    "minimum_should_match": 1,
                                }
                            },
                            {
                                "bool": {
                                    "should": title_queries,
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

    country_boosts = []
    if location and not metro_area:
        country_boosts = [
            {"match": {"location": {"query": location, "boost": 3}}},
        ]
    if metro_area and not location:
        country_boosts = [
            {"match": {"metro_area": {"query": metro_area, "boost": 3}}},
        ]
    if location and metro_area:
        country_boosts = [
            {"match": {"location": {"query": location, "boost": 3}}},
            {"match": {"metro_area": {"query": metro_area, "boost": 3}}},
        ]

    if status_flag == "ceo/chairman":
        query = {
            "_source": ["experience.title"],
            "query": {"bool": {"must": must_clauses, "should": base_should_clause}},
            "stored_fields": ["_id"],
        }
    elif status_flag == "executive":
        query = {
            "_source": ["experience.title"],
            "query": {
                "bool": {
                    "must": must_clauses,
                    "should": base_should_clause,
                }
            },
            "stored_fields": ["_id"],
        }
    elif status_flag == "non-executive":
        query = {
            "_source": ["experience.title"],
            "query": {
                "bool": {
                    "must": must_clauses,
                    "should": country_boosts + base_should_clause,
                }
            },
            "stored_fields": ["_id"],
        }

    return query


async def execute_query(
    titles,
    competitors_dict,
    location_dict,
    client,
    filter_type,
    current_title=None,
    service_flag=None,
):

    query = await construct_elasticsearch_query(
        titles,
        location_dict,
        filter_type,
        client,
        competitors_dict,
        current_title,
        service_flag,
    )
    query["size"] = 1000

    if filter_type == "Past":
        query["query"]["bool"]["must"][1]["nested"]["query"]["bool"]["must"].append(
            {"exists": {"field": "experience.end"}}
        )

    # import json
    # print(json.dumps(query))

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

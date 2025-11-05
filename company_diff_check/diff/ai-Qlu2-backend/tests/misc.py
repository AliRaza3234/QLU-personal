filters_payload = """{
  "profileNames": {"isSelected": [], "isRemoved": []},
  "jobTitles": {
    "current": {
      "isStrict": false,
      "isSelected": [
        {"name": "CFO", "isSelected": true, "min": 1, "max": 50000000, "isRemoved": false},
        {"name": "Chief Revenue Officer", "isSelected": true, "min": 1, "max": 50000000, "isRemoved": false},
        {"name": "Chief Sales Officer", "isSelected": true, "min": 1, "max": 50000000, "isRemoved": false},
        {"name": "Chief Financial Officer", "isSelected": true, "min": 1, "max": 50000000},
        {"name": "Vice President of Finance", "isSelected": true, "min": 1, "max": 50000000, "isRemoved": false},
        {"name": "Director of Finance", "isSelected": true, "min": 1, "max": 50000000, "isRemoved": false},
        {"name": "Chief Accounting Officer", "isSelected": true, "min": 1, "max": 50000000, "isRemoved": false},
        {"name": "Vice President of Accounting", "isSelected": true, "min": 1, "max": 50000000, "isRemoved": false},
        {"name": "Director of Accounting", "isSelected": true, "min": 1, "max": 50000000, "isRemoved": false}
      ],
      "isRemoved": []
    },
    "previous": {"isStrict": false, "isSelected": [], "isRemoved": []}
  },
  "managementTitles": {"isSelected": [], "isRemoved": []},
  "experience": {"total": {"min": 1, "max": 10}, "relevant": {}},
  "education": {"degree": {"isSelected": [], "isRemoved": []}, "major": {"isSelected": [], "isRemoved": []}},
  "industries": {
    "isStrict": false,
    "isSelected": [
      "Consumer Electronics",
      "Personal Computing",
      "Mobile devices",
      "Home Appliances",
      "Telecommunications",
      "Computer Hardware",
      "Audio and Video Equipment",
      "Smart Home Technology",
      "Electronics Manufacturing",
      "Computer Networking"
    ],
    "isRemoved": []
  },
  "skills": {"isStrict": false, "isSelected": ["Startups", "Leadership", "Management"], "isRemoved": []},
  "company": {
    "current": {
      "isStrict": false,
      "isSelected": [
        {"name": "Apple", "industry": "Computers and Electronics Manufacturing ", "logo": "https://qlu-media-cmp.s3.amazonaws.com/apple.jpg", "urn": "urn:li:fsd_company:162479", "universalName": "apple", "isSelected": true, "isRemoved": false},
        {"name": "Microsoft", "industry": "Software Development ", "logo": "https://qlu-media-cmp.s3.amazonaws.com/microsoft.jpg", "urn": "urn:li:fsd_company:1035", "universalName": "microsoft", "isSelected": true, "isRemoved": false},
        {"name": "Google", "industry": "Software Development", "universalName": "google", "urn": "urn:li:fsd_company:1441", "logo": "https://media.licdn.com/dms/image/C4D0BAQHiNSL4Or29cg/company-logo_200_200/0/1631311446380?e=1707955200&v=beta&t=igPSyYS8yYqbtKwUE8BVqxq0cKTw07RQiNNt7JtwWVo", "isSelected": true, "isRemoved": false}
      ],
      "isRemoved": []
    },
    "companySizes": {"isSelected": [], "isRemoved": []},
    "currentCompanyExperience": {},
    "previous": {"isStrict": false, "isSelected": [], "isRemoved": []},
    "either": {"isSelected": [], "isRemoved": []}
  },
  "locations": {"current": {"isStrict": false, "isSelected": ["United States", "California, United States", "New York, United States"], "isRemoved": []}, "previous": {"isStrict": false, "isSelected": [], "isRemoved": []}},
  "AssignmentProfilesIds": [],
  "isTitleSelected": true,
  "isCompanySearchSelected": true,
  "isManagementLevelSelected": false,
  "isLocationSelected": true,
  "isExperienceSelected": false,
  "isIndustrySelected": true,
  "isEducationSelected": false,
  "isSkillSelected": true,
  "isProfileNameSelected": false,
  "isAssignmentSelected": false
}"""

previous_company_filter = """
{
    "profileNames": {
        "isSelected": [],
        "isRemoved": []
    },
    "jobTitles": {
        "current": {
            "isStrict": false,
            "isSelected": [
                {
                    "name": "Chief",
                    "isSelected": true,
                    "min": 1,
                    "max": 50000000,
                    "isRemoved": false
                }
            ],
            "isRemoved": []
        },
        "previous": {
            "isStrict": false,
            "isSelected": [],
            "isRemoved": []
        }
    },
    "managementTitles": {
        "isSelected": [],
        "isRemoved": []
    },
    "experience": {
        "total": {
            "min": 1,
            "max": 10
        },
        "relevant": {}
    },
    "education": {
        "degree": {
            "isSelected": [],
            "isRemoved": []
        },
        "major": {
            "isSelected": [],
            "isRemoved": []
        }
    },
    "industries": {
        "isStrict": false,
        "isSelected": [],
        "isRemoved": []
    },
    "skills": {
        "isStrict": false,
        "isSelected": [
            "Management"
        ],
        "isRemoved": []
    },
    "company": {
        "current": {
            "isStrict": false,
            "isSelected": [{
                "name": "Apple", "universalName": "apple"
            }],
            "isRemoved": []
        },
        "companySizes": {
            "isSelected": [],
            "isRemoved": []
        },
        "currentCompanyExperience": {},
        "previous": {
            "isStrict": false,
            "isSelected": [{
                "universalName": "google"
            }],
            "isRemoved": []
        },
        "either": {
            "isSelected": [],
            "isRemoved": []
        }
    },
    "locations": {
        "current": {
            "isStrict": false,
            "isSelected": [
                "United States"
            ],
            "isRemoved": []
        },
        "previous": {
            "isStrict": false,
            "isSelected": [],
            "isRemoved": []
        }
    },
    "AssignmentProfilesIds": [],
    "isTitleSelected": true,
    "isCompanySearchSelected": false,
    "isManagementLevelSelected": false,
    "isLocationSelected": true,
    "isExperienceSelected": false,
    "isIndustrySelected": false,
    "isEducationSelected": false,
    "isSkillSelected": true,
    "isProfileNameSelected": false,
    "isAssignmentSelected": false
} """


previous_title_filter = """
{
    "profileNames": {
        "isSelected": [],
        "isRemoved": []
    },
    "jobTitles": {
        "current": {
            "isStrict": false,
            "isSelected": [
                {
                    "name": "Chief Marketing Officer",
                    "isSelected": true,
                    "min": 1,
                    "max": 50000000,
                    "isRemoved": false
                }
            ],
            "isRemoved": []
        },
        "previous": {
            "isStrict": false,
            "isSelected": [{
                    "name": "Marketing Director",
                    "isSelected": true,
                    "min": 1,
                    "max": 50000000,
                    "isRemoved": false
                }],
            "isRemoved": []
        }
    },
    "managementTitles": {
        "isSelected": [],
        "isRemoved": []
    },
    "experience": {
        "total": {
            "min": 1,
            "max": 10
        },
        "relevant": {}
    },
    "education": {
        "degree": {
            "isSelected": [],
            "isRemoved": []
        },
        "major": {
            "isSelected": [],
            "isRemoved": []
        }
    },
    "industries": {
        "isStrict": false,
        "isSelected": [],
        "isRemoved": []
    },
    "skills": {
        "isStrict": false,
        "isSelected": [
            "Management"
        ],
        "isRemoved": []
    },
    "company": {
        "current": {
            "isStrict": false,
            "isSelected": [{
                "name": "Apple", "universalName": "apple"
            }],
            "isRemoved": []
        },
        "companySizes": {
            "isSelected": [],
            "isRemoved": []
        },
        "currentCompanyExperience": {},
        "previous": {
            "isStrict": false,
            "isSelected": [{
                "universalName": "google"
            }],
            "isRemoved": []
        },
        "either": {
            "isSelected": [],
            "isRemoved": []
        }
    },
    "locations": {
        "current": {
            "isStrict": false,
            "isSelected": [
                "United States"
            ],
            "isRemoved": []
        },
        "previous": {
            "isStrict": false,
            "isSelected": [],
            "isRemoved": []
        }
    },
    "AssignmentProfilesIds": [],
    "isTitleSelected": true,
    "isCompanySearchSelected": false,
    "isManagementLevelSelected": false,
    "isLocationSelected": true,
    "isExperienceSelected": false,
    "isIndustrySelected": false,
    "isEducationSelected": false,
    "isSkillSelected": true,
    "isProfileNameSelected": false,
    "isAssignmentSelected": false
}
"""

person_skills = {
    "publicIdentifier": "zayn-fernandes-1257b5106",
    "headline": "CFO - Latin America Hub",
    "summary": "",
    "experienceDescriptionList": ["", "", "", "", "", "", "", "", ""],
    "titleList": [
        "CFO LATAM HUB",
        "Regional CFO - Poland, Hungary, Czech Republic & Slovakia",
        "CFO Hungary",
        "Group Financial Planning and Analysis Director (VP)",
        "GB Commercial Finance - On trade",
        "Regional Treasurer",
        "Global Audit and Risk Senior Manager",
        "Assurance Manager",
    ],
    "type": "skills",
    "entityList": [
        "Commercial Finance",
        "Corporate Finance",
        "Financial Controlling",
        "External Audit",
        "Internal Audit",
        "Business Development",
        "Treasury",
        "New Business Integration",
        "Mentoring",
        "People Management",
    ],
}
person_domains = {
    "publicIdentifier": "zayn-fernandes-1257b5106",
    "headline": "CFO - Latin America Hub",
    "summary": "",
    "experienceDescriptionList": ["", "", "", "", "", "", "", "", ""],
    "titleList": [
        "CFO LATAM HUB",
        "Regional CFO - Poland, Hungary, Czech Republic & Slovakia",
        "CFO Hungary",
        "Group Financial Planning and Analysis Director (VP)",
        "GB Commercial Finance - On trade",
        "Regional Treasurer",
        "Global Audit and Risk Senior Manager",
        "Assurance Manager",
    ],
    "type": "speciality",
    "companySpeciality": {
        "Microsoft": [
            "Business Software",
            "Developer Tools",
            "Home & Educational Software",
            "Tablets",
            "Search",
            "Advertising",
            "Servers",
            "Windows Operating System",
            "Windows Applications & Platforms",
            "Smartphones",
            "Cloud Computing",
            "Quantum Computing",
            "Future of Work",
            "Productivity",
            "AI",
            "Artificial Intelligence",
            "Machine Learning",
            "Laptops",
            "Mixed Reality",
            "Virtual Reality",
            "Gaming",
            "Developers",
            "IT Professional",
        ],
        "Diageo": [
            "Premium Drinks",
            "Marketing",
            "Innovation",
            "Supply Chain",
            "HR",
            "Sales",
            "Brand management",
            "Premium Wines and Spirits Supplier",
            "Luxury",
            "Super premium",
            "Beer",
            "Consumer goods",
            "E-commerce",
            "beverages",
            "spirits",
            "FMCG",
            "brand owners",
        ],
        "PwC UK": ["Tax", "Deals", "Consulting", "Audit", "Technology"],
        "Deloitte": [
            "Audit",
            "Consulting",
            "Financial Advisory",
            "Risk Management",
            "Tax Services",
        ],
    },
}


financials_payload_no_esid = {
    "selected": "public",
    "public_filters": {
        "market_cap": {"value": {"max": 0, "min": 50000000, "type": "Greater than"}},
        "revenue": {},
        "revenueGrowth": {},
        "earnings": {},
        "stock_filter": {
            "value": {"min": 25, "max": 30, "type": "Between"},
            "timeInterval": {"days": -60},
        },
    },
    "private_filters": {
        "last_funding_amount": {
            "value": {"min": 1595916, "max": 159599017, "type": "Between"}
        },
        "total_funding_amount": {
            "value": {"min": 500000, "max": 0, "type": "Greater than"}
        },
        "last_funding_date": {},
        "last_funding_type": [],
        "investors": [],
        "shared_investors": [],
        "estimated_revenue": {
            "value": {"min": 380000000, "max": 400000000, "type": "Between"},
            "timeInterva    l": {"type": "y", "value": 1},
        },
    },
    "estimated_revenue": {
        "value": {"min": 300000000, "max": 30, "type": "Equals"},
        "timeInterval": {"type": "q", "value": 1},
    },
    "m_and_a": ["made acquisitions"],
    "ownership": ["Private"],
}

financials_payload_esid = {
    "es_ids": ["532"],
    "selected": "public",
    "public_filters": {
        "market_cap": {"value": {"max": 0, "min": 50000000, "type": "Greater than"}},
        "revenue": {},
        "revenueGrowth": {},
        "earnings": {},
        "stock_filter": {
            "value": {"min": 25, "max": 30, "type": "Between"},
            "timeInterval": {"days": -60},
        },
    },
    "private_filters": {
        "last_funding_amount": {
            "value": {"min": 1595916, "max": 159599017, "type": "Between"}
        },
        "total_funding_amount": {
            "value": {"min": 500000, "max": 0, "type": "Greater than"}
        },
        "last_funding_date": {},
        "last_funding_type": [],
        "investors": [],
        "shared_investors": [],
        "estimated_revenue": {
            "value": {"min": 380000000, "max": 400000000, "type": "Between"},
            "timeInterva    l": {"type": "y", "value": 1},
        },
    },
    "estimated_revenue": {
        "value": {"min": 300000000, "max": 30, "type": "Equals"},
        "timeInterval": {"type": "q", "value": 1},
    },
    "m_and_a": ["made acquisitions"],
    "ownership": ["Private"],
}


demographics_payload = {
    "image_url": "/home/mohammadmomin/MominNewStuff/QLU2Backend/momin_linkedin.jpeg",
    "esId": "01HA588NXVYP7Z028MB6GX3P3G",
    "education": ["string"],
    "experience": ["string"],
    "fullName": "string",
    "firstName": "string",
    "lastName": "string",
}

financial_summary_payload = {"id": "li_universalname"}

stocks_payload = {"id": "li_universalname"}

financial_data_payload = {
    "id": "apple",
    "financial_type": "incomestatement",
    "type": "yearly",
}

skills_and_industries = {"skills": [], "industries": []}

name_mapping_payload = {"company_name": "apple"}

groups_subgroup_counts_payload = {
    "universal_name": "microsoft",
    "company_group": "Gaming",
}

groups_subgroup_rank_counts_payload = {
    "universal_name": "microsoft",
    "sub_group_name": "Xbox",
    "type": "rank",
}

groups_subgroup_function_counts_payload = {
    "universal_name": "microsoft",
    "sub_group_name": "Xbox",
    "type": "function",
}


group_subgroups_ranks_profiles_payload = {
    "sub_group_name": "Xbox",
    "type": "rank",
    "universal_name": "microsoft",
    "offset": 0,
    "limit": 10,
    "filter": "Directors",
}

group_subgroups_functions_profiles_payload = {
    "sub_group_name": "Xbox",
    "type": "function",
    "universal_name": "microsoft",
    "offset": 0,
    "limit": 10,
    "filter": "Sales",
}


rank_profiles_payload = {
    "universal_name": "microsoft",
    "offset": 0,
    "limit": 20,
    "rank": "C-suites",
}

function_profiles_payload = {
    "universal_name": "microsoft",
    "offset": 0,
    "limit": 20,
    "function": "Sales",
}

external_similar_profiles_payload = {
    "esId": "924300",
    "type": "external",
    "offset": 0,
    "limit": 8,
}

internal_similar_profiles_payload = {
    "esId": "924300",
    "type": "internal",
    "offset": 0,
    "limit": 8,
}

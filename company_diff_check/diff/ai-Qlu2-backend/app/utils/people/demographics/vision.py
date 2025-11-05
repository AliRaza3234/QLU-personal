import os
import re
from app.core.database import cache_data, get_cached_data
from qutils.llm.asynchronous import invoke
from datetime import datetime


def find_first_number(input_string):
    numbers = re.findall(r"\d+", input_string)
    if numbers:
        return int(numbers[0])
    else:
        return None


class AgeCalculation:
    def __init__(self, education=None, startdate=None, URL=None):
        self.education = education
        self.startdate = startdate
        self.url = URL

        self.listt = [
            "Person whose age is between 18-25 range",
            "Person whose age is between 25-30 range",
            "Person whose age is between 30-40 range",
            "Person whose age is between 40-50 range",
            "Person whose age is between 50-60 range",
            "Person whose age is between 60-70 range",
            "Person whose age is between 70-75 range",
        ]

        self.numbersage = [18, 25, 30, 40, 50, 60, 70, 75]

        self.degree_names = [
            "bs",
            "bachelors",
            "bachelor",
            "undergrad",
            "undergraduate",
            "bcs",
            "bsc",
            "btech",
            "bcom",
            "ba",
            "b.s",
            "b.a",
            "b.com",
        ]
        self.school_names = ["high school", "college", "secondary school"]

    async def get_age(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "You are an intelligent assistant, your job is to estimate the age of person based on their provided image. Always return a numeric value, nothing else.",
                    },
                    {"type": "image_url", "image_url": {"url": self.url}},
                ],
            }
        ]
        response = await invoke(
            messages=messages,
            model="groq/meta-llama/llama-4-maverick-17b-128e-instruct",
            temperature=0,
        )
        return response

    async def Ages(self):
        age_educ = 0

        year = datetime.now().year

        for educ in self.education:
            flag = False
            for j in self.degree_names:
                if (
                    educ["degreeName"]
                    and j in educ["degreeName"].lower().strip()
                    and "mba" not in educ["degreeName"].lower().strip()
                    and "m.b.a" not in educ["degreeName"].lower().strip()
                ):
                    flag = True
                    try:
                        age_educ = (
                            year - int(datetime.fromisoformat(educ["end"]).year)
                        ) + 22
                    except:
                        try:
                            age_educ = (
                                year - int(datetime.fromisoformat(educ["start"]).year)
                            ) + 18
                        except Exception as e:
                            flag = False

                if flag:
                    break
            if not flag:
                for j in self.school_names:
                    if educ["degreeName"] and j in educ["degreeName"].lower().strip():
                        flag = True
                        try:
                            age_educ = (
                                year - int(datetime.fromisoformat(educ["end"]).year)
                            ) + 18
                        except Exception as e:
                            flag = False

                    if flag:
                        break
            if flag:
                break

        age_image = 0
        if self.url != None:
            age_image_get = await self.get_age()
            if age_image_get != None:
                if find_first_number(age_image_get) != None:
                    age_image = int(age_image_get)

        age_exp = 0
        try:
            age_exp = (year - self.startdate) + 22
        except:
            pass

        if age_educ > age_exp:
            max_cal_age = age_educ
        else:
            max_cal_age = age_exp

        if age_image < max_cal_age:
            age = max_cal_age
        elif (age_image - max_cal_age) < 5:
            age = max_cal_age
        else:
            age = age_image

        if age != 0:
            return age
        else:
            return None

    async def main(self):
        age = await self.Ages()
        return age


async def GPT4_ethnicity_gender(url, model):
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""
Describe the image. Also tell me the name of the country the person is likely from (give your best guess about region only). The person can only be from the following regions ["Asia", "Africa", "South Asia", "Middle East", "Mexico", "London", "Other"] only. Assume all caucasians are from London region while african americans and blacks are from africa, while all latinos are from Mexico. Asia regions are those from china, japan, phillipine, etc, while south east regions include pakistan, india, bangladesh, sri lanka, etc. However, do not comment on the ethnicity of an individual but only return a likely region they are likely from. Choose "Others" when you are 100% sure they are not from the mentioned regions, otherwise give the best guess only. Describe the complete image as well, including whether the person appears to be an adult male or not (only what appears to be, NOT a conclusive decision). Describe the picture quality as well.
Your output should be a JSON object in form like the following:
             {{"description" : 'not-adult-male'~region~description-of-image}}
""",
                },
                {"type": "image_url", "image_url": {"url": url, "detail": "low"}},
            ],
        }
    ]
    response = await invoke(messages=messages, model=model, temperature=0)
    return response


async def GPT3Gender(name):
    messages = [
        {
            "role": "system",
            "content": """You are an intelligent assistant whose job is to determine gender of a person using their name. You can only return Male or Female or Other if you're unsure""",
        },
        {"role": "user", "content": name},
    ]
    response = await invoke(
        messages=messages,
        model="openai/gpt-4o-mini",
        temperature=0.3,
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    return response


async def get_from_es(id, client):
    response = await client.search(
        body={
            "_source": ["gender", "ethnicity", "age"],
            "query": {"term": {"_id": {"value": id}}},
        },
        index=os.getenv("ES_PROFILES_INDEX", "people"),
    )
    try:
        gender = response["hits"]["hits"][0]["_source"]["gender"]
        ethnicity = response["hits"]["hits"][0]["_source"]["ethnicity"]
        age = response["hits"]["hits"][0]["_source"]["age"]
        if gender == "F":
            gender = "Female"
        elif gender == "M":
            gender = "Male"
        else:
            gender = None

        return gender, ethnicity, age
    except:
        return None, None, None


async def inference(payload, es_client):

    esId = payload["esId"]

    gender, ethnicity, age = await get_from_es(esId, es_client)
    if gender and ethnicity and age:
        if ethnicity == "White":
            ethnicity = "Caucasian"
        elif ethnicity == "Black":
            ethnicity = "African"
        elif ethnicity == "Latino":
            ethnicity = "Hispanic"
        elif ethnicity == "South East Asian":
            ethnicity = "South Asian"

        return {"age": age, "gender": gender, "race": ethnicity}

    cache = await get_cached_data(f"{esId}~demographics", "cache_demographics")
    if cache:
        if cache["age"] == "Undetermined":
            cache = None
        if cache["race"] == "White":
            cache["race"] = "Caucasian"
    if cache == None:
        url = payload["image_url"]
        fullname = payload["fullName"]
        lastname = payload["lastName"]
        firstname = payload["firstName"]
        education = payload["education"]
        exp = payload["experience"]

        startdate = ""
        length = len(exp)
        startdate = datetime.now().year
        if length > 0:
            for i in exp:
                try:
                    temp_startdate = int(datetime.fromisoformat(i["start"]).year)
                    if temp_startdate < startdate:
                        startdate = temp_startdate
                except Exception as e:
                    pass

        name = ""
        if fullname == "":
            name = firstname + " " + lastname
        else:
            name = fullname

        if name.strip() == "":
            name = ""

        model = "openai/gpt-4o"
        response_content = await GPT4_ethnicity_gender(url, model)
        if response_content == None:
            gender = await GPT3Gender(name)
            if "Male" in gender:
                gender = "Male"
            elif "Female" in gender:
                gender = "Female"
            else:
                gender = "Other"
            ethnicity = "Other"
        else:
            flag = False
            for i in range(3):
                try:
                    if i == 1:
                        model = "openai/gpt-4o"
                    elif i == 2:
                        model = "openai/gpt-4o-mini"
                    if flag == True:
                        response_content = await GPT4_ethnicity_gender(url, model)

                    infer = eval(
                        response_content[
                            response_content.find("{") : response_content.rfind("}") + 1
                        ]
                    )

                    all_info = infer["description"]
                    all_information = all_info.split("~")
                    gender = all_information[0]
                    if ("not" in gender and "male" in gender) or (
                        "female" in gender and "not" not in gender
                    ):
                        gender = "Female"
                    else:
                        gender = "Male"

                    ethnicity = all_information[1]
                    for region in [
                        "Asia",
                        "Africa",
                        "South Asia",
                        "Middle East",
                        "Mexico",
                        "London",
                        "Other",
                    ]:
                        if ethnicity.lower() == region.lower():
                            if region == "Asia":
                                ethnicity = "Asian"
                            elif region == "Africa":
                                ethnicity = "African"
                            elif region == "South Asia":
                                ethnicity = "South Asian"
                            elif region == "London":
                                ethnicity = "Caucasian"
                            elif region == "Mexico":
                                ethnicity = "Latino"
                            elif region == "Middle East":
                                ethnicity = "Middle Eastern"
                            elif region == "Other":
                                ethnicity = "Other"

                            break
                    if ethnicity not in [
                        "Asian",
                        "African",
                        "South Asian",
                        "Caucasian",
                        "Latino",
                        "Middle Eastern",
                        "Other",
                    ]:
                        ethnicity = "Other"
                    flag = False
                    break
                except Exception as e:
                    flag = True
                    pass

            if flag:
                try:
                    gender = await GPT3Gender(name)
                    if "Male" in gender:
                        gender = "Male"
                    elif "Female" in gender:
                        gender = "Female"
                    else:
                        gender = "Other"
                    ethnicity = "Other"
                except:
                    gender = None
                    ethnicity = "Other"

        age_calc = AgeCalculation(education, startdate, url)
        age = await age_calc.main()
        final_result = {"age": age, "gender": gender, "race": ethnicity}
        await cache_data(
            f"{esId}~demographics",
            final_result,
            "cache_demographics",
        )
        return final_result
    else:
        return cache

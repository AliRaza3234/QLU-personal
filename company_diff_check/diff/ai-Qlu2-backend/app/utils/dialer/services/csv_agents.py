import pandas as pd
import json
import io
import asyncio
from fastapi import UploadFile, HTTPException

from qutils.llm.asynchronous import invoke
from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_MAIN_MODEL,
)


async def select_random_rows(df: pd.DataFrame, num_rows: int = 20) -> pd.DataFrame:
    df = df.copy()  # Ensure it's a new DataFrame instance

    if df.empty:
        raise ValueError("The input DataFrame is empty.")
    if num_rows <= 0:
        raise ValueError("The number of rows to select must be greater than zero.")
    if num_rows > len(df):
        raise ValueError(
            "The number of rows to select cannot exceed the DataFrame size."
        )

    sampled_df = df.sample(n=num_rows, random_state=None).reset_index(drop=True)

    return sampled_df


async def get_column_names_info(df_sample_data, column_name_dict):
    # Get column numbers from first row of sample data
    """Get formatted string of column names and numbers from sample data."""
    try:
        first_row = df_sample_data[0]
        column_numbers = list(first_row.keys())
        column_info = "\n\nColumn Names:"
        for col_num in column_numbers:
            if col_num in column_name_dict:
                column_info += f"\nColumn {col_num}: {column_name_dict[col_num]}"
        return column_info
    except:
        return ""


async def make_user_prompt(df_sample_data, column_name_dict, treat_first_row_as_header):
    prompt = "Here's the table information:"
    if treat_first_row_as_header:
        column_info = await get_column_names_info(df_sample_data, column_name_dict)
    else:
        column_info = ""

    if column_info:
        prompt += column_info

    sample_data_str = "\n".join(map(str, df_sample_data))
    prompt += "\n\nSample Data:\n" + sample_data_str
    prompt += "\n\nIdentify the relevant columns:\n"
    return prompt


async def identify_name_columns(
    df_sample_data, column_name_dict, treat_first_row_as_header
) -> dict:
    system_prompt = """
    You are an AI tasked with analyzing a dataset where each row is structured as a dictionary. In this dataset:
    - The keys represent column indices (e.g., `0`, `1`, etc.).
    - The values represent data for those columns, which may include single or multiple pieces of information.

    ### Your task:
    1. Identify which columns (keys) contain:
        - **Full Name**: A single column that contains both First Name and Last Name in one field (e.g., 'John Doe').
        - **First Name**: A column that contains only the first name (e.g., 'John').
        - **Last Name**: A column that contains only the last name (e.g., 'Doe').

    2. Prioritize checking for **full names**:
        - If a single column contains full names for all rows (both First and Last Name combined), tag it as `fullName`.
        - In this case, **do not** attempt to identify separate columns for `firstName` and `lastName`.

    3. If no full name column is detected:
        - Check for **First Name** and **Last Name** columns separately and assign them to their respective tags.

    ### Important considerations:
    - Analyze the **data in the values**, not the column names, as column names may be misleading or repetitive.
    - A column is considered to contain full names only if all or most of its rows include both First and Last Names.
    - A column is considered a First Name or Last Name column only if it consistently contains those values across rows.
    - It is necessary that names are explicitly there, not like in links or any other form.

    ### Output Format:
    Return your output as a JSON object with the following structure:
    ```json
    {
        "reason": "<Explanation of why certain columns were included or excluded with columns number mentioned>",
        "data": {
            "fullName": [<column index>] OR {
                "firstName": [<column index>],
                "lastName": [<column index>]
            }
        }
    }
    ```

    ### Examples:
    1. If column `0` contains full names (e.g., 'John Smith'), your output might look like:
    ```json
    {
        "reason": "Column 0 contains both First and Last Names combined in one field for all rows.",
        "data": {
            "fullName": [0]
        }
    }
    ```

    2. If separate columns `0` and `1` contain first and last names, respectively, your output might look like:
    ```json
    {   
        "reason": "Column 0 contains only First Names (e.g., 'John'), and column 1 contains only Last Names (e.g., 'Doe').",
        "data": {
            "firstName": [0],
            "lastName": [1]
        }
    }
    ```
    3. It is also possible that the first name and last name are in different columns, or may be only one column is present. In this case, your output might look like:
    ```json
    {
        "reason": "Column 0 contains only First Names (e.g., 'John')",
        "data": {
            "firstName": [0]
        }
    }
    ```
    or
    ```json
    {
        "reason": "Column 1 contains only Last Names (e.g., 'Doe')",
        "data": {
            "lastName": [1]
        }
    }
    ```

    4. If no consistent patterns are detected in the columns, your output might look like:
    ```json
    {
        "reason": "No columns consistently contained full names, first names, or last names.",
        "data": {}
    }
    ```

    Focus on consistency and provide explanations for your decisions in the `reason` field.
    """

    prompt = await make_user_prompt(
        df_sample_data, column_name_dict, treat_first_row_as_header
    )

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    try:
        response = await invoke(
            messages=chat,
            temperature=0.0,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
        json_response = json.loads(response)
        output = json_response.get("data", {})

    except Exception as e:
        raise Exception(f"Error in processing phone number identification: {e}")

    return output


async def identify_phone_columns(
    df_sample_data, column_name_dict, treat_first_row_as_header
) -> dict:
    system_prompt = """
    You are an AI that analyzes the content of a dataset where each row is structured as a dictionary. In this dictionary:
        - Each key represents a column index (e.g., `0`, `1`, etc.).
        - The associated value represents the data for that column.

    Your task is to:
    1. Identify which columns contain valid phone numbers by analyzing the values in each column. 
    2. Focus on patterns that match phone numbers, such as valid country codes and 10-15 digit sequences.

    Return your output as a JSON object with the following structure:
    {
        "reason": "<reason for including or excluding specific columns>",
        "data": {"phoneNumbers": [<column index>, <column index>, ...]}
    }

    Do not assume any specific column index. Always infer the relevant column(s) by analyzing the provided data.
    """

    prompt = await make_user_prompt(
        df_sample_data, column_name_dict, treat_first_row_as_header
    )

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        response = await invoke(
            messages=chat,
            temperature=0.0,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print(f"Error in LLM call: {e}")
        return {"phoneNumbers": []}  # Default return in case of failure

    try:
        output = json.loads(response)
        return output.get("data", {"phoneNumbers": []})  # Ensures expected structure

    except Exception as e:
        print(f"Error parsing response: {e}")
        return {"phoneNumbers": []}  # Default return if JSON is invalid


async def identify_linkedin_company_job_columns(
    df_sample_data, column_name_dict, treat_first_row_as_header
) -> dict:
    system_prompt = """
    You are an AI that analyzes a dataset where each row is structured as a dictionary. In this dataset:
    - The keys represent column indices (e.g., `"0"`, `"1"`, etc.).
    - The values represent data for those columns, which may contain multiple pieces of information.

    ### Your Task:
    1. **Identify which columns (keys) contain:**
    - **LinkedIn URLs:** Strings that start with `"https://www.linkedin.com/"`.  
    - **Company Names:** The column should contain only organization names (e.g., `"Huawei Consumer Business Group"`).  
        - **Do NOT select columns that contain:**  
        - URLs, links, or any web addresses.  
        - Longer descriptive text (sentences, job descriptions, or company bios).  
        - Text that is consistently longer than five words.  
    - **Job Titles:** Professional roles (e.g., `"Senior Retail Manager"`). 

    2. **Handle mixed-content columns:**
    - If a single column contains multiple pieces of information, extract and classify relevant parts accordingly.
    - If a column contains irrelevant or unclear data that does not fit these categories, ignore it.

    ### Output Format:
    Return a JSON object structured as follows:
    ```json
    {
        "reason": "<Explanation of why certain columns were included or excluded with columns number mentioned>",
        "data": {
            "linkedinURL": [<column index>, ...],
            "companyName": [<column index>, ...],
            "jobTitle": [<column index>, ...]
        }
    }
    ```
    Strict Validation Rules:
    - If a column does not clearly contain any required data, return an empty list for that category.
    - Do not assume missing or ambiguous values belong to any category.
    - Only classify data that explicitly matches the criteria.
"""

    prompt = await make_user_prompt(
        df_sample_data, column_name_dict, treat_first_row_as_header
    )

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        response = await invoke(
            messages=chat,
            temperature=0.0,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )

        if not response or response.strip() == "":
            return {"linkedinURL": [], "companyName": [], "jobTitle": []}

        output = json.loads(response)
        return output.get(
            "data", {"linkedinURL": [], "companyName": [], "jobTitle": []}
        )

    except Exception as e:
        return {"linkedinURL": [], "companyName": [], "jobTitle": []}


async def should_treat_first_row_as_header(first_row: list[str]) -> bool:
    system_prompt = "You are a helpful assistant that identifies if a row from a CSV file looks like column names or regular data."
    prompt = f"""Given the following list from a CSV file's first row:

{first_row}

Does it look like a list of **column names** or just **data**? Reply with exactly one word: "header" or "data"."""

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    decision = await invoke(
        messages=chat,
        temperature=0.0,
        model=GPT_MAIN_MODEL,
        response_format={"type": "text"},
    )
    return decision.lower().strip() == "header"


async def get_suggested_column_names(df: pd.DataFrame) -> list[str] | None:
    first_rows = df.head(5).values.tolist()

    system_prompt = """You are a data analyst assistant.

    Given the first few rows of a CSV file (with no column names), your task is to suggest short and meaningful column names based on the values.

    Return a JSON object with the following structure:
    {
        "reason": "<reason for the suggested column names>",
        "data": ["column name 1", "column name 2", "column name 3"]
    }
    """

    user_prompt = f"{first_rows}"

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await invoke(
        messages=chat,
        temperature=0.0,
        model=GPT_MAIN_MODEL,
        response_format={"type": "json_object"},
    )
    json_response = json.loads(response)
    output = json_response.get("data", [])
    return output


async def read_file_to_dataframe(file: UploadFile):
    try:
        file_content = file.file.read()
        treat_first_row_as_header = False

        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_content), header=None)

            if len(df) > 1:
                # Assume first row as tentative header
                df.columns = df.iloc[0]
                df.columns = [
                    f"Unnamed_{i}" if pd.isna(col) else col
                    for i, col in enumerate(df.columns)
                ]

                first_row = df.columns.tolist()
                treat_first_row_as_header = await should_treat_first_row_as_header(
                    first_row
                )

                if treat_first_row_as_header:
                    df = df[1:].reset_index(drop=True)
                else:
                    suggested_columns = await get_suggested_column_names(df)
                    len_suggested_columns = len(suggested_columns)
                    len_df_columns = len(df.columns)

                    if suggested_columns and len_suggested_columns == len_df_columns:
                        df.columns = suggested_columns
                        treat_first_row_as_header = True

        elif file.filename.endswith((".xls", ".xlsx")):
            df = pd.read_excel(io.BytesIO(file_content))

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload a CSV or Excel file.",
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    return df, treat_first_row_as_header


async def analyze_name_columns(sample_df, final_result):
    """Analyzes name columns to determine whether to use full names or combined first/last names.

    Args:
        sample_df (pd.DataFrame): The sample DataFrame containing the data
        final_result (dict): Dictionary containing identified column indices for different name types

    Returns:
        dict: Updated final_result with appropriate name columns
    """
    # Get sample values for comparison
    first_last_samples = []
    full_name_samples = []

    # Get up to 5 rows of first+last combinations
    first_name_cols = [
        sample_df.iloc[:5, col].values for col in final_result["firstName"]
    ]
    last_name_cols = [
        sample_df.iloc[:5, col].values for col in final_result["lastName"]
    ]
    for f_col in first_name_cols:
        for l_col in last_name_cols:
            first_last_samples.extend(
                [f"{f} {l}".strip() for f, l in zip(f_col, l_col)]
            )

    # Get up to 5 rows of fullName values
    for col in final_result["fullName"]:
        full_name_samples.extend(sample_df.iloc[:5, col].values)

    # Prepare prompt for LLM
    prompt = f"""Given these two sets of name data, which appears more complete and reliable?
    Set 1 (Combined first and last names): {first_last_samples[:5]}
    Set 2 (Full names): {full_name_samples[:5]}
    
    Reply with exactly one word: either 'full' or 'combined'"""

    chat = [
        {
            "role": "system",
            "content": "You are a helpful assistant that analyzes name data. Respond with exactly one word: either 'full' or 'combined'.",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        response = await invoke(
            messages=chat,
            temperature=0.0,
            model=GPT_MAIN_MODEL,
            response_format={"type": "text"},
        )
        llm_choice = response.strip().lower()
        if llm_choice not in ["full", "combined"]:
            llm_choice = "full"
    except Exception as e:
        print(f"Error in LLM call for name analysis: {e}")
        llm_choice = "full"

    if llm_choice == "combined":
        final_result.pop("fullName", None)
    else:
        final_result.pop("firstName", None)
        final_result.pop("lastName", None)

    return final_result


async def processing_csv(file):
    try:
        df, treat_first_row_as_header = await read_file_to_dataframe(file)
        sample_rows = len(df)
        sample_df = df
        column_name_dict = {idx: col for idx, col in enumerate(sample_df.columns)}

        max_columns = 15
        if len(df.columns) > max_columns:
            df_chunks = await split_dataframe_columns(
                sample_df, max_columns=max_columns
            )
            sample_data = []
            for i in range(len(df_chunks)):
                chunk = df_chunks[i]
                chunk.columns = [
                    f"{col}_{idx}" for idx, col in enumerate(chunk.columns)
                ]
                idx_new = i * max_columns
                temp_data = (
                    chunk.head(sample_rows)
                    .rename(
                        columns={
                            col: idx + idx_new for idx, col in enumerate(chunk.columns)
                        }
                    )
                    .to_dict(orient="records")
                )
                sample_data.append(temp_data)
        else:
            sample_data = [
                (
                    sample_df.head(sample_rows)
                    .rename(columns={col: idx for idx, col in enumerate(df.columns)})
                    .to_dict(orient="records")
                )
            ]

        tasks = [
            process_dataframe_chunk(chunk, column_name_dict, treat_first_row_as_header)
            for chunk in sample_data
        ]
        results = await asyncio.gather(*tasks)

        final_result = {}
        for res in results:
            for key, value in res.items():
                if key not in final_result:
                    final_result[key] = set(value)
                else:
                    final_result[key].update(value)
        final_result = {
            key: sorted(map(int, value)) for key, value in final_result.items()
        }

        # Check if we have both name combinations (first+last and full)
        if (
            "firstName" in final_result and "lastName" in final_result
        ) and "fullName" in final_result:
            final_result = await analyze_name_columns(sample_df, final_result)

        return final_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def split_dataframe_columns(df, max_columns=15):
    """Splits a DataFrame into chunks based on the number of columns."""
    num_splits = (len(df.columns) // max_columns) + (
        1 if len(df.columns) % max_columns != 0 else 0
    )
    return [
        df.iloc[:, i * max_columns : (i + 1) * max_columns] for i in range(num_splits)
    ]


async def process_dataframe_chunk(
    df_chunk, column_name_dict, treat_first_row_as_header
):
    """Processes a chunk of the DataFrame asynchronously."""
    task1 = identify_name_columns(
        df_sample_data=df_chunk,
        column_name_dict=column_name_dict,
        treat_first_row_as_header=treat_first_row_as_header,
    )
    task2 = identify_linkedin_company_job_columns(
        df_sample_data=df_chunk,
        column_name_dict=column_name_dict,
        treat_first_row_as_header=treat_first_row_as_header,
    )
    name_columns, name_linkedin_columns = await asyncio.gather(task1, task2)

    phone_columns = await identify_phone_columns(
        df_sample_data=df_chunk,
        column_name_dict=column_name_dict,
        treat_first_row_as_header=treat_first_row_as_header,
    )

    result = name_columns.copy()
    result.update(phone_columns)
    result.update(name_linkedin_columns)

    # Ensure all values in the lists are unique
    for key in result:
        if result[key]:  # Check if the list is not empty
            result[key] = list(set(result[key]))

    return result

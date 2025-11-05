import json
from app.core.database import (
    postgres_fetch_all,
    postgres_insert,
    postgres_delete,
    postgres_fetch,
)


async def get_cache(
    es_id,
    type=None,
    service_type=None,
    groups=None,
    rank=None,
    function=None,
    experience_indices=None,
):
    where_clause = f"WHERE esId = '{es_id}'"
    if type:
        where_clause += f" AND type = '{type}'"

    if service_type:
        where_clause += f" AND serviceType = '{service_type}'"

    if groups:
        where_clause += f" AND groups = '{groups}'"

    if rank:
        where_clause += f" AND rank = '{rank}'"

    if function:
        where_clause += f" AND function = '{function}'"

    if experience_indices and len(experience_indices) >= 1:
        where_clause += f" AND experienceIndices = '{experience_indices}'"

    query = f"""
        SELECT similarProfile, esid_updatedat
        FROM cache_similar_profiles
        {where_clause}
    """

    rows = await postgres_fetch_all(query)
    if rows:
        similar_profiles = [row[0] for row in rows]
        esid_updatedat = [row[1] for row in rows]
        return similar_profiles, esid_updatedat
    return None


async def set_cache(
    es_id,
    similar_profiles,
    type,
    service_type,
    expiration,
    groups=None,
    rank=None,
    function=None,
    experience_indices=None,
    esId_updatedAt=None,
):
    """
    Inserts or updates records in the `cache_similar_profiles` table.

    Parameters:
        es_id (str): The primary ID for the entry.
        similar_profiles (list[dict]): A list of similar profile data to be stored as JSONB.
        type (str): Type of the profile.
        service_type (str): Service type for the profile.
        expiration (str): Expiration timestamp.
        groups (str, optional): Group information.
        experience_indices (str, optional): Experience indices.
        esId_updatedAt (str, optional): Last updated timestamp for esId.

    Returns:
        bool: True if the operation succeeds, False otherwise.
    """
    base_columns = ["esId", "type", "serviceType", "similarProfile", "expiration"]
    dynamic_values = [es_id, type, service_type, None, expiration]

    if groups is not None:
        base_columns.append("groups")
        dynamic_values.append(groups)
    if rank is not None:
        base_columns.append("rank")
        dynamic_values.append(rank)
    if function is not None:
        base_columns.append("function")
        dynamic_values.append(function)
    if experience_indices is not None:
        base_columns.append("experienceIndices")
        dynamic_values.append(experience_indices)
    if esId_updatedAt is not None:
        base_columns.append("esId_updatedAt")
        esId_updatedAt = json.dumps(esId_updatedAt)
        dynamic_values.append(esId_updatedAt)

    insert_columns = ", ".join(base_columns)

    values_list = []
    for profile in similar_profiles:
        values = dynamic_values.copy()
        values[3] = json.dumps(profile)

        value_row = (
            "("
            + ", ".join(f"'{val}'" if val is not None else "NULL" for val in values)
            + ")"
        )
        values_list.append(value_row)

    values_clause = ", ".join(values_list)

    query = f"""
        INSERT INTO cache_similar_profiles ({insert_columns})
        VALUES {values_clause}
    """

    try:
        success = await postgres_insert(query)
        return success
    except Exception as e:
        print(f"Error executing query: {e}")
        return False


async def delete_cache(
    es_id=None, type=None, service_type=None, groups=None, experience_indices=None
):
    """
    Deletes records from the `cache_similar_profiles` table based on the provided criteria.

    Parameters:
        es_id (str, optional): The primary ID for the entry. If None, all entries matching other criteria will be deleted.
        type (str, optional): Type of the profile.
        service_type (str, optional): Service type for the profile.
        groups (str, optional): Group information.
        experience_indices (str, optional): Experience indices.
    Returns:
        bool: True if the operation succeeds, False otherwise.
    """
    where_clause = []

    if es_id:
        where_clause.append(f"esId = '{es_id}'")

    where_clause = " AND ".join(where_clause)

    if where_clause:
        query = f"DELETE FROM cache_similar_profiles WHERE {where_clause}"
    else:
        raise ValueError(
            "No conditions provided for deletion. Specify at least one parameter."
        )

    success = await postgres_delete(query)
    return success


async def get_similar_companies(universal_name, type=None, industry=None):
    """
    Fetches similar companies from the `cache_similar_companies` table.

    Parameters:
        universal_name (str): The universal name of the company.
        type (str, optional): Type of the company.
        industry (list[str], optional): List of industries.

    Returns:
        list[dict]: List of similar companies if found, None otherwise.
    """
    where_conditions = [f"universal_name = '{universal_name}'"]

    if type:
        where_conditions.append(f"type = '{type}'")

    if industry:
        where_conditions.append(f"industries @> '{json.dumps(industry)}'::jsonb")
    else:
        where_conditions.append(
            "(industries IS NULL OR industries = '{}'::jsonb OR industries = '[]'::jsonb)"
        )

    where_clause = "WHERE " + " AND ".join(where_conditions)

    query = f"""
        SELECT similar_companies
        FROM cache_similar_companies
        {where_clause}
    """

    rows = await postgres_fetch_all(query)
    if rows:
        similar_companies = [row[0] for row in rows]
        return similar_companies
    return None


async def set_similar_companies(
    universal_name, type, similar_companies, industries=None
):
    """
    Inserts or updates records in the `cache_similar_companies` table.

    Parameters:
        universal_name (str): The universal name of the company.
        type (str): Type of the company.
        similar_companies (list[dict]): A list of similar companies as JSONB.
        industries (list[str], optional): A list of industries.

    Returns:
        bool: True if the operation succeeds, False otherwise.
    """
    insert_columns = ["universal_name", "type", "similar_companies", "industries"]
    industries_value = f"'{json.dumps(industries)}'" if industries else "'[]'"
    values = [
        f"'{universal_name}'",
        f"'{type}'",
        f"'{json.dumps(similar_companies)}'",
        industries_value,
    ]

    query = f"""
        INSERT INTO cache_similar_companies ({', '.join(insert_columns)})
        VALUES ({', '.join(values)})
        ON CONFLICT (universal_name, type, industries)
        DO UPDATE SET similar_companies = EXCLUDED.similar_companies
    """

    try:
        success = await postgres_insert(query)
        return success
    except Exception as e:
        print(f"Error executing query: {e}")
        return False


async def delete_similar_companies(universal_name=None, type=None, industry=None):
    """
    Deletes records from the `cache_similar_companies` table based on the provided criteria
    and if the cache is older than 30 days.

    Parameters:
        universal_name (str, optional): The universal name of the company.
        type (str, optional): Type of the company.
        industry (list or dict, optional): Industries for the company (stored as JSON).

    Returns:
        bool: True if the operation succeeds, False otherwise.
    """
    where_clause = ["insertion_timestamp < NOW() - INTERVAL '30 days'"]

    if universal_name:
        where_clause.append(f"universal_name = '{universal_name}'")

    if type:
        where_clause.append(f"type = '{type}'")

    if industry:
        industry_json = json.dumps(industry)
        where_clause.append(f"industries @> '{industry_json}'::jsonb")

    if not where_clause:
        raise ValueError(
            "No conditions provided for deletion. Specify at least one parameter or old cache cleanup."
        )

    final_where_clause = " AND ".join(where_clause)

    query = f"DELETE FROM cache_similar_companies WHERE {final_where_clause}"
    success = await postgres_delete(query)
    return success


async def check_cache_expiry(universal_name, industry):
    """
    Checks if ANY cache entry for the given `universal_name`
    (across p2p_companies, llm_companies, and companies_through_industry)
    is older than 30 days.

    Parameters:
        universal_name (str): The universal name of the company.
        industry (list or dict, optional): Industry filter.

    Returns:
        bool: True if there is ANY entry older than 30 days, otherwise False.
    """

    where_conditions = [
        f"universal_name = '{universal_name}'",
        "type IN ('p2p_companies', 'llm_companies', 'companies_through_industry')",
        "insertion_timestamp < NOW() - INTERVAL '30 days'",
    ]

    if industry:
        industry_json = json.dumps(industry)
        where_conditions.append(f"industries @> '{industry_json}'::jsonb")
    else:
        where_conditions.append(
            "(industries IS NULL OR industries = '{}'::jsonb OR industries = '[]'::jsonb)"
        )

    where_clause = " AND ".join(where_conditions)

    query = f"""
        SELECT universal_name, type, insertion_timestamp
        FROM cache_similar_companies
        WHERE {where_clause}
    """

    rows = await postgres_fetch(query)
    has_expired_data = bool(rows)
    return has_expired_data

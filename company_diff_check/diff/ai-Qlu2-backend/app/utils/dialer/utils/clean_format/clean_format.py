import contractions, re


def clean_and_combine_texts(text_list: list) -> str:
    """
    Cleans and combines a list of text strings into a single, formatted string.

    Args:
    - text_list (list of str): List of text strings to be combined and cleaned.

    Returns:
    - str: A single, cleaned and combined text string.
    """

    combined_text = " ".join(text_list)
    combined_text = combined_text.lower()
    combined_text = contractions.fix(combined_text)
    combined_text_no_punctuation = re.sub(r"[^\w\s]", "", combined_text)
    cleaned_text = re.sub(r"\s+", " ", combined_text_no_punctuation).strip()
    return cleaned_text


def text_indexed_converter(text_list: list) -> str:
    """
    Converts a list of texts into a formatted string with index labels.

    Args:
    - text_list (list of str): List of text strings.

    Returns:
    - str: A formatted string with each text labeled by its index.
    """

    result = ""
    for idx, text in enumerate(text_list):
        result += f"{idx}: {text}\n"

    return result

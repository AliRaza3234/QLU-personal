from pydantic import BaseModel, model_validator
from app.utils.search.qsearch.autocomplete.prompts import DATA_DICT


class AutoCompleteInput(BaseModel):
    uncomplete_entity: str
    entity_type: str

    @model_validator(mode="after")
    def validate_entity_type(self):
        allowed_values = set([i for i in DATA_DICT])
        if self.entity_type.lower() not in allowed_values:
            raise ValueError(f"entity_type must be one of {allowed_values}")
        return self


class AutoCompleteOutput(BaseModel):
    entity_list: list[str]

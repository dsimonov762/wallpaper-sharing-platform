"""Base DTOs. The wire format is camelCase, Python code stays snake_case."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Responses: serialize as camelCase; Python code may build them with snake_case names."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ApiRequest(ApiModel):
    """Requests: only the camelCase names are accepted and unknown fields are rejected."""

    model_config = ConfigDict(populate_by_name=False, extra="forbid")

"""Api schema."""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """QueryRequest."""

    input_text: str


class QueryResponse(BaseModel):
    """QueryResponse."""

    input_text: str
    output_text: str


class JobRequest(BaseModel):
    """JobRequest."""

    input_text: str


class JobResponse(BaseModel):
    """JobResponse."""

    input_text: str
    output_text: str

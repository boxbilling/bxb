from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Individual search result across all resource types."""

    type: str = Field(
        ...,
        description="Resource type (customer, invoice, subscription, plan)",
    )
    id: str
    title: str = Field(..., description="Primary display title")
    subtitle: str | None = Field(default=None, description="Secondary display info")
    url: str = Field(..., description="Resource URL path for navigation")


class GlobalSearchResponse(BaseModel):
    """Response for global search endpoint."""

    query: str
    results: list[SearchResult] = Field(default_factory=list)
    total_count: int

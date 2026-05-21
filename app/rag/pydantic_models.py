from pydantic import BaseModel, Field


class SectionRef(BaseModel):
    # We use Optional and default=None to handle the "use null for missing fields" requirement
    chapter: str | None = Field(default=None, description="The chapter title")
    section: str | None = Field(default=None, description="The section title")
    subsection: str | None = Field(default=None, description="The subsection title")


class RAGSearchAgentResponse(BaseModel):
    """Agent's decision about which sections to fetch directly."""

    source_name: str = Field(description="The document's source_name from get_document_structure")
    selected_sections: list[SectionRef] = Field(
        description="Sections to retrieve, matching values from get_document_structure exactly"
    )

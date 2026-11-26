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


class DocumentSections(BaseModel):
    """The sections selected from one document."""

    document_id: int = Field(description="The document's id.")
    sections: list[SectionRef] = Field(description="The sections the request needs.")


class SectionSelection(BaseModel):
    """The sections of the attached documents that a request needs."""

    documents: list[DocumentSections] = Field(default_factory=list, description="The documents the request draws on.")
    unavailable: str | None = Field(
        default=None,
        description="Which document couldn't be read and why, such as one still processing, in one sentence.",
    )

from pydantic import BaseModel, Field


class Auth(BaseModel):
    api_url: str = Field(..., description="Moodle site URL")
    api_token: str = Field(..., description="Moodle web service token")

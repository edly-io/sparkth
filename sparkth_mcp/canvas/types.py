from enum import Enum
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class AuthenticationPayload(BaseModel):
    api_url: str
    api_token: str


class CourseFormat(str, Enum):
    on_campus = "on_campus"
    online = "online"
    blended = "blended"


class Course(BaseModel):
    name: str
    course_code: Optional[str] = None
    sis_course_id: Optional[int] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_public: Optional[bool] = None
    course_format: Optional[CourseFormat] = None
    post_manually: Optional[bool] = None


class CoursePayload(BaseModel):
    course: Course
    enroll_me: bool
    offer: Optional[bool] = None
    enable_sis_reactivation: Optional[bool] = None
    account_id: int
    auth: AuthenticationPayload


class ModuleParams(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    module_id: int


class Module(BaseModel):
    name: str
    position: Optional[int] = None
    unlock_at: Optional[datetime] = None
    require_sequential_progress: Optional[bool] = None
    prerequisite_module_ids: Optional[List[int]] = None
    publish_final_grade: Optional[bool] = None


class ModulePayload(BaseModel):
    module: Module
    course_id: int
    auth: AuthenticationPayload


class UpdatedModule(BaseModel):
    name: Optional[str] = None
    position: Optional[int] = None
    unlock_at: Optional[datetime] = None
    require_sequential_progress: Optional[bool] = None
    prerequisite_module_ids: Optional[List[int]] = None
    publish_final_grade: Optional[bool] = None
    published: Optional[bool] = None


class UpdateModulePayload(BaseModel):
    module: UpdatedModule
    course_id: int
    module_id: int
    auth: AuthenticationPayload

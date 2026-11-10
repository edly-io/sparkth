from sparkth.lib.compose.hooks import register_agent
from sparkth.lib.frontend.hooks import DISPLAY_INFO, DisplayInfo
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.plugins import SparkthPlugin
from sparkth.plugins.course_design.agent import COURSE_DESIGN


class CourseDesignPlugin(SparkthPlugin):
    """Designs courses, lessons and written assessments in Compose."""

    def __init__(self) -> None:
        super().__init__("course-design")
        DISPLAY_INFO.add_item(
            self,
            DisplayInfo(
                gettext_noop("Course design"),
                gettext_noop("Design courses, lessons and written assessments"),
            ),
        )
        register_agent(self, COURSE_DESIGN)

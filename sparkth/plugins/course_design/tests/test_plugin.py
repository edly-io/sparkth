from sparkth.lib.compose.hooks import COMPOSE_AGENTS, enabled_agents
from sparkth.lib.frontend import get_plugin_display_info
from sparkth.lib.plugins import get_plugin_loader
from sparkth.plugins.course_design.agent import COURSE_DESIGN
from sparkth.plugins.course_design.plugin import CourseDesignPlugin


def test_the_plugin_is_named_course_design() -> None:
    assert CourseDesignPlugin().name == "course-design"


def test_the_plugin_declares_display_info() -> None:
    plugin = CourseDesignPlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    display = get_plugin_display_info("course-design")
    assert display is not None
    assert display.display_name == "Course design"
    assert display.description == "Design courses, lessons and written assessments"


def test_the_plugin_is_loaded_by_the_loader() -> None:
    loaded_names = [name for name, _ in get_plugin_loader().get_loaded_plugins()]

    assert "course-design" in loaded_names


def test_the_plugin_contributes_the_course_design_agent() -> None:
    plugin = CourseDesignPlugin()

    assert [item for owner, item in COMPOSE_AGENTS.iter_items() if owner is plugin] == [COURSE_DESIGN]


def test_the_agent_is_offered_once_after_a_second_construction() -> None:
    """The loader builds the plugin, and tests build it again; the agent is offered once."""
    plugin = CourseDesignPlugin()  # noqa: F841 - keeps the weakly-keyed hook entry alive

    assert enabled_agents(set()).count(COURSE_DESIGN) == 1

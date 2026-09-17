<?php
namespace local_sparkth\external;

use context_course;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Append a section to a course and set its name and summary.
 *
 * @package    local_sparkth
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class create_section extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'course id', VALUE_REQUIRED),
            'name'     => new external_value(PARAM_TEXT, 'section name', VALUE_REQUIRED),
            'summary'  => new external_value(PARAM_RAW, 'section summary HTML', VALUE_DEFAULT, ''),
        ]);
    }

    /**
     * @return array{id: int, sectionnum: int}
     */
    public static function execute(int $courseid, string $name, string $summary = ''): array {
        global $CFG, $DB;
        require_once($CFG->dirroot . '/course/lib.php');

        ['courseid' => $courseid, 'name' => $name, 'summary' => $summary] =
            self::validate_parameters(self::execute_parameters(), [
                'courseid' => $courseid, 'name' => $name, 'summary' => $summary,
            ]);

        $course = $DB->get_record('course', ['id' => $courseid], '*', MUST_EXIST);
        $context = context_course::instance($course->id);
        self::validate_context($context);
        require_capability('moodle/course:manageactivities', $context);

        $section = course_create_section($course->id);
        course_update_section($course, $section, [
            'name'          => $name,
            'summary'       => $summary,
            'summaryformat' => FORMAT_HTML,
        ]);

        return ['id' => (int) $section->id, 'sectionnum' => (int) $section->section];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'id'         => new external_value(PARAM_INT, 'course_sections row id'),
            'sectionnum' => new external_value(PARAM_INT, 'section number within the course'),
        ]);
    }
}

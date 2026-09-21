<?php
namespace local_sparkth\external;

use context_course;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;
use stdClass;

/**
 * Create a Page activity carrying HTML content.
 *
 * @package    local_sparkth
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class create_page extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'   => new external_value(PARAM_INT, 'course id', VALUE_REQUIRED),
            'sectionnum' => new external_value(PARAM_INT, 'section number', VALUE_REQUIRED),
            'name'       => new external_value(PARAM_TEXT, 'activity name', VALUE_REQUIRED),
            'content'    => new external_value(PARAM_RAW, 'page body HTML', VALUE_REQUIRED),
            'intro'      => new external_value(PARAM_RAW, 'activity description HTML', VALUE_DEFAULT, ''),
        ]);
    }

    /**
     * @return array{cmid: int, instanceid: int}
     */
    public static function execute(
        int $courseid,
        int $sectionnum,
        string $name,
        string $content,
        string $intro = ''
    ): array {
        global $CFG, $DB;
        require_once($CFG->dirroot . '/course/modlib.php');
        require_once($CFG->libdir . '/resourcelib.php');

        [
            'courseid' => $courseid, 'sectionnum' => $sectionnum, 'name' => $name,
            'content' => $content, 'intro' => $intro,
        ] = self::validate_parameters(self::execute_parameters(), [
            'courseid' => $courseid, 'sectionnum' => $sectionnum, 'name' => $name,
            'content' => $content, 'intro' => $intro,
        ]);

        $course = $DB->get_record('course', ['id' => $courseid], '*', MUST_EXIST);
        $context = context_course::instance($course->id);
        self::validate_context($context);
        require_capability('moodle/course:manageactivities', $context);

        // page_add_instance() only reads the editor array when called from a form.
        // Called programmatically it inserts the record as-is, so the content and
        // contentformat columns are set directly.
        $moduleinfo = new stdClass();
        $moduleinfo->modulename        = 'page';
        $moduleinfo->module            = $DB->get_field('modules', 'id', ['name' => 'page'], MUST_EXIST);
        $moduleinfo->course            = $course->id;
        $moduleinfo->section           = $sectionnum;
        $moduleinfo->name              = $name;
        $moduleinfo->intro             = $intro;
        $moduleinfo->introformat       = FORMAT_HTML;
        $moduleinfo->content           = $content;
        $moduleinfo->contentformat     = FORMAT_HTML;
        $moduleinfo->display           = RESOURCELIB_DISPLAY_AUTO;
        $moduleinfo->printintro        = 0;
        $moduleinfo->printlastmodified = 1;
        $moduleinfo->visible           = 1;

        $created = add_moduleinfo($moduleinfo, $course);

        return ['cmid' => (int) $created->coursemodule, 'instanceid' => (int) $created->instance];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'cmid'       => new external_value(PARAM_INT, 'course module id'),
            'instanceid' => new external_value(PARAM_INT, 'page instance id'),
        ]);
    }
}

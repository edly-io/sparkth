<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <http://www.gnu.org/licenses/>.

namespace local_sparkth\external;

use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Append a section to a course and set its name and summary.
 *
 * @package    local_sparkth
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class create_section extends course_external {

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
        global $CFG;
        require_once($CFG->dirroot . '/course/lib.php');

        ['courseid' => $courseid, 'name' => $name, 'summary' => $summary] =
            self::validate_parameters(self::execute_parameters(), [
                'courseid' => $courseid, 'name' => $name, 'summary' => $summary,
            ]);

        $course = self::require_course_access($courseid);

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

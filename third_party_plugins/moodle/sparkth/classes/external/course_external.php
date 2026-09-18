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

use context_course;
use core_external\external_api;
use stdClass;

/**
 * Shared entry guard for the externals that author inside a course.
 *
 * validate_context() is protected on external_api, so this has to be a base class
 * rather than a helper the functions call.
 *
 * @package    local_sparkth
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
abstract class course_external extends external_api {

    /**
     * Resolve the course, set up the call's context and require authoring rights.
     *
     * Passing $sectionnum also asserts the section exists, which callers that place an
     * activity need before add_moduleinfo() silently creates one.
     *
     * @param int $courseid course to author in
     * @param int|null $sectionnum section that must exist, or null to skip that check
     * @return stdClass the course record
     */
    protected static function require_course_access(int $courseid, ?int $sectionnum = null): stdClass {
        global $DB;

        $course = $DB->get_record('course', ['id' => $courseid], '*', MUST_EXIST);
        $context = context_course::instance($course->id);
        self::validate_context($context);
        require_capability('moodle/course:manageactivities', $context);

        if ($sectionnum !== null) {
            $DB->get_record('course_sections',
                ['course' => $course->id, 'section' => $sectionnum], 'id', MUST_EXIST);
        }

        return $course;
    }
}

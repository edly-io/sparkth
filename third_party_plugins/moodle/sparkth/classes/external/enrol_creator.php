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
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Enrol the token's user into a course using the site's configured creator role.
 *
 * core_course_external::create_courses() does not enrol the creator; course/edit.php
 * does, via enrol_try_internal_enrol() with $CFG->creatornewroleid. This mirrors that
 * guard for a course created over web services.
 *
 * @package    local_sparkth
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class enrol_creator extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'course id', VALUE_REQUIRED),
        ]);
    }

    /**
     * Enrol the current user into $courseid with the site's creator role, if configured.
     *
     * @return array{enrolled: bool, roleid: int}
     */
    public static function execute(int $courseid): array {
        global $CFG, $DB, $USER;
        require_once($CFG->libdir . '/enrollib.php');

        ['courseid' => $courseid] = self::validate_parameters(
            self::execute_parameters(), ['courseid' => $courseid]);

        $course = $DB->get_record('course', ['id' => $courseid], '*', MUST_EXIST);
        $context = context_course::instance($course->id);
        self::validate_context($context);
        require_capability('moodle/course:manageactivities', $context);

        $roleid = (int) ($CFG->creatornewroleid ?? 0);
        if ($roleid <= 0 || is_enrolled($context, null, 'moodle/role:assign')) {
            return ['enrolled' => false, 'roleid' => 0];
        }

        $enrolled = enrol_try_internal_enrol($course->id, $USER->id, $roleid);

        return ['enrolled' => $enrolled, 'roleid' => $enrolled ? $roleid : 0];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'enrolled' => new external_value(PARAM_BOOL, 'whether this call enrolled the user'),
            'roleid'   => new external_value(PARAM_INT, 'role used to enrol; 0 when not enrolled'),
        ]);
    }
}

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

defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_sparkth_create_section' => [
        'classname'   => 'local_sparkth\external\create_section',
        'methodname'  => 'execute',
        'description' => 'Append a section to a course and set its name and summary.',
        'type'        => 'write',
        'ajax'        => false,
    ],
    'local_sparkth_create_page' => [
        'classname'   => 'local_sparkth\external\create_page',
        'methodname'  => 'execute',
        'description' => 'Create a Page activity carrying HTML content.',
        'type'        => 'write',
        'ajax'        => false,
    ],
    'local_sparkth_create_quiz' => [
        'classname'   => 'local_sparkth\external\create_quiz',
        'methodname'  => 'execute',
        'description' => 'Create a Quiz activity with its questions.',
        'type'        => 'write',
        'ajax'        => false,
    ],
];

$services = [
    'Sparkth publishing' => [
        'shortname'       => 'local_sparkth',
        'functions'       => [
            'local_sparkth_create_section',
            'local_sparkth_create_page',
            'local_sparkth_create_quiz',
            'core_webservice_get_site_info',
            'core_enrol_get_users_courses',
            'core_course_create_courses',
        ],
        'restrictedusers' => 1,
        'enabled'         => 1,
    ],
];

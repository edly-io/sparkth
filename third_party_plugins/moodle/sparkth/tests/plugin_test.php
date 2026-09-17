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

namespace local_sparkth;

/**
 * Installation-level checks: the plugin registers itself and its web service functions.
 */
final class plugin_test extends \advanced_testcase {
    public function test_plugin_is_installed(): void {
        $this->resetAfterTest();
        $this->assertNotEmpty(get_config('local_sparkth', 'version'));
    }

    public function test_declared_functions_are_registered(): void {
        global $DB;
        $this->resetAfterTest();
        $this->assertTrue($DB->record_exists('external_functions',
            ['name' => 'local_sparkth_create_section']));
    }

    public function test_service_exposes_all_declared_functions(): void {
        global $DB;
        $this->resetAfterTest();
        $service = $DB->get_record('external_services', ['shortname' => 'local_sparkth']);
        $this->assertNotEmpty($service);
        foreach ([
            'local_sparkth_create_section',
            'local_sparkth_create_page',
            'local_sparkth_create_quiz',
        ] as $functionname) {
            $this->assertTrue($DB->record_exists('external_services_functions', [
                'externalserviceid' => $service->id,
                'functionname'      => $functionname,
            ]));
        }
    }
}

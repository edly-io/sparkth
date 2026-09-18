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

/**
 * @covers \local_sparkth\external\enrol_creator
 */
final class enrol_creator_test extends \core_external\tests\externallib_testcase {

    public function test_enrols_a_capable_user_with_the_configured_role(): void {
        $this->resetAfterTest();
        global $DB, $USER;
        $course = $this->getDataGenerator()->create_course();
        $roleid = $DB->get_field('role', 'id', ['shortname' => 'editingteacher'], MUST_EXIST);
        set_config('creatornewroleid', $roleid);
        $this->setAdminUser();

        $result = enrol_creator::execute($course->id);
        $result = \core_external\external_api::clean_returnvalue(
            enrol_creator::execute_returns(), $result);

        $this->assertTrue($result['enrolled']);
        $this->assertSame((int) $roleid, $result['roleid']);

        $context = \context_course::instance($course->id);
        $this->assertTrue(is_enrolled($context, $USER));
    }

    public function test_second_call_does_not_double_enrol(): void {
        $this->resetAfterTest();
        global $DB, $USER;
        $course = $this->getDataGenerator()->create_course();
        $roleid = $DB->get_field('role', 'id', ['shortname' => 'editingteacher'], MUST_EXIST);
        set_config('creatornewroleid', $roleid);
        $this->setAdminUser();

        enrol_creator::execute($course->id);
        $second = enrol_creator::execute($course->id);

        $this->assertFalse($second['enrolled']);
        $this->assertSame(0, $second['roleid']);
        $this->assertSame(1, $DB->count_records('user_enrolments', ['userid' => $USER->id]));
    }

    public function test_does_nothing_when_the_site_has_no_creator_role_configured(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course();
        set_config('creatornewroleid', 0);
        $this->setAdminUser();

        $result = enrol_creator::execute($course->id);

        $this->assertFalse($result['enrolled']);
        $this->assertSame(0, $result['roleid']);
    }

    public function test_requires_manageactivities_capability(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course();
        $user = $this->getDataGenerator()->create_and_enrol($course, 'student');
        $this->setUser($user);

        $this->expectException(\required_capability_exception::class);
        enrol_creator::execute($course->id);
    }
}

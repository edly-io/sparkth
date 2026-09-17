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
 * @covers \local_sparkth\external\create_page
 */
final class create_page_test extends \core_external\tests\externallib_testcase {

    public function test_creates_a_page_with_its_html_body(): void {
        global $DB;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        $result = create_page::execute(
            $course->id, $section['sectionnum'], 'Lesson One',
            '<h2>Hello</h2><p>Body copy.</p>', '<p>desc</p>');
        $result = \core_external\external_api::clean_returnvalue(
            create_page::execute_returns(), $result);

        $row = $DB->get_record('page', ['id' => $result['instanceid']]);
        $this->assertSame('Lesson One', $row->name);
        $this->assertSame('<h2>Hello</h2><p>Body copy.</p>', $row->content);
        $this->assertEquals(FORMAT_HTML, $row->contentformat);
    }

    public function test_page_lands_in_the_requested_section(): void {
        global $DB;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        create_section::execute($course->id, 'Module 1', '');
        $second = create_section::execute($course->id, 'Module 2', '');

        $result = create_page::execute($course->id, $second['sectionnum'], 'L', '<p>x</p>', '');

        $cm = $DB->get_record('course_modules', ['id' => $result['cmid']]);
        $this->assertSame((int) $second['id'], (int) $cm->section);
    }

    public function test_requires_manageactivities_capability(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $user = $this->getDataGenerator()->create_and_enrol($course, 'student');
        $this->setUser($user);

        $this->expectException(\required_capability_exception::class);
        create_page::execute($course->id, 1, 'L', '<p>x</p>', '');
    }

    public function test_rejects_a_sectionnum_the_course_does_not_have(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();

        $this->expectException(\dml_missing_record_exception::class);
        create_page::execute($course->id, 47, 'L', '<p>x</p>', '');
    }
}

<?php
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
}

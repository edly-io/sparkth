<?php
namespace local_sparkth\external;

/**
 * @covers \local_sparkth\external\create_section
 */
final class create_section_test extends \core_external\tests\externallib_testcase {

    public function test_appends_a_named_section(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();

        $result = create_section::execute($course->id, 'Module 1', '<p>intro</p>');
        $result = \core_external\external_api::clean_returnvalue(
            create_section::execute_returns(), $result);

        $this->assertSame(1, $result['sectionnum']);

        global $DB;
        $row = $DB->get_record('course_sections', ['id' => $result['id']]);
        $this->assertSame('Module 1', $row->name);
        $this->assertSame('<p>intro</p>', $row->summary);
    }

    public function test_second_call_appends_section_two(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();

        create_section::execute($course->id, 'Module 1', '');
        $second = create_section::execute($course->id, 'Module 2', '');

        $this->assertSame(2, $second['sectionnum']);
    }

    public function test_requires_manageactivities_capability(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course();
        $user = $this->getDataGenerator()->create_and_enrol($course, 'student');
        $this->setUser($user);

        $this->expectException(\required_capability_exception::class);
        create_section::execute($course->id, 'Module 1', '');
    }
}

<?php
namespace local_sparkth;

/**
 * @covers \local_sparkth
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
}

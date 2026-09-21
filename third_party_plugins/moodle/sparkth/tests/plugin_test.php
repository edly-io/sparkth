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

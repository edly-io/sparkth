<?php
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
        ],
        'restrictedusers' => 1,
        'enabled'         => 1,
    ],
];

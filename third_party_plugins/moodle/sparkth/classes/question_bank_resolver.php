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

use context_course;
use context_module;
use core_question\local\bank\question_bank_helper;
use stdClass;

/**
 * Resolves the question category to author into, across Moodle versions.
 *
 * Moodle 5.0 moved question banks into mod_qbank instances, so a course context no
 * longer yields a default category there. Before that, questions lived directly in
 * the course context. This class is the only place that difference is expressed.
 *
 * @package    local_sparkth
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class question_bank_resolver {

    /**
     * Name of the bank this plugin authors into on Moodle 5.x.
     *
     * It is an identity key, matched on in bank_context() to find the bank again, so it must
     * never become a lang string: a site that changes language would stop finding its own bank
     * and silently fork a second one, splitting a course's questions across two banks.
     */
    private const BANK_NAME = 'Sparkth question bank';

    /**
     * Return a question category row for the course, creating what is needed.
     */
    public static function default_category_for_course(stdClass $course): stdClass {
        global $CFG, $DB;
        require_once($CFG->libdir . '/questionlib.php');

        if (!$DB->record_exists('modules', ['name' => 'qbank'])) {
            return question_make_default_categories([context_course::instance($course->id)]);
        }

        return question_get_default_category(self::bank_context($course)->id, true);
    }

    /**
     * Find this plugin's qbank instance for the course, creating it on first use.
     */
    private static function bank_context(stdClass $course): context_module {
        foreach (get_fast_modinfo($course)->get_instances_of('qbank') as $bank) {
            if ($bank->name === self::BANK_NAME) {
                return context_module::instance($bank->id);
            }
        }

        $created = question_bank_helper::create_default_open_instance($course, self::BANK_NAME);

        return context_module::instance($created->id);
    }
}

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
 * @covers \local_sparkth\external\create_quiz
 */
final class create_quiz_test extends \core_external\tests\externallib_testcase {

    /** @return array<int, array<string, mixed>> */
    private function two_questions(): array {
        return [
            [
                'qtype' => 'multichoice',
                'name' => 'Q1',
                'questiontext' => '<p>What is 2+2?</p>',
                'answers' => ['3', '4', '5'],
                'correctindex' => 1,
                'correcttrue' => false,
            ],
            [
                'qtype' => 'truefalse',
                'name' => 'Q2',
                'questiontext' => '<p>The sky is blue.</p>',
                'answers' => [],
                'correctindex' => 0,
                'correcttrue' => true,
            ],
        ];
    }

    /** Return the question_categories row holding the named question. */
    private function category_of(string $questionname): \stdClass {
        global $DB;
        return $DB->get_record_sql(
            "SELECT qc.*
               FROM {question} q
               JOIN {question_versions} qv ON qv.questionid = q.id
               JOIN {question_bank_entries} qbe ON qbe.id = qv.questionbankentryid
               JOIN {question_categories} qc ON qc.id = qbe.questioncategoryid
              WHERE q.name = :name",
            ['name' => $questionname], MUST_EXIST);
    }

    public function test_creates_a_quiz_with_both_question_types(): void {
        global $DB;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        $result = create_quiz::execute(
            $course->id, $section['sectionnum'], 'Section Quiz',
            '<p>Check understanding.</p>', $this->two_questions());
        $result = \core_external\external_api::clean_returnvalue(
            create_quiz::execute_returns(), $result);

        $this->assertSame(2, $result['questioncount']);
        $this->assertSame(2, $DB->count_records('quiz_slots',
            ['quizid' => $result['instanceid']]));
        $this->assertEquals(2.0, (float) $DB->get_field('quiz', 'sumgrades',
            ['id' => $result['instanceid']], MUST_EXIST));
    }

    public function test_multichoice_answers_and_fractions_are_saved(): void {
        global $DB;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '',
            [$this->two_questions()[0]]);

        $question = $DB->get_record('question', ['name' => 'Q1'], '*', MUST_EXIST);
        $this->assertSame('multichoice', $question->qtype);

        $answers = array_values($DB->get_records('question_answers',
            ['question' => $question->id], 'id', 'answer,fraction'));
        $this->assertSame('4', $answers[1]->answer);
        $this->assertEquals(1.0, (float) $answers[1]->fraction);
        $this->assertEquals(0.0, (float) $answers[0]->fraction);
    }

    public function test_truefalse_marks_true_as_correct(): void {
        global $DB;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '',
            [$this->two_questions()[1]]);

        $question = $DB->get_record('question', ['name' => 'Q2'], '*', MUST_EXIST);
        $this->assertSame('truefalse', $question->qtype);

        $answers = array_values($DB->get_records('question_answers',
            ['question' => $question->id], 'id', 'answer,fraction'));
        $this->assertSame('True', $answers[0]->answer);
        $this->assertEquals(1.0, (float) $answers[0]->fraction);
    }

    public function test_questions_land_in_the_bank_this_moodle_version_uses(): void {
        global $CFG, $DB;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '',
            [$this->two_questions()[1]]);

        $level = $DB->get_field('context', 'contextlevel',
            ['id' => $this->category_of('Q2')->contextid], MUST_EXIST);
        $expected = (int) $CFG->branch >= 500 ? CONTEXT_MODULE : CONTEXT_COURSE;
        $this->assertSame($expected, (int) $level);
    }

    public function test_bank_is_visible_but_off_the_course_page(): void {
        global $CFG, $DB;
        $this->resetAfterTest();

        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '',
            [$this->two_questions()[1]]);

        $cms = $DB->get_records_sql(
            "SELECT cm.id, cm.visible, cm.visibleoncoursepage
               FROM {course_modules} cm
               JOIN {modules} m ON m.id = cm.module
              WHERE cm.course = :courseid AND m.name = 'qbank'",
            ['courseid' => $course->id]);

        if ((int) $CFG->branch < 500) {
            $this->assertSame([], $cms);
            return;
        }

        $cm = reset($cms);
        $this->assertSame(1, (int) $cm->visible);
        $this->assertSame(0, (int) $cm->visibleoncoursepage);
    }

    public function test_a_second_quiz_reuses_the_same_question_category(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        create_quiz::execute($course->id, $section['sectionnum'], 'First', '',
            [$this->two_questions()[0]]);
        create_quiz::execute($course->id, $section['sectionnum'], 'Second', '',
            [$this->two_questions()[1]]);

        $this->assertSame(
            (int) $this->category_of('Q1')->id, (int) $this->category_of('Q2')->id);
    }

    public function test_rejects_an_unsupported_question_type(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        $this->expectException(\invalid_parameter_exception::class);
        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '', [[
            'qtype' => 'essay', 'name' => 'E', 'questiontext' => '<p>Discuss.</p>',
            'answers' => [], 'correctindex' => 0, 'correcttrue' => true,
        ]]);
    }

    public function test_requires_manageactivities_capability(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $user = $this->getDataGenerator()->create_and_enrol($course, 'student');
        $this->setUser($user);

        $this->expectException(\required_capability_exception::class);
        create_quiz::execute($course->id, 1, 'Q', '', $this->two_questions());
    }

    public function test_rejects_a_sectionnum_the_course_does_not_have(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();

        $this->expectException(\dml_missing_record_exception::class);
        create_quiz::execute($course->id, 47, 'Q', '', $this->two_questions());
    }

    public function test_rejects_a_multichoice_correctindex_out_of_range(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        $question = $this->two_questions()[0];
        $question['correctindex'] = 7;

        $this->expectException(\invalid_parameter_exception::class);
        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '', [$question]);
    }

    public function test_rejects_a_multichoice_without_enough_answers(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        $question = $this->two_questions()[0];
        $question['answers'] = [];

        $this->expectException(\invalid_parameter_exception::class);
        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '', [$question]);
    }

    public function test_rejects_a_multichoice_with_only_one_answer(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        // In range on its own (0 < 1), so only the count check can catch this.
        $question = $this->two_questions()[0];
        $question['answers'] = ['4'];
        $question['correctindex'] = 0;

        $this->expectException(\invalid_parameter_exception::class);
        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '', [$question]);
    }

    public function test_requires_question_add_capability(): void {
        global $DB;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        $user = $this->getDataGenerator()->create_and_enrol($course, 'editingteacher');
        $roleid = $DB->get_field('role', 'id', ['shortname' => 'editingteacher'], MUST_EXIST);
        $context = \context_course::instance($course->id);
        assign_capability('moodle/question:add', CAP_PROHIBIT, $roleid, $context->id, true);
        accesslib_clear_all_caches_for_unit_testing();
        $this->setUser($user);

        $this->expectException(\required_capability_exception::class);
        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '',
            $this->two_questions());
    }
}

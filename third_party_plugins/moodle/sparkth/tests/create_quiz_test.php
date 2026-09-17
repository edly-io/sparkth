<?php
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
        global $DB;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['numsections' => 0]);
        $this->setAdminUser();
        $section = create_section::execute($course->id, 'Module 1', '');

        create_quiz::execute($course->id, $section['sectionnum'], 'Q', '',
            [$this->two_questions()[1]]);

        $level = $DB->get_field('context', 'contextlevel',
            ['id' => $this->category_of('Q2')->contextid], MUST_EXIST);
        $expected = $DB->record_exists('modules', ['name' => 'qbank'])
            ? CONTEXT_MODULE : CONTEXT_COURSE;
        $this->assertSame($expected, (int) $level);
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
}

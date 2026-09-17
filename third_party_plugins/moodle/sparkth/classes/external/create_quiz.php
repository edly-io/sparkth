<?php
namespace local_sparkth\external;

use context_course;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;
use invalid_parameter_exception;
use local_sparkth\question_bank_resolver;
use mod_quiz\quiz_settings;
use question_bank;
use stdClass;

/**
 * Create a Quiz activity with its questions.
 *
 * @package    local_sparkth
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class create_quiz extends external_api {

    /** Question types this plugin can author. */
    private const SUPPORTED_QTYPES = ['multichoice', 'truefalse'];

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'   => new external_value(PARAM_INT, 'course id', VALUE_REQUIRED),
            'sectionnum' => new external_value(PARAM_INT, 'section number', VALUE_REQUIRED),
            'name'       => new external_value(PARAM_TEXT, 'quiz name', VALUE_REQUIRED),
            'intro'      => new external_value(PARAM_RAW, 'quiz description HTML', VALUE_DEFAULT, ''),
            'questions'  => new external_multiple_structure(
                new external_single_structure([
                    'qtype'        => new external_value(PARAM_ALPHA, 'multichoice or truefalse'),
                    'name'         => new external_value(PARAM_TEXT, 'question name'),
                    'questiontext' => new external_value(PARAM_RAW, 'question text HTML'),
                    'answers'      => new external_multiple_structure(
                        new external_value(PARAM_RAW, 'answer option text'),
                        'multichoice options; empty for truefalse',
                        VALUE_DEFAULT, []
                    ),
                    'correctindex' => new external_value(PARAM_INT,
                        'index into answers that is correct; multichoice only', VALUE_DEFAULT, 0),
                    'correcttrue'  => new external_value(PARAM_BOOL,
                        'whether True is correct; truefalse only', VALUE_DEFAULT, true),
                ]),
                'questions to create'
            ),
        ]);
    }

    /**
     * @param array<int, array<string, mixed>> $questions
     * @return array{cmid: int, instanceid: int, questioncount: int}
     */
    public static function execute(
        int $courseid,
        int $sectionnum,
        string $name,
        string $intro,
        array $questions
    ): array {
        global $CFG, $DB;
        require_once($CFG->dirroot . '/course/modlib.php');
        require_once($CFG->dirroot . '/mod/quiz/locallib.php');
        require_once($CFG->libdir . '/questionlib.php');

        [
            'courseid' => $courseid, 'sectionnum' => $sectionnum, 'name' => $name,
            'intro' => $intro, 'questions' => $questions,
        ] = self::validate_parameters(self::execute_parameters(), [
            'courseid' => $courseid, 'sectionnum' => $sectionnum, 'name' => $name,
            'intro' => $intro, 'questions' => $questions,
        ]);

        $course = $DB->get_record('course', ['id' => $courseid], '*', MUST_EXIST);
        $context = context_course::instance($course->id);
        self::validate_context($context);
        require_capability('moodle/course:manageactivities', $context);
        require_capability('moodle/question:add', $context);
        $DB->get_record('course_sections',
            ['course' => $course->id, 'section' => $sectionnum], 'id', MUST_EXIST);

        self::validate_questions($questions);

        $moduleinfo = (object) array_merge(self::quiz_defaults(), [
            'modulename'  => 'quiz',
            'module'      => $DB->get_field('modules', 'id', ['name' => 'quiz'], MUST_EXIST),
            'course'      => $course->id,
            'section'     => $sectionnum,
            'name'        => $name,
            'intro'       => $intro,
            'introformat' => FORMAT_HTML,
            'visible'     => 1,
            // edit_module_post_actions() reads cmidnumber unguarded for graded
            // activities, so quiz needs it set and page does not.
            'cmidnumber'  => '',
        ]);
        $created = add_moduleinfo($moduleinfo, $course);
        $quiz = $DB->get_record('quiz', ['id' => $created->instance], '*', MUST_EXIST);

        $category = question_bank_resolver::default_category_for_course($course);

        foreach ($questions as $question) {
            $form = self::question_form($question, "{$category->id},{$category->contextid}");
            $saved = question_bank::get_qtype($question['qtype'])
                ->save_question((object) ['qtype' => $question['qtype']], $form);
            quiz_add_quiz_question($saved->id, $quiz, 0, 1.0);
        }

        quiz_settings::create($quiz->id)->get_grade_calculator()->recompute_quiz_sumgrades();

        return [
            'cmid'          => (int) $created->coursemodule,
            'instanceid'    => (int) $created->instance,
            'questioncount' => count($questions),
        ];
    }

    /**
     * Reject any question this plugin cannot author, before anything is written.
     *
     * @param array<int, array<string, mixed>> $questions
     */
    private static function validate_questions(array $questions): void {
        foreach ($questions as $question) {
            if (!in_array($question['qtype'], self::SUPPORTED_QTYPES, true)) {
                throw new invalid_parameter_exception(
                    "Unsupported question type: {$question['qtype']}");
            }

            if ($question['qtype'] === 'multichoice') {
                $count = count($question['answers']);
                if ($count < 2 || $question['correctindex'] < 0 || $question['correctindex'] >= $count) {
                    throw new invalid_parameter_exception(
                        "multichoice question '{$question['name']}' needs 2+ answers " .
                        "and an in-range correctindex");
                }
            }
        }
    }

    /**
     * Build the qtype form object for one question.
     *
     * @param array<string, mixed> $question
     */
    private static function question_form(array $question, string $category): stdClass {
        $form = new stdClass();
        $form->category        = $category;
        $form->name            = $question['name'];
        $form->questiontext    = ['text' => $question['questiontext'], 'format' => FORMAT_HTML];
        $form->generalfeedback = ['text' => '', 'format' => FORMAT_HTML];
        $form->defaultmark     = 1.0;

        if ($question['qtype'] === 'truefalse') {
            $form->penalty       = 1.0;
            $form->correctanswer = $question['correcttrue'] ? 1 : 0;
            $form->feedbacktrue  = ['text' => '', 'format' => FORMAT_HTML];
            $form->feedbackfalse = ['text' => '', 'format' => FORMAT_HTML];
            return $form;
        }

        $form->penalty                  = 0.3333333;
        $form->single                   = 1;
        $form->shuffleanswers           = 1;
        $form->answernumbering          = 'abc';
        $form->showstandardinstruction  = 0;
        $form->shownumcorrect           = 0;
        $form->correctfeedback          = ['text' => '', 'format' => FORMAT_HTML];
        $form->partiallycorrectfeedback = ['text' => '', 'format' => FORMAT_HTML];
        $form->incorrectfeedback        = ['text' => '', 'format' => FORMAT_HTML];
        $form->answer   = [];
        $form->fraction = [];
        $form->feedback = [];

        foreach ($question['answers'] as $index => $answer) {
            $form->answer[$index]   = ['text' => $answer, 'format' => FORMAT_HTML];
            $form->fraction[$index] = ($index === (int) $question['correctindex']) ? 1.0 : 0.0;
            $form->feedback[$index] = ['text' => '', 'format' => FORMAT_HTML];
        }

        return $form;
    }

    /**
     * The quiz table has many NOT NULL columns. These mirror Moodle's own quiz
     * generator defaults. Note quizpassword is the form field for the password column.
     *
     * @return array<string, mixed>
     */
    private static function quiz_defaults(): array {
        return [
            'timeopen' => 0, 'timeclose' => 0, 'preferredbehaviour' => 'deferredfeedback',
            'attempts' => 0, 'attemptonlast' => 0, 'grademethod' => QUIZ_GRADEHIGHEST,
            'decimalpoints' => 2, 'questiondecimalpoints' => -1,
            'attemptduring' => 1, 'correctnessduring' => 1, 'maxmarksduring' => 1,
            'marksduring' => 1, 'specificfeedbackduring' => 1, 'generalfeedbackduring' => 1,
            'rightanswerduring' => 1, 'overallfeedbackduring' => 0,
            'attemptimmediately' => 1, 'correctnessimmediately' => 1,
            'maxmarksimmediately' => 1, 'marksimmediately' => 1,
            'specificfeedbackimmediately' => 1, 'generalfeedbackimmediately' => 1,
            'rightanswerimmediately' => 1, 'overallfeedbackimmediately' => 1,
            'attemptopen' => 1, 'correctnessopen' => 1, 'maxmarksopen' => 1, 'marksopen' => 1,
            'specificfeedbackopen' => 1, 'generalfeedbackopen' => 1,
            'rightansweropen' => 1, 'overallfeedbackopen' => 1,
            'attemptclosed' => 1, 'correctnessclosed' => 1, 'maxmarksclosed' => 1,
            'marksclosed' => 1, 'specificfeedbackclosed' => 1, 'generalfeedbackclosed' => 1,
            'rightanswerclosed' => 1, 'overallfeedbackclosed' => 1,
            'questionsperpage' => 1, 'shuffleanswers' => 1, 'sumgrades' => 0, 'grade' => 100,
            'timelimit' => 0, 'overduehandling' => 'autosubmit', 'graceperiod' => 86400,
            'quizpassword' => '', 'subnet' => '', 'browsersecurity' => '',
            'delay1' => 0, 'delay2' => 0, 'showuserpicture' => 0, 'showblocks' => 0,
            'navmethod' => QUIZ_NAVMETHOD_FREE,
        ];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'cmid'          => new external_value(PARAM_INT, 'course module id'),
            'instanceid'    => new external_value(PARAM_INT, 'quiz instance id'),
            'questioncount' => new external_value(PARAM_INT, 'questions added'),
        ]);
    }
}

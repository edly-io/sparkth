// MCQ plugin - validates answers and saves configuration via WASM backend
//
// Actions handled:
// - config.save: Save question, answers, and correct_answers
// - answer.submit: Check if selected answers match correct answers

import { getField, sendEvent, setField } from "pxc:sandbox/state";

// Handle incoming actions from frontend
export function onAction(name, data, context, permission) {
  const value = JSON.parse(data);
  if (name === "config.save") {
    handleConfigSave(value, permission);
  } else if (name === "answer.submit") {
    handleAnswerSubmit(value);
  }
  return "";
}

// Return state visible to the current user based on permission level.
export function getState(context, permission) {
  const state = {
    question: JSON.parse(getField("question")),
    answers: JSON.parse(getField("answers")),
  };
  if (permission === "edit") {
    state.correct_answers = JSON.parse(getField("correct_answers"));
  }
  return JSON.stringify(state);
}

// Save configuration (question, answers, correct_answers)
function handleConfigSave(config, permission) {
  if (permission !== "edit") {
    console.log("config.save rejected: permission is " + permission);
    return;
  }
  setField("question", JSON.stringify(config.question));
  setField("answers", JSON.stringify(config.answers));
  setField("correct_answers", JSON.stringify(config.correct_answers));

  // Notify frontend of field changes
  sendEvent("fields.change.question", JSON.stringify(config.question), null, "play");
  sendEvent("fields.change.answers", JSON.stringify(config.answers), null, "play");
  sendEvent("fields.change.correct_answers", JSON.stringify(config.correct_answers), null, "edit");
}

// Check submitted answers against correct answers
function handleAnswerSubmit(selected) {

  // Get correct answers from stored config
  const correctAnswers = JSON.parse(getField("correct_answers"));

  // Compare selected answers with correct answers
  const selectedSet = new Set(selected);
  const correctSet = new Set(correctAnswers);

  const isCorrect =
    selectedSet.size === correctSet.size &&
    [...selectedSet].every((x) => correctSet.has(x));

  let feedback;
  if (isCorrect) {
    feedback = "Correct! Well done.";
  } else if (selected.length === 0) {
    feedback = "Please select at least one answer.";
  } else {
    feedback = "Incorrect. Try again!";
  }

  sendEvent("answer.result", JSON.stringify({ correct: isCorrect, feedback }), null, "play");
}

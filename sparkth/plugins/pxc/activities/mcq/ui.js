// Activity script for MCQ (Multiple Choice Question)
// Supports author view (define question/answers) and student view (answer question)

export function setup(activity) {
  const element = activity.element;
  const permission = activity.permission;
  let isAuthorView = permission === "edit";

  // Parse stored config from fields
  function getConfig() {
    return {
      question: activity.state.question || "",
      answers: activity.state.answers || [],
      correct_answers: activity.state.correct_answers || [],
    };
  }

  // Render the toggle button (if edit) and current view
  function render() {
    const config = getConfig();
    const hasConfig = config.question && config.answers.length > 0;

    const toggleHtml = permission === "edit"
      ? `<button class="toggle-btn" id="toggle-view">Switch to ${isAuthorView ? "Student" : "Author"} View</button>`
      : "";

    element.innerHTML = `
      <style>
        #mcq-container { font-family: sans-serif; max-width: 600px; }
        .toggle-btn { margin-bottom: 1rem; padding: 0.5rem 1rem; cursor: pointer; }
        .answer-item { display: flex; align-items: center; gap: 0.5rem; margin: 0.5rem 0; }
        .answer-item input[type="text"] { flex: 1; padding: 0.25rem; }
        .answer-item button { padding: 0.25rem 0.5rem; }
        .add-btn { margin-top: 0.5rem; }
        .save-btn, .submit-btn { margin-top: 1rem; padding: 0.5rem 1rem; }
        .feedback { margin-top: 1rem; padding: 0.75rem; border-radius: 4px; }
        .feedback.correct { background: #d4edda; color: #155724; }
        .feedback.incorrect { background: #f8d7da; color: #721c24; }
        .student-answer { display: flex; align-items: center; gap: 0.5rem; margin: 0.5rem 0; }
        .no-config { color: #666; font-style: italic; }
      </style>
      <div id="mcq-container"></div>
    `;

    const container = element.querySelector("#mcq-container");

    if (isAuthorView) {
      renderAuthorView(container, config);
    } else {
      renderStudentView(container, config, hasConfig);
    }
  }

  // Author view: edit question, answers, and correct answers
  function renderAuthorView(container, config) {
    const answersHtml = config.answers
      .map(
        (ans, i) => `
        <div class="answer-item" data-index="${i}">
          <input type="checkbox" class="correct-checkbox" ${config.correct_answers.includes(i) ? "checked" : ""}>
          <input type="text" class="answer-text" value="${escapeHtml(ans)}">
          <button type="button" class="remove-answer">Remove</button>
        </div>
      `
      )
      .join("");

    container.innerHTML = `
      <div class="author-view">
        <div>
          <label for="question-input"><strong>Question:</strong></label><br>
          <textarea id="question-input" rows="3" style="width: 100%; margin-top: 0.25rem;">${escapeHtml(config.question)}</textarea>
        </div>
        <div style="margin-top: 1rem;">
          <strong>Answers:</strong> <em>(check the correct ones)</em>
          <div id="answers-list">${answersHtml}</div>
          <button type="button" class="add-btn" id="add-answer">+ Add Answer</button>
        </div>
        <button type="button" class="save-btn" id="save-config">Save</button>
        <div id="save-feedback"></div>
      </div>
    `;

    // Add answer button
    container.querySelector("#add-answer").addEventListener("click", () => {
      const list = container.querySelector("#answers-list");
      const index = list.querySelectorAll(".answer-item").length;
      list.insertAdjacentHTML("beforeend", `
        <div class="answer-item" data-index="${index}">
          <input type="checkbox" class="correct-checkbox">
          <input type="text" class="answer-text" value="">
          <button type="button" class="remove-answer">Remove</button>
        </div>
      `);
      attachRemoveHandler(list.lastElementChild);
    });

    // Attach remove handlers to existing items
    container.querySelectorAll(".answer-item").forEach(attachRemoveHandler);

    // Save button
    container.querySelector("#save-config").addEventListener("click", async () => {
      const question = container.querySelector("#question-input").value.trim();
      const answerItems = container.querySelectorAll(".answer-item");
      const answers = [];
      const correct_answers = [];

      answerItems.forEach((item, i) => {
        const text = item.querySelector(".answer-text").value.trim();
        if (text) {
          const newIndex = answers.length;
          answers.push(text);
          if (item.querySelector(".correct-checkbox").checked) {
            correct_answers.push(newIndex);
          }
        }
      });

      const feedbackEl = container.querySelector("#save-feedback");

      try {
        await activity.sendAction(
          "config.save",
          { question, answers, correct_answers }
        );
        feedbackEl.innerHTML = '<div class="feedback correct">Configuration saved!</div>';
      } catch (err) {
        feedbackEl.innerHTML = `<div class="feedback incorrect">Error: ${err.message}</div>`;
      }
    });

    function attachRemoveHandler(item) {
      item.querySelector(".remove-answer").addEventListener("click", () => {
        item.remove();
      });
    }
  }

  // Student view: display question and answer checkboxes
  function renderStudentView(container, config, hasConfig) {
    if (!hasConfig) {
      container.innerHTML = `
        <div class="student-view">
          <p class="no-config">No question has been configured yet.</p>
        </div>
      `;
      return;
    }

    const canSubmit = permission !== "view";
    const answersHtml = config.answers
      .map(
        (ans, i) => `
        <div class="student-answer">
          <input type="checkbox" id="answer-${i}" data-index="${i}" ${canSubmit ? "" : "disabled"}>
          <label for="answer-${i}">${escapeHtml(ans)}</label>
        </div>
      `
      )
      .join("");

    const submitHtml = canSubmit
      ? `<button type="button" class="submit-btn" id="submit-answer">Submit</button>`
      : "";

    container.innerHTML = `
      <div class="student-view">
        <p><strong>${escapeHtml(config.question)}</strong></p>
        <div id="student-answers">${answersHtml}</div>
        ${submitHtml}
        <div id="answer-feedback"></div>
      </div>
    `;

    if (!canSubmit) return;

    container.querySelector("#submit-answer").addEventListener("click", async () => {
      const checkboxes = container.querySelectorAll('input[type="checkbox"]:checked');
      const selected = Array.from(checkboxes).map((cb) => parseInt(cb.dataset.index, 10));

      const feedbackEl = container.querySelector("#answer-feedback");

      try {
        await activity.sendAction(
          "answer.submit",
          selected
        );
      } catch (err) {
        feedbackEl.innerHTML = `<div class="feedback incorrect">Error: ${err.message}</div>`;
      }
    });
  }

  // Escape HTML to prevent XSS
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Handle events from backend
  activity.onEvent = (name, value) => {
    if (name === "answer.result") {
      const feedbackEl = element.querySelector("#answer-feedback");
      if (feedbackEl) {
        feedbackEl.innerHTML = `<div class="feedback ${value.correct ? "correct" : "incorrect"}">${escapeHtml(value.feedback)}</div>`;
      }
    } else if (name === "fields.change.question") {
      activity.state.question = value;
    } else if (name === "fields.change.answers") {
      activity.state.answers = value;
    } else if (name === "fields.change.correct_answers") {
      activity.state.correct_answers = value;
    }
  };

  // Initial render
  render();
}

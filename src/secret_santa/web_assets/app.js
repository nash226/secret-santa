const STORAGE_KEY = "merry-match-state-v1";

const elements = {
  personForm: document.querySelector("#person-form"),
  personName: document.querySelector("#person-name"),
  peopleList: document.querySelector("#people-list"),
  personCount: document.querySelector("#person-count"),
  emptyState: document.querySelector("#empty-state"),
  familyPanel: document.querySelector("#family-panel"),
  familyToggle: document.querySelector("#family-toggle"),
  familyContent: document.querySelector("#family-content"),
  familyForm: document.querySelector("#family-form"),
  familyOne: document.querySelector("#family-person-one"),
  familyTwo: document.querySelector("#family-person-two"),
  familyList: document.querySelector("#family-list"),
  familyEmpty: document.querySelector("#family-empty"),
  drawButton: document.querySelector("#draw-button"),
  formError: document.querySelector("#form-error"),
  sortingOverlay: document.querySelector("#sorting-overlay"),
  sortingMessage: document.querySelector("#sorting-message"),
  sortingCards: [...document.querySelectorAll(".name-card")],
  results: document.querySelector("#results"),
  resultList: document.querySelector("#result-list"),
  editButton: document.querySelector("#edit-button"),
  nextYearButton: document.querySelector("#next-year-button"),
  workspace: document.querySelector(".workspace"),
  historyNote: document.querySelector("#history-note"),
  resetButton: document.querySelector("#reset-button"),
};

let state = loadState();
let pendingHistoryEntry = null;

function emptyState() {
  return { people: [], relationships: [], history: [] };
}

function loadState() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (
      Array.isArray(value?.people) &&
      Array.isArray(value?.relationships) &&
      Array.isArray(value?.history)
    ) {
      return value;
    }
  } catch {
    // A damaged browser entry should not prevent the app from opening.
  }
  return emptyState();
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function makeId() {
  if (globalThis.crypto?.randomUUID) {
    return crypto.randomUUID();
  }
  return `person-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function escapeText(value) {
  const span = document.createElement("span");
  span.textContent = value;
  return span.innerHTML;
}

function personById(personId) {
  return state.people.find((person) => person.id === personId);
}

function showError(message) {
  elements.formError.textContent = message;
  elements.formError.hidden = !message;
}

function render() {
  elements.personCount.textContent = state.people.length;
  elements.emptyState.hidden = state.people.length > 0;
  elements.peopleList.hidden = state.people.length === 0;
  elements.familyPanel.hidden = state.people.length < 2;
  elements.drawButton.disabled = state.people.length < 2;
  elements.resetButton.hidden =
    state.people.length === 0 && state.history.length === 0;

  elements.historyNote.hidden = state.history.length === 0;
  elements.historyNote.textContent =
    state.history.length === 1
      ? "1 previous draw remembered"
      : `${state.history.length} previous draws remembered`;

  elements.peopleList.innerHTML = state.people
    .map(
      (person) => `
        <li class="person-card">
          <span class="person-avatar" aria-hidden="true">${escapeText(
            person.name.trim().charAt(0).toUpperCase()
          )}</span>
          <span class="person-name">${escapeText(person.name)}</span>
          <button
            class="icon-button"
            type="button"
            data-remove-person="${person.id}"
            aria-label="Remove ${escapeText(person.name)}"
          >×</button>
        </li>
      `
    )
    .join("");

  const options = state.people
    .map(
      (person) =>
        `<option value="${person.id}">${escapeText(person.name)}</option>`
    )
    .join("");
  elements.familyOne.innerHTML = options;
  elements.familyTwo.innerHTML = options;
  if (state.people.length > 1) {
    elements.familyTwo.selectedIndex = 1;
  }

  elements.familyList.innerHTML = state.relationships
    .map((relationship, index) => {
      const first = personById(relationship.person_1);
      const second = personById(relationship.person_2);
      if (!first || !second) return "";
      return `
        <li class="connection-item">
          <span class="connection-bow" aria-hidden="true">✦</span>
          <span class="connection-label">${escapeText(first.name)} and ${escapeText(
            second.name
          )}</span>
          <button
            class="icon-button"
            type="button"
            data-remove-relationship="${index}"
            aria-label="Remove connection between ${escapeText(
              first.name
            )} and ${escapeText(second.name)}"
          >×</button>
        </li>
      `;
    })
    .join("");
  elements.familyEmpty.hidden = state.relationships.length > 0;
}

elements.personForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = elements.personName.value.trim();
  if (!name) return;

  if (
    state.people.some(
      (person) => person.name.toLocaleLowerCase() === name.toLocaleLowerCase()
    )
  ) {
    showError(
      "That name is already on the list. Add a last name or nickname to distinguish them."
    );
    return;
  }

  state.people.push({ id: makeId(), name });
  elements.personName.value = "";
  showError("");
  saveState();
  render();
  elements.personName.focus();
});

elements.peopleList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-person]");
  if (!button) return;

  const personId = button.dataset.removePerson;
  state.people = state.people.filter((person) => person.id !== personId);
  state.relationships = state.relationships.filter(
    (pair) => pair.person_1 !== personId && pair.person_2 !== personId
  );
  state.history = state.history.map((assignment) =>
    Object.fromEntries(
      Object.entries(assignment).filter(
        ([giver, recipient]) => giver !== personId && recipient !== personId
      )
    )
  );
  saveState();
  render();
});

elements.familyToggle.addEventListener("click", () => {
  const willOpen = elements.familyContent.hidden;
  elements.familyContent.hidden = !willOpen;
  elements.familyToggle.setAttribute("aria-expanded", String(willOpen));
  elements.familyToggle.textContent = willOpen
    ? "Hide connections"
    : "Add connections";
});

elements.familyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const firstId = elements.familyOne.value;
  const secondId = elements.familyTwo.value;

  if (firstId === secondId) {
    showError("Choose two different people for a family connection.");
    return;
  }

  const alreadyConnected = state.relationships.some(
    (pair) =>
      (pair.person_1 === firstId && pair.person_2 === secondId) ||
      (pair.person_1 === secondId && pair.person_2 === firstId)
  );
  if (alreadyConnected) {
    showError("Those two people are already connected.");
    return;
  }

  state.relationships.push({ person_1: firstId, person_2: secondId });
  showError("");
  saveState();
  render();
});

elements.familyList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-relationship]");
  if (!button) return;
  state.relationships.splice(Number(button.dataset.removeRelationship), 1);
  saveState();
  render();
});

elements.drawButton.addEventListener("click", async () => {
  showError("");
  pendingHistoryEntry = null;
  elements.sortingOverlay.hidden = false;
  document.body.style.overflow = "hidden";

  const messages = [
    "Shuffling the stockings…",
    "Checking the family tree…",
    "Tying the final bows…",
  ];
  let messageIndex = 0;
  const messageTimer = setInterval(() => {
    messageIndex = (messageIndex + 1) % messages.length;
    elements.sortingMessage.textContent = messages[messageIndex];
    elements.sortingCards.forEach((card, index) => {
      const person =
        state.people[(messageIndex + index) % state.people.length];
      card.textContent = person.name.charAt(0).toUpperCase();
    });
  }, 650);

  const minimumAnimation = new Promise((resolve) => setTimeout(resolve, 2100));

  try {
    const responsePromise = fetch("/api/draw", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        people: state.people,
        immediate_family: state.relationships,
        history: state.history,
      }),
    });
    const [response] = await Promise.all([responsePromise, minimumAnimation]);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The draw could not be completed.");
    }
    pendingHistoryEntry = data.history_entry;
    showResults(data.assignments);
  } catch (error) {
    showError(
      error instanceof Error
        ? error.message
        : "Something went wrong while making the draw."
    );
  } finally {
    clearInterval(messageTimer);
    elements.sortingOverlay.hidden = true;
    document.body.style.overflow = "";
  }
});

function showResults(assignments) {
  elements.resultList.innerHTML = assignments
    .map(
      ({ giver, recipient }) => `
        <button class="result-card" type="button" data-recipient="${escapeText(
          recipient.name
        )}" aria-expanded="false">
          <span class="result-giver">${escapeText(giver.name)}’s card</span>
          <span class="result-instruction">Tap to reveal your person</span>
        </button>
      `
    )
    .join("");
  elements.results.hidden = false;
  elements.results.scrollIntoView({ behavior: "smooth", block: "start" });
}

elements.resultList.addEventListener("click", (event) => {
  const card = event.target.closest(".result-card");
  if (!card) return;

  if (card.classList.contains("revealed")) {
    card.classList.remove("revealed");
    card.setAttribute("aria-expanded", "false");
    card.querySelector(".result-recipient").outerHTML =
      '<span class="result-instruction">Tap to reveal your person</span>';
    return;
  }

  document.querySelectorAll(".result-card.revealed").forEach((openCard) => {
    openCard.classList.remove("revealed");
    openCard.setAttribute("aria-expanded", "false");
    openCard.querySelector(".result-recipient").outerHTML =
      '<span class="result-instruction">Tap to reveal your person</span>';
  });
  card.classList.add("revealed");
  card.setAttribute("aria-expanded", "true");
  card.querySelector(".result-instruction").outerHTML = `
    <span class="result-recipient">You’re gifting ${escapeText(
      card.dataset.recipient
    )}</span>
  `;
});

elements.editButton.addEventListener("click", () => {
  pendingHistoryEntry = null;
  elements.results.hidden = true;
  elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
});

elements.nextYearButton.addEventListener("click", () => {
  if (pendingHistoryEntry) {
    state.history = [...state.history, pendingHistoryEntry].slice(-2);
    saveState();
  }
  pendingHistoryEntry = null;
  elements.results.hidden = true;
  render();
  elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
});

elements.resetButton.addEventListener("click", () => {
  if (
    !confirm(
      "Start over and remove this family list, its connections, and draw history?"
    )
  ) {
    return;
  }
  state = emptyState();
  pendingHistoryEntry = null;
  localStorage.removeItem(STORAGE_KEY);
  elements.results.hidden = true;
  elements.familyContent.hidden = true;
  elements.familyToggle.setAttribute("aria-expanded", "false");
  elements.familyToggle.textContent = "Add connections";
  showError("");
  render();
  elements.personName.focus();
});

render();

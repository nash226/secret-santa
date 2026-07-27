const STORAGE_KEY = "merry-match-state-v3";
const LEGACY_STORAGE_KEYS = [
  "merry-match-state-v2",
  "merry-match-state-v1",
];
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const elements = {
  organizerView: document.querySelector("#organizer-view"),
  organizerHeaderActions: document.querySelector("#organizer-header-actions"),
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
  copyAllButton: document.querySelector("#copy-all-button"),
  copyStatus: document.querySelector("#copy-status"),
  editButton: document.querySelector("#edit-button"),
  nextYearButton: document.querySelector("#next-year-button"),
  workspace: document.querySelector("#workspace"),
  historyControl: document.querySelector("#history-control"),
  historyNote: document.querySelector("#history-note"),
  forgetHistoryButton: document.querySelector("#forget-history-button"),
  resetButton: document.querySelector("#reset-button"),
  revealView: document.querySelector("#reveal-view"),
  revealButton: document.querySelector("#reveal-button"),
  revealCopy: document.querySelector("#reveal-copy"),
  revealResult: document.querySelector("#reveal-result"),
  revealGiver: document.querySelector("#reveal-giver"),
  revealRecipient: document.querySelector("#reveal-recipient"),
  revealError: document.querySelector("#reveal-error"),
};

let state = loadState();
let currentParticipants = [];

function emptyState() {
  return {
    people: [],
    relationships: [],
    previousExchange: null,
    activeExchange: null,
  };
}

function isExchangeReference(value) {
  return (
    value &&
    typeof value.exchange_id === "string" &&
    typeof value.organizer_token === "string"
  );
}

function loadState() {
  for (const key of [STORAGE_KEY, ...LEGACY_STORAGE_KEYS]) {
    try {
      const value = JSON.parse(localStorage.getItem(key));
      if (
        Array.isArray(value?.people) &&
        Array.isArray(value?.relationships)
      ) {
        return {
          people: value.people,
          relationships: value.relationships,
          previousExchange: isExchangeReference(value.previousExchange)
            ? value.previousExchange
            : null,
          activeExchange: isExchangeReference(value.activeExchange)
            ? value.activeExchange
            : null,
        };
      }
    } catch {
      // Damaged browser state should not prevent the application from opening.
    }
  }
  return emptyState();
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  LEGACY_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
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

function scrollTo(element) {
  element.scrollIntoView({
    behavior: reduceMotion ? "auto" : "smooth",
    block: "start",
  });
}

function clearCompletedView() {
  state.activeExchange = null;
  currentParticipants = [];
  elements.results.hidden = true;
  elements.copyStatus.textContent = "";
}

function render() {
  elements.personCount.textContent = state.people.length;
  elements.emptyState.hidden = state.people.length > 0;
  elements.peopleList.hidden = state.people.length === 0;
  elements.familyPanel.hidden = state.people.length < 2;
  elements.drawButton.disabled = state.people.length < 2;
  elements.resetButton.hidden =
    state.people.length === 0 &&
    !state.previousExchange;

  elements.historyControl.hidden = !state.previousExchange;
  elements.historyNote.textContent =
    "The last draw will prevent recent repeats.";

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
            data-remove-person="${escapeText(person.id)}"
            aria-label="Remove ${escapeText(person.name)}"
          >Remove</button>
        </li>
      `
    )
    .join("");

  const options = state.people
    .map(
      (person) =>
        `<option value="${escapeText(person.id)}">${escapeText(
          person.name
        )}</option>`
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
          <span class="connection-label">${escapeText(
            first.name
          )} and ${escapeText(second.name)}</span>
          <button
            class="icon-button"
            type="button"
            data-remove-relationship="${index}"
            aria-label="Remove connection between ${escapeText(
              first.name
            )} and ${escapeText(second.name)}"
          >Remove</button>
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

  clearCompletedView();
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

  clearCompletedView();
  const personId = button.dataset.removePerson;
  state.people = state.people.filter((person) => person.id !== personId);
  state.relationships = state.relationships.filter(
    (pair) => pair.person_1 !== personId && pair.person_2 !== personId
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

  clearCompletedView();
  state.relationships.push({ person_1: firstId, person_2: secondId });
  showError("");
  saveState();
  render();
});

elements.familyList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-relationship]");
  if (!button) return;
  clearCompletedView();
  state.relationships.splice(Number(button.dataset.removeRelationship), 1);
  saveState();
  render();
});

elements.forgetHistoryButton.addEventListener("click", () => {
  state.previousExchange = null;
  saveState();
  render();
  showError("Previous draw history was removed. The next draw starts fresh.");
});

elements.drawButton.addEventListener("click", async () => {
  showError("");
  elements.sortingOverlay.hidden = false;
  document.body.style.overflow = "hidden";

  const messages = [
    "Shuffling the stockings…",
    "Checking family connections…",
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

  const minimumAnimation = new Promise((resolve) =>
    setTimeout(resolve, reduceMotion ? 0 : 2100)
  );

  try {
    const payload = {
      people: state.people,
      immediate_family: state.relationships,
    };
    if (state.previousExchange) {
      payload.previous_exchange = state.previousExchange;
    }

    const responsePromise = fetch("/api/exchanges", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const [response] = await Promise.all([responsePromise, minimumAnimation]);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The draw could not be completed.");
    }

    state.activeExchange = {
      exchange_id: data.exchange_id,
      organizer_token: data.organizer_token,
    };
    saveState();
    showOrganizerLinks(data.participants);
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

function revealUrl(participant) {
  return new URL(participant.reveal_path, window.location.origin).href;
}

function showOrganizerLinks(participants) {
  currentParticipants = participants;
  elements.resultList.innerHTML = participants
    .map((participant) => {
      const name = escapeText(participant.person.name);
      const url = escapeText(revealUrl(participant));
      return `
        <article class="result-card">
          <div class="link-person">
            <span class="person-avatar" aria-hidden="true">${name
              .trim()
              .charAt(0)
              .toUpperCase()}</span>
            <div>
              <h3>${name}</h3>
              <a href="${url}" target="_blank" rel="noreferrer">${url}</a>
            </div>
          </div>
          <button
            class="button button-secondary copy-link-button"
            type="button"
            data-copy-url="${url}"
            data-copy-name="${name}"
          >Copy link</button>
        </article>
      `;
    })
    .join("");
  elements.results.hidden = false;
  elements.copyStatus.textContent = "";
  scrollTo(elements.results);
}

async function copyText(value) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textArea = document.createElement("textarea");
  textArea.value = value;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "fixed";
  textArea.style.opacity = "0";
  document.body.append(textArea);
  textArea.select();
  const copied = document.execCommand("copy");
  textArea.remove();
  if (!copied) {
    throw new Error("Copy is not available in this browser.");
  }
}

elements.resultList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-url]");
  if (!button) return;

  try {
    await copyText(button.dataset.copyUrl);
    elements.copyStatus.textContent = `${button.dataset.copyName}’s link copied.`;
    button.textContent = "Copied";
    setTimeout(() => {
      button.textContent = "Copy link";
    }, 1600);
  } catch (error) {
    elements.copyStatus.textContent =
      error instanceof Error ? error.message : "The link could not be copied.";
  }
});

elements.copyAllButton.addEventListener("click", async () => {
  const linkText = currentParticipants
    .map(
      (participant) =>
        `${participant.person.name}: ${revealUrl(participant)}`
    )
    .join("\n");
  try {
    await copyText(linkText);
    elements.copyStatus.textContent = "All private links copied.";
  } catch (error) {
    elements.copyStatus.textContent =
      error instanceof Error ? error.message : "The links could not be copied.";
  }
});

elements.editButton.addEventListener("click", () => {
  elements.results.hidden = true;
  scrollTo(elements.workspace);
});

elements.nextYearButton.addEventListener("click", () => {
  if (state.activeExchange) {
    state.previousExchange = state.activeExchange;
  }
  clearCompletedView();
  saveState();
  render();
  showError("This draw will be used to prevent repeat pairings next year.");
  scrollTo(elements.workspace);
});

elements.resetButton.addEventListener("click", () => {
  if (
    !confirm(
      "Start over and remove this family list, its connections, and saved history?"
    )
  ) {
    return;
  }
  state = emptyState();
  currentParticipants = [];
  localStorage.removeItem(STORAGE_KEY);
  LEGACY_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
  elements.results.hidden = true;
  elements.familyContent.hidden = true;
  elements.familyToggle.setAttribute("aria-expanded", "false");
  elements.familyToggle.textContent = "Add connections";
  showError("");
  render();
  elements.personName.focus();
});

function revealTokenFromPath() {
  const match = window.location.pathname.match(/^\/reveal\/([^/]+)$/);
  return match ? decodeURIComponent(match[1]) : null;
}

function showRevealMode() {
  elements.organizerView.hidden = true;
  elements.organizerHeaderActions.hidden = true;
  elements.revealView.hidden = false;
  document.body.classList.add("reveal-mode");
}

elements.revealButton.addEventListener("click", async () => {
  const token = revealTokenFromPath();
  if (!token) return;

  elements.revealButton.disabled = true;
  elements.revealButton.textContent = "Opening…";
  elements.revealError.hidden = true;

  try {
    const response = await fetch(`/api/reveals/${encodeURIComponent(token)}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(
        data.error ||
          "This private link could not be found. Ask the organizer for a new one."
      );
    }

    elements.revealGiver.textContent = `${data.giver.name}, this card is for you.`;
    elements.revealRecipient.textContent = data.recipient.name;
    elements.revealCopy.hidden = true;
    elements.revealButton.hidden = true;
    elements.revealResult.hidden = false;
  } catch (error) {
    elements.revealButton.disabled = false;
    elements.revealButton.textContent = "Try again";
    elements.revealError.textContent =
      error instanceof Error
        ? error.message
        : "This private link could not be opened.";
    elements.revealError.hidden = false;
  }
});

async function restoreOrganizerLinks() {
  if (!state.activeExchange) return;

  const { exchange_id: exchangeId, organizer_token: organizerToken } =
    state.activeExchange;
  const url =
    `/api/exchanges/${encodeURIComponent(exchangeId)}` +
    `?organizer_token=${encodeURIComponent(organizerToken)}`;
  try {
    const response = await fetch(url);
    const data = await response.json();
    if (!response.ok) throw new Error();
    showOrganizerLinks(data.participants);
  } catch {
    state.activeExchange = null;
    saveState();
  }
}

const revealToken = revealTokenFromPath();
if (revealToken) {
  showRevealMode();
} else {
  render();
  restoreOrganizerLinks();
}

const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor("#14091f");
  tg.setBackgroundColor("#09060f");
}

const TASKS_FORCE_MOCK = new URLSearchParams(window.location.search).get("mockTasks") === "1";

const navItems = [...document.querySelectorAll(".nav-item")];
const screens = [...document.querySelectorAll(".screen")];

const crystalsValue = document.getElementById("crystalsValue");
const crystalMultiplierValue = document.getElementById("crystalMultiplierValue");
const scoreValue = document.getElementById("scoreValue");
const runMultiplierValue = document.getElementById("runMultiplierValue");
const tasksCrystalsValue = document.getElementById("tasksCrystalsValue");
const tasksMultiplierValue = document.getElementById("tasksMultiplierValue");
const tasksReferralCountValue = document.getElementById("tasksReferralCountValue");
const tasksList = document.getElementById("tasksList");
const leaderboardTabButtons = [...document.querySelectorAll("[data-leaderboard-kind]")];
const leaderboardReferralActions = document.getElementById("leaderboardReferralActions");
const leaderboardList = document.getElementById("leaderboardList");
const leaderboardCurrent = document.getElementById("leaderboardCurrent");
const copyInviteButton = document.getElementById("copyInviteButton");
const shareInviteButton = document.getElementById("shareInviteButton");
const withdrawBalanceValue = document.getElementById("withdrawBalanceValue");
const withdrawButton = document.getElementById("withdrawButton");
const connectWalletButton = document.getElementById("connectWalletButton");
const withdrawHint = document.getElementById("withdrawHint");
const withdrawHistory = document.getElementById("withdrawHistory");
const toast = document.getElementById("toast");

const gameFrame = document.getElementById("gameFrame");
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const gameOverlay = document.getElementById("gameOverlay");
const overlayTitle = document.getElementById("overlayTitle");
const overlayText = document.getElementById("overlayText");
const overlayButton = document.getElementById("overlayButton");

const music = new Audio("./background-loop.m4a");
music.preload = "auto";
music.volume = 0.38;
music.loop = true;

const storageKeys = {
  bestScore: "jetpack-pulse-best-score",
  crystals: "jetpack-pulse-crystals",
  crystalMultiplier: "jetpack-pulse-crystal-multiplier",
  mockShareTaskCompleted: "jetpack-pulse-mock-share-task-completed",
  mockReferralCount: "jetpack-pulse-mock-referral-count",
  mockWalletConnected: "jetpack-pulse-mock-wallet-connected",
  mockWithdrawHistory: "jetpack-pulse-mock-withdraw-history"
};

const TASK_CONFIG = {
  firstReferralTarget: 3,
  secondReferralTarget: 10,
  referralTargetStep: 10
};

function shouldUseMockTasks() {
  return TASKS_FORCE_MOCK || !tg?.initData;
}

function normalizeTenths(value) {
  return Math.round(value * 10) / 10;
}

function formatTenths(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

let toastTimer = 0;

function showToast(message) {
  if (!toast) {
    return;
  }

  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("toast-visible");
  toastTimer = window.setTimeout(() => {
    toast.classList.remove("toast-visible");
  }, 3000);
}

function formatTon(value) {
  return Number(value.toFixed(3)).toString();
}

function getReferralTargets(referralCount) {
  const targets = [TASK_CONFIG.firstReferralTarget];
  let nextTarget = TASK_CONFIG.secondReferralTarget;

  while (true) {
    targets.push(nextTarget);
    if (referralCount < nextTarget) {
      break;
    }
    nextTarget += TASK_CONFIG.referralTargetStep;
  }

  return targets;
}

function getMockReferralCount() {
  const stored = Number(localStorage.getItem(storageKeys.mockReferralCount) || 4);
  return Number.isFinite(stored) && stored >= 0 ? stored : 4;
}

function buildMockTasksPayload() {
  const referralCount = getMockReferralCount();
  const shareCompleted = localStorage.getItem(storageKeys.mockShareTaskCompleted) === "1";
  let crystalMultiplier = 1;

  const items = [
    {
      id: "share_app",
      type: "share",
      title: "Рассказать друзьям",
      description: "Поделись приложением через Telegram.",
      status: shareCompleted ? "completed" : "pending",
      reward: {
        kind: "crystal_multiplier",
        label: "+0.1x к множителю кристаллов",
        value: 0.1
      },
      meta: {
        canClaimViaClient: true
      }
    }
  ];

  if (shareCompleted) {
    crystalMultiplier += 0.1;
  }

  for (const target of getReferralTargets(referralCount)) {
    const isCompleted = referralCount >= target;
    if (isCompleted) {
      crystalMultiplier += 0.3;
    }

    items.push({
      id: `invite_${target}`,
      type: "invite_users",
      title: `Пригласить ${target} пользователей`,
      description: "Это задание засчитывается автоматически по количеству приглашённых рефералов.",
      status: isCompleted ? "completed" : "pending",
      reward: {
        kind: "crystal_multiplier",
        label: "+0.3x к множителю кристаллов",
        value: 0.3
      },
      meta: {
        current: referralCount,
        target,
        canClaimViaClient: false
      }
    });
  }

  return {
    items,
    referralCount,
    crystalMultiplier: normalizeTenths(crystalMultiplier),
    balance: normalizeTenths(Number(localStorage.getItem(storageKeys.crystals) || 0)),
    inviteUrl: window.location.href
  };
}

function buildMockLeaderboardPayload(kind) {
  const isReferrals = kind === "referrals";
  const top = isReferrals
    ? [
        { position: 1, userId: "11", displayName: "rocketmax", username: "rocketmax", firstName: "Max", avatarUrl: null, value: 28, valueLabel: "28" },
        { position: 2, userId: "12", displayName: "sasha", username: "sasha", firstName: "Саша", avatarUrl: null, value: 22, valueLabel: "22" },
        { position: 3, userId: "13", displayName: "luna", username: "luna", firstName: "Luna", avatarUrl: null, value: 17, valueLabel: "17" },
        { position: 4, userId: "14", displayName: "Vika", username: "", firstName: "Vika", avatarUrl: null, value: 15, valueLabel: "15" },
        { position: 5, userId: "15", displayName: "andrey", username: "andrey", firstName: "Андрей", avatarUrl: null, value: 12, valueLabel: "12" },
        { position: 6, userId: "16", displayName: "Mila", username: "", firstName: "Mila", avatarUrl: null, value: 11, valueLabel: "11" },
        { position: 7, userId: "17", displayName: "storm", username: "storm", firstName: "Storm", avatarUrl: null, value: 10, valueLabel: "10" },
        { position: 8, userId: "18", displayName: "leo", username: "leo", firstName: "Leo", avatarUrl: null, value: 9, valueLabel: "9" },
        { position: 9, userId: "19", displayName: "Rina", username: "", firstName: "Rina", avatarUrl: null, value: 7, valueLabel: "7" },
        { position: 10, userId: "20", displayName: "niko", username: "niko", firstName: "Niko", avatarUrl: null, value: 6, valueLabel: "6" }
      ]
    : [
        { position: 1, userId: "11", displayName: "rocketmax", username: "rocketmax", firstName: "Max", avatarUrl: null, value: 1840, valueLabel: "1840 м" },
        { position: 2, userId: "12", displayName: "sasha", username: "sasha", firstName: "Саша", avatarUrl: null, value: 1680, valueLabel: "1680 м" },
        { position: 3, userId: "13", displayName: "luna", username: "luna", firstName: "Luna", avatarUrl: null, value: 1510, valueLabel: "1510 м" },
        { position: 4, userId: "14", displayName: "Vika", username: "", firstName: "Vika", avatarUrl: null, value: 1390, valueLabel: "1390 м" },
        { position: 5, userId: "15", displayName: "andrey", username: "andrey", firstName: "Андрей", avatarUrl: null, value: 1295, valueLabel: "1295 м" },
        { position: 6, userId: "16", displayName: "Mila", username: "", firstName: "Mila", avatarUrl: null, value: 1180, valueLabel: "1180 м" },
        { position: 7, userId: "17", displayName: "storm", username: "storm", firstName: "Storm", avatarUrl: null, value: 1090, valueLabel: "1090 м" },
        { position: 8, userId: "18", displayName: "leo", username: "leo", firstName: "Leo", avatarUrl: null, value: 980, valueLabel: "980 м" },
        { position: 9, userId: "19", displayName: "Rina", username: "", firstName: "Rina", avatarUrl: null, value: 840, valueLabel: "840 м" },
        { position: 10, userId: "20", displayName: "niko", username: "niko", firstName: "Niko", avatarUrl: null, value: 760, valueLabel: "760 м" }
      ];

  const currentUser = isReferrals
    ? {
        position: 14,
        userId: "self",
        displayName: "Вы",
        username: "",
        firstName: "Вы",
        avatarUrl: null,
        value: getMockReferralCount(),
        valueLabel: String(getMockReferralCount())
      }
    : {
        position: 7,
        userId: "self",
        displayName: "Вы",
        username: "",
        firstName: "Вы",
        avatarUrl: null,
        value: state.bestScore,
        valueLabel: `${state.bestScore} м`
      };

  return {
    kind,
    top,
    currentUser,
    inviteUrl: state.inviteUrl || window.location.href
  };
}

function getMockWalletInfo() {
  if (localStorage.getItem(storageKeys.mockWalletConnected) !== "1") {
    return null;
  }

  return {
    address: "UQDemoWalletAddress1234567890"
  };
}

function getDefaultMockWithdrawHistory() {
  return [
    {
      id: 201,
      amount: 24,
      walletAddress: "UQDemoWalletAddress1234567890",
      status: "pending",
      createdAt: "2026-04-08T09:12:00Z",
      completedAt: null
    },
    {
      id: 188,
      amount: 18,
      walletAddress: "UQAnotherWallet987654321",
      status: "completed",
      createdAt: "2026-04-07T14:05:00Z",
      completedAt: "2026-04-07T18:20:00Z"
    }
  ];
}

function getMockWithdrawHistory() {
  const raw = localStorage.getItem(storageKeys.mockWithdrawHistory);
  if (!raw) {
    return getDefaultMockWithdrawHistory();
  }

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : getDefaultMockWithdrawHistory();
  } catch {
    return getDefaultMockWithdrawHistory();
  }
}

function buildMockWithdrawPayload() {
  const walletInfo = getMockWalletInfo();
  const fallbackBalance = state.crystals > 0 ? state.crystals : 36;

  return {
    balance: normalizeTenths(fallbackBalance),
    walletInfo,
    minAmount: 10,
    maxAmount: 40,
    tonRatePerCrystal: 0.01,
    processingText: "Вывод до 24 часов",
    items: getMockWithdrawHistory()
  };
}

const state = {
  activeScreen: "home",
  crystals: normalizeTenths(Number(localStorage.getItem(storageKeys.crystals) || 0)),
  crystalMultiplier: normalizeTenths(Number(localStorage.getItem(storageKeys.crystalMultiplier) || 1)),
  bestScore: Number(localStorage.getItem(storageKeys.bestScore) || 0),
  tasks: [],
  referralCount: 0,
  inviteUrl: window.location.href,
  leaderboardKind: "referrals",
  leaderboards: {
    referrals: null,
    distance: null
  },
  withdraw: {
    balance: normalizeTenths(Number(localStorage.getItem(storageKeys.crystals) || 0)),
    minAmount: 10,
    maxAmount: 40,
    tonRatePerCrystal: 0.01,
    processingText: "Вывод до 24 часов",
    walletInfo: null,
    items: null
  },
  score: 0,
  scoreFloat: 0,
  scoreMultiplier: 1,
  runCrystals: 0,
  paused: false,
  running: false,
  pressing: false,
  musicActivated: false,
  time: 0,
  lastFrame: 0,
  gateTimer: 0,
  shardTimer: 0,
  firstGatePassed: false,
  player: {
    x: 94,
    y: 260,
    velocityY: 0,
    radius: 18
  },
  gates: [],
  shardsList: [],
  flash: 0,
  trails: []
};

function savePersistentState() {
  localStorage.setItem(storageKeys.bestScore, String(state.bestScore));
  localStorage.setItem(storageKeys.crystals, formatTenths(state.crystals));
  localStorage.setItem(storageKeys.crystalMultiplier, formatTenths(state.crystalMultiplier));
}

function updateHud() {
  crystalsValue.textContent = formatTenths(state.crystals);
  crystalMultiplierValue.textContent = `x${formatTenths(state.crystalMultiplier)}`;
  scoreValue.textContent = `${state.score} м`;
  runMultiplierValue.textContent = `x${state.scoreMultiplier.toFixed(1)}`;
  state.withdraw.balance = state.crystals;

  if (tasksMultiplierValue) {
    tasksMultiplierValue.textContent = `x${formatTenths(state.crystalMultiplier)}`;
  }

  if (tasksCrystalsValue) {
    tasksCrystalsValue.textContent = formatTenths(state.crystals);
  }

  if (tasksReferralCountValue) {
    tasksReferralCountValue.textContent = String(state.referralCount);
  }

  if (state.activeScreen === "withdraw") {
    renderWithdraw();
  }
}

function getTaskActionLabel(task) {
  if (task.type === "invite_users") {
    return "Пригласить";
  }

  if (task.type === "share") {
    return "Поделиться";
  }

  return "Выполнить";
}

function canRenderTaskAction(task) {
  if (task.status === "completed") {
    return false;
  }

  return task.meta?.canClaimViaClient || task.type === "invite_users";
}

function renderTasks() {
  if (!tasksList) {
    return;
  }

  tasksList.innerHTML = state.tasks.map((task) => {
    const statusClass = task.status === "completed" ? "task-status-completed" : "task-status-pending";
    const statusLabel = task.status === "completed" ? "Выполнено" : "Не выполнено";
    const actionButton = canRenderTaskAction(task)
      ? `<button class="task-action" type="button" data-task-action="${escapeHtml(task.id)}">${getTaskActionLabel(task)}</button>`
      : "";

    return `
      <article class="task-card">
        <div class="task-card-head">
          <div>
            <h3 class="task-title">${escapeHtml(task.title)}</h3>
            <p class="task-description">${escapeHtml(task.description)}</p>
          </div>
          <span class="task-status ${statusClass}">${statusLabel}</span>
        </div>
        <div class="task-reward-row">
          <div class="task-reward">${escapeHtml(task.reward.label)}</div>
          ${actionButton}
        </div>
      </article>
    `;
  }).join("");

  tasksList.querySelectorAll("[data-task-action]").forEach((button) => {
    button.addEventListener("click", () => {
      handleTaskAction(button.dataset.taskAction);
    });
  });
}

function getInitials(name) {
  return String(name || "?").trim().slice(0, 1).toUpperCase() || "?";
}

function renderLeaderboardRow(entry, isCurrentUser = false) {
  const name = entry.displayName || entry.username || entry.firstName || "Unknown";
  const avatar = entry.avatarUrl
    ? `<img class="leaderboard-avatar" src="${escapeHtml(entry.avatarUrl)}" alt="${escapeHtml(name)}">`
    : `<div class="leaderboard-avatar-fallback">${escapeHtml(getInitials(name))}</div>`;
  const subtitle = isCurrentUser ? `<p class="leaderboard-subtitle">Вы</p>` : "";

  return `
    <article class="leaderboard-row">
      <div class="leaderboard-position">${entry.position}</div>
      <div class="leaderboard-user">
        ${avatar}
        <div class="leaderboard-user-meta">
          <p class="leaderboard-name">${escapeHtml(name)}</p>
          ${subtitle}
        </div>
      </div>
      <p class="leaderboard-value">${escapeHtml(entry.valueLabel)}</p>
    </article>
  `;
}

function renderLeaderboard() {
  if (!leaderboardList || !leaderboardCurrent) {
    return;
  }

  const payload = state.leaderboards[state.leaderboardKind];

  leaderboardTabButtons.forEach((button) => {
    button.classList.toggle("leaderboard-tab-active", button.dataset.leaderboardKind === state.leaderboardKind);
  });

  if (!payload) {
    leaderboardList.innerHTML = `<article class="leaderboard-row"><div class="leaderboard-position">-</div><div class="leaderboard-user"><div class="leaderboard-user-meta"><p class="leaderboard-name">Загрузка</p><p class="leaderboard-subtitle">Подтягиваем рейтинг</p></div></div><p class="leaderboard-value">...</p></article>`;
    leaderboardCurrent.innerHTML = "";
    if (leaderboardReferralActions) {
      leaderboardReferralActions.classList.toggle("leaderboard-actions-hidden", state.leaderboardKind !== "referrals");
    }
    return;
  }

  leaderboardList.innerHTML = payload.top.map((entry) => renderLeaderboardRow(entry)).join("");
  leaderboardCurrent.innerHTML = payload.currentUser ? renderLeaderboardRow(payload.currentUser, true) : "";

  if (leaderboardReferralActions) {
    leaderboardReferralActions.classList.toggle("leaderboard-actions-hidden", state.leaderboardKind !== "referrals");
  }
}

function applyLeaderboardPayload(payload) {
  state.leaderboards[payload.kind] = payload;
  if (payload.inviteUrl) {
    state.inviteUrl = payload.inviteUrl;
  }
  renderLeaderboard();
}

function getWithdrawableAmount() {
  return normalizeTenths(Math.min(state.withdraw.balance, state.withdraw.maxAmount));
}

function formatWithdrawDate(value) {
  if (!value) {
    return "";
  }

  try {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function renderWithdrawHistoryItem(item) {
  const isCompleted = item.status === "completed";
  const statusLabel = isCompleted ? "Выполнено" : "В обработке";
  const dateLabel = isCompleted ? item.completedAt || item.createdAt : item.createdAt;
  const titleClass = isCompleted ? "withdraw-row-title-completed" : "withdraw-row-title-pending";

  return `
    <article class="withdraw-row">
      <div>
        <p class="withdraw-row-title ${titleClass}">${statusLabel}</p>
        <p class="withdraw-row-subtitle">${escapeHtml(formatWithdrawDate(dateLabel))}</p>
      </div>
      <p class="withdraw-row-value">${escapeHtml(`${formatTenths(item.amount)} кристаллов`)}</p>
    </article>
  `;
}

function renderWithdraw() {
  if (!withdrawButton || !withdrawHistory || !withdrawBalanceValue || !withdrawHint || !connectWalletButton) {
    return;
  }

  const availableAmount = getWithdrawableAmount();
  const tonAmount = availableAmount * state.withdraw.tonRatePerCrystal;
  const walletConnected = Boolean(state.withdraw.walletInfo);
  const amountTooSmall = availableAmount < state.withdraw.minAmount;

  withdrawBalanceValue.textContent = formatTenths(state.withdraw.balance);
  withdrawButton.textContent = `Вывести ${formatTenths(availableAmount)} кристаллов • ${formatTon(tonAmount)} TON`;
  withdrawButton.classList.toggle("withdraw-button-disabled", amountTooSmall);
  withdrawButton.setAttribute("aria-disabled", amountTooSmall ? "true" : "false");

  connectWalletButton.classList.toggle("withdraw-connect-hidden", walletConnected);
  withdrawHint.textContent = walletConnected
    ? state.withdraw.processingText
    : "Подключи TON кошелек";

  const items = state.withdraw.items || [];
  if (items.length === 0) {
    withdrawHistory.innerHTML = `
      <h3 class="withdraw-history-title">История</h3>
      <article class="withdraw-row">
        <div>
          <p class="withdraw-row-title">Пока пусто</p>
          <p class="withdraw-row-subtitle">Здесь появятся заявки на вывод.</p>
        </div>
        <p class="withdraw-row-value">-</p>
      </article>
    `;
    return;
  }

  withdrawHistory.innerHTML = `
    <h3 class="withdraw-history-title">История</h3>
    ${items.map(renderWithdrawHistoryItem).join("")}
  `;
}

function applyWithdrawPayload(payload) {
  state.withdraw.balance = normalizeTenths(typeof payload.balance === "number" ? payload.balance : state.crystals);
  state.withdraw.minAmount = payload.minAmount ?? state.withdraw.minAmount;
  state.withdraw.maxAmount = payload.maxAmount ?? state.withdraw.maxAmount;
  state.withdraw.tonRatePerCrystal = payload.tonRatePerCrystal ?? state.withdraw.tonRatePerCrystal;
  state.withdraw.processingText = payload.processingText || state.withdraw.processingText;
  state.withdraw.walletInfo = payload.walletInfo || state.withdraw.walletInfo;
  state.withdraw.items = payload.items || [];
  state.crystals = state.withdraw.balance;
  updateHud();
  renderWithdraw();
  savePersistentState();
}

async function loadWithdrawPayload() {
  if (shouldUseMockTasks()) {
    return buildMockWithdrawPayload();
  }

  const [authResponse, historyResponse] = await Promise.all([
    fetch("/api/auth/init", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": tg?.initData || ""
      },
      body: JSON.stringify({
        initData: tg?.initData || ""
      })
    }),
    fetch("/api/withdraw/history", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": tg?.initData || ""
      }
    })
  ]);

  const authPayload = await authResponse.json();
  const historyPayload = await historyResponse.json();

  if (!authResponse.ok || !authPayload.ok) {
    throw new Error(authPayload?.error?.message || "Не удалось загрузить вывод.");
  }
  if (!historyResponse.ok || !historyPayload.ok) {
    throw new Error(historyPayload?.error?.message || "Не удалось загрузить историю вывода.");
  }

  return {
    balance: authPayload.data.user?.balance ?? state.crystals,
    minAmount: authPayload.data.withdraw?.minAmount ?? state.withdraw.minAmount,
    maxAmount: authPayload.data.withdraw?.maxAmount ?? state.withdraw.maxAmount,
    tonRatePerCrystal: authPayload.data.withdraw?.tonRatePerCrystal ?? state.withdraw.tonRatePerCrystal,
    processingText: authPayload.data.withdraw?.processingText ?? state.withdraw.processingText,
    walletInfo: state.withdraw.walletInfo,
    items: historyPayload.data.items || []
  };
}

async function ensureWithdrawLoaded() {
  if (state.withdraw.items) {
    renderWithdraw();
    return;
  }

  renderWithdraw();

  try {
    const payload = await loadWithdrawPayload();
    applyWithdrawPayload(payload);
  } catch (error) {
    console.error(error);
    showToast(error.message || "Ошибка загрузки");
    applyWithdrawPayload(buildMockWithdrawPayload());
  }
}

async function loadLeaderboardPayload(kind) {
  if (shouldUseMockTasks()) {
    return buildMockLeaderboardPayload(kind);
  }

  const response = await fetch(`/api/leaderboard?kind=${encodeURIComponent(kind)}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg?.initData || ""
    }
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload?.error?.message || "Не удалось загрузить лидеров.");
  }
  return payload.data;
}

async function ensureLeaderboardLoaded(kind = state.leaderboardKind) {
  if (state.leaderboards[kind]) {
    renderLeaderboard();
    return;
  }

  renderLeaderboard();

  try {
    const payload = await loadLeaderboardPayload(kind);
    applyLeaderboardPayload(payload);
  } catch (error) {
    console.error(error);
    showToast(error.message || "Ошибка загрузки");
    applyLeaderboardPayload(buildMockLeaderboardPayload(kind));
  }
}

function applyTasksPayload(payload) {
  state.tasks = payload.items || [];
  state.referralCount = payload.referralCount || 0;
  state.crystalMultiplier = normalizeTenths(payload.crystalMultiplier || 1);
  state.inviteUrl = payload.inviteUrl || state.inviteUrl;
  if (typeof payload.balance === "number") {
    state.crystals = normalizeTenths(payload.balance);
  }
  updateHud();
  renderTasks();
  savePersistentState();
}

async function loadTasksPayload() {
  if (shouldUseMockTasks()) {
    return buildMockTasksPayload();
  }

  const response = await fetch("/api/tasks", {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg?.initData || ""
    }
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload?.error?.message || "Не удалось загрузить задания.");
  }
  return payload.data;
}

function openSharePrompt() {
  const shareUrl = new URL("https://t.me/share/url");
  shareUrl.searchParams.set("url", window.location.href);
  shareUrl.searchParams.set("text", "Залетай в игру и попробуй побить мой рекорд.");

  if (tg?.openTelegramLink) {
    tg.openTelegramLink(shareUrl.toString());
    return;
  }

  window.open(shareUrl.toString(), "_blank", "noopener,noreferrer");
}

function openInvitePrompt() {
  const inviteUrl = state.inviteUrl || window.location.href;
  const shareUrl = new URL("https://t.me/share/url");
  shareUrl.searchParams.set("url", inviteUrl);
  shareUrl.searchParams.set("text", "Залетай в игру по моей ссылке и попробуй побить мой рекорд.");

  if (tg?.openTelegramLink) {
    tg.openTelegramLink(shareUrl.toString());
    return;
  }

  window.open(shareUrl.toString(), "_blank", "noopener,noreferrer");
}

function saveMockWithdrawHistory(items) {
  localStorage.setItem(storageKeys.mockWithdrawHistory, JSON.stringify(items));
}

async function connectTonWallet() {
  if (shouldUseMockTasks()) {
    localStorage.setItem(storageKeys.mockWalletConnected, "1");
    state.withdraw.walletInfo = getMockWalletInfo();
    renderWithdraw();
    showToast("TON кошелек подключен");
    return;
  }

  showToast("Подключение TON кошелька добавим следующим шагом");
}

async function createWithdrawRequest() {
  const amount = getWithdrawableAmount();

  if (!state.withdraw.walletInfo) {
    showToast("Сначала подключи TON кошелек");
    return;
  }

  if (amount < state.withdraw.minAmount) {
    showToast(`От ${formatTenths(state.withdraw.minAmount)} кристаллов`);
    return;
  }

  if (shouldUseMockTasks()) {
    const items = [
      {
        id: Date.now(),
        amount,
        walletAddress: state.withdraw.walletInfo.address,
        status: "pending",
        createdAt: new Date().toISOString(),
        completedAt: null
      },
      ...(state.withdraw.items || [])
    ];

    saveMockWithdrawHistory(items);
    applyWithdrawPayload({
      ...buildMockWithdrawPayload(),
      balance: normalizeTenths(state.withdraw.balance - amount),
      walletInfo: state.withdraw.walletInfo,
      items
    });
    showToast("Заявка создана");
    return;
  }

  const response = await fetch("/api/withdraw/request", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg?.initData || ""
    },
    body: JSON.stringify({
      initData: tg?.initData || "",
      amount,
      wallet_info: state.withdraw.walletInfo
    })
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload?.error?.message || "Не удалось создать заявку на вывод.");
  }

  const nextItems = [
    {
      id: payload.data.requestId,
      amount,
      walletAddress: payload.data.walletAddress,
      status: payload.data.status,
      createdAt: new Date().toISOString(),
      completedAt: null
    },
    ...(state.withdraw.items || [])
  ];

  applyWithdrawPayload({
    balance: payload.data.balance,
    minAmount: state.withdraw.minAmount,
    maxAmount: state.withdraw.maxAmount,
    tonRatePerCrystal: state.withdraw.tonRatePerCrystal,
    processingText: payload.data.processingText || state.withdraw.processingText,
    walletInfo: state.withdraw.walletInfo,
    items: nextItems
  });
  showToast("Заявка создана");
}

async function completeTask(task) {
  if (task?.type === "share") {
    openSharePrompt();
  }

  if (shouldUseMockTasks()) {
    if (task?.id === "share_app") {
      localStorage.setItem(storageKeys.mockShareTaskCompleted, "1");
    }
    return buildMockTasksPayload();
  }

  const response = await fetch("/api/tasks/complete-task", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg?.initData || ""
    },
    body: JSON.stringify({
      initData: tg?.initData || "",
      taskId: task?.id || ""
    })
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload?.error?.message || "Не удалось завершить задание.");
  }
  return payload.data;
}

async function handleTaskAction(taskId) {
  const task = state.tasks.find((item) => item.id === taskId);
  if (!task || task.status === "completed") {
    return;
  }

  if (task.type === "invite_users") {
    openInvitePrompt();
    return;
  }

  if (!task.meta?.canClaimViaClient) {
    return;
  }

  try {
    const payload = await completeTask(task);
    applyTasksPayload(payload);
  } catch (error) {
    console.error(error);
    showToast(error.message || "Ошибка");
  }
}

function switchScreen(target) {
  if (target !== "home" && state.running) {
    pauseRun();
  }

  state.activeScreen = target;

  screens.forEach((screen) => {
    screen.classList.toggle("screen-active", screen.dataset.screen === target);
  });

  navItems.forEach((item) => {
    item.classList.toggle("nav-item-active", item.dataset.target === target);
  });

  if (target === "home") {
    ensureMusicStarted();
  } else {
    music.pause();
  }

  if (target === "leaderboard") {
    ensureLeaderboardLoaded();
  }

  if (target === "withdraw") {
    ensureWithdrawLoaded();
  }
}

navItems.forEach((item) => {
  item.addEventListener("click", () => {
    switchScreen(item.dataset.target);
  });
});

leaderboardTabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.leaderboardKind = button.dataset.leaderboardKind;
    renderLeaderboard();
    ensureLeaderboardLoaded(state.leaderboardKind);
  });
});

if (copyInviteButton) {
  copyInviteButton.addEventListener("click", async () => {
    const inviteUrl = state.inviteUrl || window.location.href;

    try {
      await navigator.clipboard.writeText(inviteUrl);
      showToast("Ссылка скопирована");
    } catch (error) {
      console.error(error);
      showToast("Не удалось скопировать ссылку");
    }
  });
}

if (shareInviteButton) {
  shareInviteButton.addEventListener("click", () => {
    openInvitePrompt();
  });
}

if (connectWalletButton) {
  connectWalletButton.addEventListener("click", () => {
    connectTonWallet().catch((error) => {
      console.error(error);
      showToast(error.message || "Ошибка");
    });
  });
}

if (withdrawButton) {
  withdrawButton.addEventListener("click", () => {
    createWithdrawRequest().catch((error) => {
      console.error(error);
      showToast(error.message || "Ошибка");
    });
  });
}

function resetRun() {
  state.score = 0;
  state.scoreFloat = 0;
  state.scoreMultiplier = 1;
  state.runCrystals = 0;
  state.time = 0;
  state.lastFrame = 0;
  state.gateTimer = 0;
  state.shardTimer = 0;
  state.firstGatePassed = false;
  state.flash = 0;
  state.player.y = canvas.height / 2;
  state.player.velocityY = 0;
  state.gates = [];
  state.shardsList = [];
  state.trails = [];
  updateHud();
}

function showOverlay(mode, payload = {}) {
  gameOverlay.classList.remove("hidden");

  if (mode === "ready") {
    overlayTitle.textContent = "Удерживай экран, чтобы лететь вверх";
    overlayText.textContent = "Пролетай через лазерные ворота и собирай кристалы.";
    overlayButton.textContent = "Старт";
  }

  if (mode === "gameover") {
    overlayTitle.textContent = `Счёт: ${payload.score} м`;
    overlayText.textContent = `Лучший результат: ${payload.bestScore} м, кристаллы за ран: ${formatTenths(payload.runCrystals)}`;
    overlayButton.textContent = "Ещё раз";
  }

  if (mode === "paused") {
    overlayTitle.textContent = "Забег остановлен";
    overlayText.textContent = `Текущий счёт: ${state.score} м • Множитель: x${state.scoreMultiplier.toFixed(1)}`;
    overlayButton.textContent = "Продолжить";
  }
}

function hideOverlay() {
  gameOverlay.classList.add("hidden");
}

function startRun() {
  ensureMusicStarted();
  switchScreen("home");
  resetRun();
  state.paused = false;
  state.running = true;
  hideOverlay();
}

function resumeRun() {
  ensureMusicStarted();
  switchScreen("home");
  state.paused = false;
  state.running = true;
  hideOverlay();
}

function pauseRun() {
  state.running = false;
  state.pressing = false;
  state.paused = true;
  showOverlay("paused");
}

function endRun() {
  state.running = false;
  state.paused = false;
  state.pressing = false;
  state.bestScore = Math.max(state.bestScore, state.score);
  savePersistentState();
  updateHud();

  showOverlay("gameover", {
    score: state.score,
    bestScore: state.bestScore,
    runCrystals: state.runCrystals
  });
}

function spawnGate() {
  const gapHeight = 154 - Math.min(state.score * 0.08, 40);
  const safeCenter = 120 + Math.random() * (canvas.height - 240);
  const width = 56;
  const speed = 3.6 + Math.min(state.score * 0.012, 3.5);

  state.gates.push({
    x: canvas.width + width,
    width,
    speed,
    gapTop: safeCenter - gapHeight / 2,
    gapBottom: safeCenter + gapHeight / 2,
    passed: false
  });
}

function spawnShard() {
  state.shardsList.push({
    x: canvas.width + 34,
    y: 74 + Math.random() * (canvas.height - 148),
    radius: 9,
    speed: 3.8 + Math.min(state.score * 0.012, 3.4),
    pulse: Math.random() * Math.PI * 2
  });
}

function update(deltaMs) {
  if (!state.running) {
    return;
  }

  const delta = deltaMs / 16.666;
  state.time += deltaMs;
  state.flash = Math.max(0, state.flash - deltaMs * 0.004);

  const baseSpeed = 0.82 + Math.min(state.score * 0.0018, 0.95);
  state.scoreFloat += baseSpeed * delta;
  state.score = Math.max(0, Math.floor(state.scoreFloat));
  state.scoreMultiplier = 1 + Math.min(state.score / 180, 4);

  const gravity = 0.42;
  const thrust = -0.68;
  state.player.velocityY += gravity * delta;

  if (state.pressing) {
    state.player.velocityY += thrust * delta;
    state.trails.push({
      x: state.player.x - 12,
      y: state.player.y + 6,
      radius: 10 + Math.random() * 8,
      alpha: 0.5
    });
  }

  state.player.velocityY = Math.max(-5.8, Math.min(6.6, state.player.velocityY));
  state.player.y += state.player.velocityY * delta * 2.2;

  state.trails.forEach((trail) => {
    trail.x -= 2.3 * delta;
    trail.radius *= 0.98;
    trail.alpha *= 0.95;
  });
  state.trails = state.trails.filter((trail) => trail.alpha > 0.05);

  state.gateTimer += deltaMs;
  state.shardTimer += deltaMs;

  if (state.gateTimer > 1460) {
    spawnGate();
    state.gateTimer = 0;
  }

  if (state.shardTimer > 1180) {
    if (state.firstGatePassed || Math.random() < 0.05) {
      spawnShard();
    }
    state.shardTimer = 0;
  }

  state.gates.forEach((gate) => {
    gate.x -= gate.speed * delta;

    if (!gate.passed && gate.x + gate.width < state.player.x) {
      gate.passed = true;
      state.firstGatePassed = true;
    }
  });

  state.shardsList.forEach((shard) => {
    shard.x -= shard.speed * delta;
    shard.pulse += 0.09 * delta;
  });

  state.gates = state.gates.filter((gate) => gate.x + gate.width > -20);
  state.shardsList = state.shardsList.filter((shard) => shard.x + shard.radius > -20);

  const playerTop = state.player.y - state.player.radius;
  const playerBottom = state.player.y + state.player.radius;
  const playerLeft = state.player.x - state.player.radius;
  const playerRight = state.player.x + state.player.radius;

  if (playerTop <= 18 || playerBottom >= canvas.height - 18) {
    endRun();
    return;
  }

  for (const gate of state.gates) {
    const overlapsX = playerRight > gate.x && playerLeft < gate.x + gate.width;
    const inBlockedArea = playerTop < gate.gapTop || playerBottom > gate.gapBottom;

    if (overlapsX && inBlockedArea) {
      endRun();
      return;
    }
  }

  let crystalsCollected = false;

  for (const shard of state.shardsList) {
    const dx = state.player.x - shard.x;
    const dy = state.player.y - shard.y;

    if (Math.hypot(dx, dy) < state.player.radius + shard.radius + 2) {
      state.runCrystals += 1;
      state.crystals += state.crystalMultiplier;
      state.crystals = normalizeTenths(state.crystals);
      state.flash = 1;
      crystalsCollected = true;
      shard.collected = true;
    }
  }

  state.shardsList = state.shardsList.filter((shard) => !shard.collected);

  if (crystalsCollected) {
    savePersistentState();
  }

  updateHud();
}

function drawBackground() {
  const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
  gradient.addColorStop(0, "#2b103f");
  gradient.addColorStop(0.5, "#140a22");
  gradient.addColorStop(1, "#07050d");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.save();
  ctx.globalAlpha = 0.28;
  for (let index = 0; index < 8; index += 1) {
    const x = ((state.time * 0.03) + index * 56) % (canvas.width + 80) - 40;
    ctx.fillStyle = index % 2 === 0 ? "rgba(191, 117, 255, 0.14)" : "rgba(255, 106, 226, 0.1)";
    ctx.fillRect(canvas.width - x, 0, 2, canvas.height);
  }
  ctx.restore();

  ctx.fillStyle = "rgba(191, 117, 255, 0.08)";
  ctx.fillRect(0, 18, canvas.width, 4);
  ctx.fillRect(0, canvas.height - 22, canvas.width, 4);
}

function drawGates() {
  state.gates.forEach((gate) => {
    const glow = ctx.createLinearGradient(gate.x, 0, gate.x + gate.width, 0);
    glow.addColorStop(0, "#ff6ed8");
    glow.addColorStop(1, "#9d52ff");

    ctx.fillStyle = "rgba(84, 41, 153, 0.36)";
    ctx.fillRect(gate.x, 0, gate.width, gate.gapTop);
    ctx.fillRect(gate.x, gate.gapBottom, gate.width, canvas.height - gate.gapBottom);

    ctx.fillStyle = glow;
    ctx.fillRect(gate.x - 2, gate.gapTop - 8, gate.width + 4, 8);
    ctx.fillRect(gate.x - 2, gate.gapBottom, gate.width + 4, 8);
  });
}

function drawTrails() {
  state.trails.forEach((trail) => {
    ctx.fillStyle = `rgba(255, 110, 216, ${trail.alpha})`;
    ctx.beginPath();
    ctx.arc(trail.x, trail.y, trail.radius, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawShards() {
  state.shardsList.forEach((shard) => {
    const pulse = Math.sin(shard.pulse) * 1.6;
    ctx.save();
    ctx.translate(shard.x, shard.y);
    ctx.rotate(shard.pulse * 0.4);
    ctx.fillStyle = "#ecd2ff";
    ctx.shadowBlur = 18;
    ctx.shadowColor = "#cc92ff";
    ctx.beginPath();
    ctx.moveTo(0, -10 - pulse);
    ctx.lineTo(9 + pulse, 0);
    ctx.lineTo(0, 10 + pulse);
    ctx.lineTo(-9 - pulse, 0);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  });
}

function drawPlayer() {
  drawTrails();

  ctx.save();
  ctx.translate(state.player.x, state.player.y);
  ctx.rotate(state.player.velocityY * 0.06);

  ctx.fillStyle = "#f2eaff";
  ctx.beginPath();
  ctx.roundRect(-18, -12, 32, 24, 10);
  ctx.fill();

  ctx.fillStyle = "#9d52ff";
  ctx.beginPath();
  ctx.arc(-6, -2, 8, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#180f26";
  ctx.fillRect(6, -6, 10, 6);

  ctx.fillStyle = "#ff6ed8";
  ctx.beginPath();
  ctx.moveTo(-18, 5);
  ctx.lineTo(-34 - Math.random() * 6, 0);
  ctx.lineTo(-18, -5);
  ctx.closePath();
  ctx.fill();

  ctx.restore();
}

function drawFlash() {
  if (state.flash <= 0) {
    return;
  }

  ctx.fillStyle = `rgba(236, 210, 255, ${state.flash * 0.18})`;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function render() {
  drawBackground();
  drawGates();
  drawShards();
  drawPlayer();
  drawFlash();
}

function loop(timestamp) {
  if (!state.lastFrame) {
    state.lastFrame = timestamp;
  }

  const deltaMs = Math.min(32, timestamp - state.lastFrame);
  state.lastFrame = timestamp;

  update(deltaMs);
  render();
  requestAnimationFrame(loop);
}

function setPressing(value) {
  state.pressing = value;
}

function ensureMusicStarted() {
  if (state.activeScreen !== "home") {
    music.pause();
    return;
  }

  if (state.musicActivated) {
    if (music.paused && document.visibilityState === "visible") {
      music.play().catch(() => {});
    }
    return;
  }

  state.musicActivated = true;
  music.play().catch(() => {});
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    music.pause();
    return;
  }

  if (state.musicActivated && state.activeScreen === "home") {
    music.play().catch(() => {});
  }
});

function bindHold(target, startEvent, endEvent) {
  target.addEventListener(startEvent, (event) => {
    event.preventDefault();
    ensureMusicStarted();

    if (state.paused) {
      resumeRun();
    } else if (!state.running) {
      startRun();
    }

    setPressing(true);
  });

  target.addEventListener(endEvent, (event) => {
    event.preventDefault();
    setPressing(false);
  });
}

bindHold(gameFrame, "pointerdown", "pointerup");
gameFrame.addEventListener("pointerleave", () => setPressing(false));
gameFrame.addEventListener("pointercancel", () => setPressing(false));

let lastTouchEndAt = 0;

document.addEventListener("touchend", (event) => {
  const now = Date.now();
  if (now - lastTouchEndAt < 320) {
    event.preventDefault();
  }
  lastTouchEndAt = now;
}, { passive: false });

document.addEventListener("dblclick", (event) => {
  event.preventDefault();
}, { passive: false });

["gesturestart", "gesturechange", "gestureend"].forEach((eventName) => {
  document.addEventListener(eventName, (event) => {
    event.preventDefault();
  }, { passive: false });
});

document.addEventListener("keydown", (event) => {
  if (event.code === "Space") {
    event.preventDefault();
    ensureMusicStarted();

    if (state.paused) {
      resumeRun();
    } else if (!state.running) {
      startRun();
    }

    setPressing(true);
  }
});

document.addEventListener("keyup", (event) => {
  if (event.code === "Space") {
    event.preventDefault();
    setPressing(false);
  }
});

overlayButton.addEventListener("click", () => {
  ensureMusicStarted();

  if (state.paused) {
    resumeRun();
    return;
  }

  startRun();
});

async function bootstrap() {
  updateHud();
  showOverlay("ready");
  render();

  try {
    const payload = await loadTasksPayload();
    applyTasksPayload(payload);
  } catch (error) {
    console.error(error);
    showToast(error.message || "Ошибка загрузки");
    applyTasksPayload(buildMockTasksPayload());
  }

  requestAnimationFrame(loop);
}

bootstrap();

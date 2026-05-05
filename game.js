let vocab = [];
let queue = [];
let selectedCategory = 'all';
let current = null;
let choiceCount = 2;
let answered = false;
let firstAttempt = true;
let totalAnswered = 0;
let totalCorrect = 0;
let missedWords = [];
let _volume = 1;

// ── Boot ──────────────────────────────────────────────
async function init() {
  let config = { vocabFile: "vocabulary_demo.json", choiceCount: 2 };
  try { config = await fetch("config.json").then(r => r.json()); } catch(e) {}
  choiceCount = config.choiceCount || 2;

  const all = await fetch(config.vocabFile).then(r => r.json());
  vocab = all.filter(v => v.active !== false);

  document.getElementById("start-btn").addEventListener("click", () => { unlockAudio(); startGame(); });
  document.getElementById("replay-btn").addEventListener("click", () => { unlockAudio(); startGame(); });
  document.getElementById("play-btn").addEventListener("click", () => { unlockAudio(); playAudio(current); });

  document.querySelectorAll('.btn-cat').forEach(btn => {
    btn.addEventListener('click', () => {
      unlockAudio();
      selectedCategory = btn.dataset.cat;
      document.querySelectorAll('.btn-cat').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    });
  });

  initFullscreenBtn();
  initVolumeControls();
}

// ── Game flow ─────────────────────────────────────────
function startGame() {
  totalAnswered = 0;
  totalCorrect = 0;
  missedWords = [];
  const pool = selectedCategory === 'all' ? vocab : vocab.filter(v => v.category === selectedCategory);
  queue = shuffle([...pool]);
  show("game-screen");
  nextQuestion();
}

function nextQuestion() {
  answered = false;
  firstAttempt = true;
  clearFeedback();

  current = queue.shift();

  const pool = selectedCategory === 'all' ? vocab : vocab.filter(v => v.category === selectedCategory);
  const distractors = shuffle(pool.filter(v => v.word !== current.word))
    .slice(0, choiceCount - 1);

  const choices = shuffle([
    { entry: current, correct: true },
    ...distractors.map(d => ({ entry: d, correct: false }))
  ]);

  const container = document.getElementById("choices");
  container.innerHTML = "";
  choices.forEach(({ entry, correct }) => {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.correct = correct ? "1" : "0";

    const img = document.createElement("img");
    img.src = pickRandom(entry.images);
    img.alt = entry.word;
    card.appendChild(img);

    const icon = document.createElement("div");
    icon.className = "listen-icon";
    icon.textContent = "🔊";
    card.appendChild(icon);

    card.addEventListener("click", () => handleCardClick(card, entry));
    container.appendChild(card);
  });

  applyCardSize(choices.length);
  updateScore();
  playAudio(current);
}

function handleCardClick(card, entry) {
  unlockAudio();

  if (card.classList.contains("listen-mode")) {
    playAudio(entry);
    return;
  }

  if (card.dataset.correct === "1") {
    if (answered) return;
    answered = true;
    totalAnswered++;
    if (firstAttempt) totalCorrect++;
    card.classList.add("correct");
    showFeedback("⭐ Great job!");
    playCorrectSound();
    spawnStars();
    updateScore();
    setTimeout(() => {
      if (queue.length === 0) showEndScreen();
      else nextQuestion();
    }, 1400);
  } else {
    if (answered) return;
    if (firstAttempt) {
      firstAttempt = false;
      missedWords.push({ word: current.word, entry: current });
    }
    card.classList.add("wrong");
    showFeedback("Try again! 🎧");
    playWrongSound();
    setTimeout(() => {
      card.classList.remove("wrong");
      card.classList.add("listen-mode");
      clearFeedback();
      playAudio(current);
    }, 800);
  }
}

// ── Audio ─────────────────────────────────────────────
let _audioUnlocked = false;

// iOS 要求第一次播音必須在用戶手勢的同步 call stack 內。
// 這裡在手勢時播一段無聲音，之後所有 new Audio().play() 都能在 setTimeout 內運作。
function unlockAudio() {
  if (_audioUnlocked) return;
  _audioUnlocked = true;
  // 解鎖 HTML5 audio（1ms 靜音 WAV）
  const sil = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA");
  sil.play().catch(() => {});
  // 解鎖 AudioContext
  const ctx = getAudioContext();
  ctx.resume();
}

function playAudio(entry) {
  const audio = new Audio(pickRandom(entry.audio));
  audio.volume = _volume;
  audio.play().catch(() => {});
}

function playSFX(name) {
  const audio = new Audio(`assets/audio/sfx/${name}.mp3`);
  audio.volume = _volume;
  audio.play().catch(() => {});
}

function playCorrectSound() { playSFX("correct"); }
function playWrongSound()   { playSFX("wrong"); }
function playCompleteSound() { playSFX("complete"); }

// ── Fullscreen ────────────────────────────────────────
function initFullscreenBtn() {
  const btn = document.getElementById("fullscreen-btn");
  const update = () => { btn.textContent = document.fullscreenElement ? "⊠" : "⛶"; };
  document.addEventListener("fullscreenchange", update);
  btn.addEventListener("click", () => {
    unlockAudio();
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      document.documentElement.requestFullscreen().catch(() =>
        showToast("請點 Safari 分享 → 加入主畫面，即可全螢幕")
      );
    }
  });
}

// ── Volume ────────────────────────────────────────────
function initVolumeControls() {
  const btn = document.getElementById("volume-btn");
  const wrap = document.getElementById("volume-slider-wrap");
  const slider = document.getElementById("volume-slider");

  btn.addEventListener("click", e => {
    e.stopPropagation();
    unlockAudio();
    wrap.classList.toggle("hidden");
  });

  slider.addEventListener("input", () => {
    const v = parseFloat(slider.value);
    _volume = v;
    if (window._masterGain) window._masterGain.gain.value = v;
    btn.textContent = v === 0 ? "🔇" : v < 0.5 ? "🔉" : "🔊";
  });

  document.addEventListener("click", e => {
    if (!document.getElementById("floating-controls").contains(e.target)) {
      wrap.classList.add("hidden");
    }
  });
}

// ── Toast ─────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById("ios-toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2500);
}

// ── Stars ─────────────────────────────────────────────
function spawnStars() {
  const emojis = ["⭐", "🌟", "✨"];
  for (let i = 0; i < 6; i++) {
    const el = document.createElement("div");
    el.className = "star";
    el.textContent = emojis[i % emojis.length];
    el.style.left = `${20 + Math.random() * 60}vw`;
    el.style.top  = `${30 + Math.random() * 40}vh`;
    document.body.appendChild(el);
    el.addEventListener("animationend", () => el.remove());
  }
}

// ── UI helpers ────────────────────────────────────────
function show(id) {
  ["start-screen", "game-screen", "end-screen"].forEach(s =>
    document.getElementById(s).classList.toggle("hidden", s !== id)
  );
}

function updateScore() {
  document.getElementById("score-text").textContent = `✓ ${totalCorrect} / ${totalAnswered}`;
}

function showFeedback(msg) {
  const el = document.getElementById("feedback");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearFeedback() {
  const el = document.getElementById("feedback");
  el.textContent = "";
  el.classList.add("hidden");
}

function applyCardSize(count) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const reserved = 260; // score-bar + play-btn + feedback + gaps
  const gap = 24;

  let size;
  if (count <= 2) {
    const byWidth  = Math.floor((vw - gap * 3) / 2);
    const byHeight = vh - reserved;
    size = Math.min(byWidth, byHeight);
  } else if (count === 3) {
    const byWidth  = Math.floor((vw - gap * 4) / 3);
    const byHeight = vh - reserved;
    size = Math.min(byWidth, byHeight);
  } else {
    const byWidth  = Math.floor((vw - gap * 3) / 2);
    const byHeight = Math.floor((vh - reserved - gap) / 2);
    size = Math.min(byWidth, byHeight);
  }
  size = Math.max(size, 120);

  document.documentElement.style.setProperty("--card-size", `${size}px`);
  const container = document.getElementById("choices");
  container.style.maxWidth = count === 4 ? `calc(${size}px * 2 + ${gap}px)` : "none";
}

function showEndScreen() {
  const pct = totalAnswered > 0 ? Math.round((totalCorrect / totalAnswered) * 100) : 100;
  const emoji = pct >= 80 ? "🏆" : pct >= 50 ? "😊" : "💪";
  document.getElementById("end-emoji").textContent = emoji;
  document.getElementById("end-score").textContent =
    `You got ${totalCorrect} out of ${totalAnswered} correct! (${pct}%)`;

  const missedSection = document.getElementById("missed-section");
  const missedList = document.getElementById("missed-list");
  missedList.innerHTML = "";

  if (missedWords.length > 0) {
    missedWords.forEach(({ word, entry }) => {
      const item = document.createElement("div");
      item.className = "missed-item";
      item.title = `Click to hear "${word}"`;
      item.innerHTML = `
        <img src="${pickRandom(entry.images)}" alt="${word}">
        <span>${word}</span>
        <span class="missed-speaker">🔊</span>
      `;
      item.addEventListener("click", () => playAudio(entry));
      missedList.appendChild(item);
    });
    missedSection.classList.remove("hidden");
  } else {
    missedSection.classList.add("hidden");
  }

  show("end-screen");
  playCompleteSound();
}

// ── Utils ─────────────────────────────────────────────
function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function pickRandom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

init();

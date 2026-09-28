/* BlackLotusVPN — фронтенд мини-приложения */
(() => {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) {
    tg.expand();
    tg.setHeaderColor("#0a0a0a");
    tg.setBackgroundColor("#0a0a0a");
    tg.ready();
  }

  // Заголовок X-Init-Data — Telegram передаёт подписанную строку,
  // бэкенд валидирует её через HMAC-SHA256.
  const authHeaders = () => {
    const h = { "Content-Type": "application/json" };
    if (tg && tg.initData) h["X-Init-Data"] = tg.initData;
    return h;
  };

  const api = {
    async get(path) {
      const r = await fetch(path, { headers: authHeaders() });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    async post(path, body) {
      const r = await fetch(path, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(body || {}),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
  };

  // ---- Переключение вкладок ----
  const tabs = document.querySelectorAll(".tab");
  const tabbtns = document.querySelectorAll(".tabbtn");
  tabbtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      tabs.forEach((t) => t.classList.toggle("active", t.id === `tab-${tab}`));
      tabbtns.forEach((b) => b.classList.toggle("active", b === btn));
      if (tab === "keys") loadKeys();
    });
  });

  // ---- Главная: подписка + список серверов ----
  async function loadMe() {
    try {
      const me = await api.get("/api/me");
      const box = document.getElementById("sub-status");
      if (me.is_subscribed && me.subscription) {
        const dt = new Date(me.subscription.expires_at);
        box.classList.add("active");
        box.innerHTML = `✅ Подписка активна<br><small>Тариф: <b>${me.subscription.plan}</b> · до ${dt.toLocaleDateString("ru-RU")}</small>`;
      } else {
        box.classList.remove("active");
        box.innerHTML = "❌ Подписка не активна.<br><small>Выбери тариф во вкладке 💜 Тарифы.</small>";
      }
    } catch (e) {
      console.error(e);
      document.getElementById("sub-status").textContent = "Ошибка загрузки статуса";
    }
  }

  async function loadPlans() {
    try {
      const { plans, servers } = await api.get("/api/plans");

      // Селектор серверов
      const sel = document.getElementById("server-select");
      sel.innerHTML = "";
      servers.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.code;
        opt.textContent = `${s.flag} ${s.name}`;
        sel.appendChild(opt);
      });

      // Карточки тарифов
      const list = document.getElementById("plans-list");
      list.innerHTML = "";
      Object.entries(plans).forEach(([code, p], idx) => {
        const card = document.createElement("div");
        card.className = "plan-card" + (idx === 1 ? " hot" : "");
        card.innerHTML = `
          <div class="plan-title">${p.title}</div>
          <div class="plan-price">${p.price.toFixed(0)} ₽ <small>/ ${p.days} дней</small></div>
          <button class="btn btn-primary" data-plan="${code}">💳 Оплатить</button>
        `;
        list.appendChild(card);
      });

      list.querySelectorAll("[data-plan]").forEach((btn) => {
        btn.addEventListener("click", () => onPay(btn.dataset.plan));
      });
    } catch (e) {
      console.error(e);
    }
  }

  async function onPay(plan) {
    // Пока это заглушка: сервер сразу активирует подписку.
    // Позже здесь будет открытие платёжной страницы.
    try {
      const r = await api.post("/api/pay", { plan });
      if (tg) tg.HapticFeedback && tg.HapticFeedback.notificationOccurred("success");
      alert(`🎃 Подписка ${r.plan} активирована до ${new Date(r.expires_at).toLocaleDateString("ru-RU")}`);
      loadMe();
    } catch (e) {
      alert("Ошибка оплаты: " + e.message);
    }
  }

  // ---- Ключи ----
  async function loadKeys() {
    try {
      const { keys } = await api.get("/api/keys");
      const list = document.getElementById("keys-list");
      if (!keys.length) {
        list.innerHTML = '<p class="muted">Ключей пока нет. Нажми «🗝 Получить ключ» на главной.</p>';
        return;
      }
      list.innerHTML = "";
      keys.forEach((k) => {
        const item = document.createElement("div");
        item.className = "key-item";
        item.innerHTML = `
          <div class="key-country">🕯 ${k.country.toUpperCase()}</div>
          <div class="key-value">${k.key_value}</div>
          <div class="key-actions">
            <button class="key-copy">📋 Копировать</button>
          </div>
        `;
        item.querySelector(".key-copy").addEventListener("click", () => {
          navigator.clipboard.writeText(k.key_value).then(() => {
            if (tg) tg.HapticFeedback && tg.HapticFeedback.notificationOccurred("success");
            alert("Ключ скопирован 🎃");
          });
        });
        list.appendChild(item);
      });
    } catch (e) {
      console.error(e);
    }
  }

  document.getElementById("btn-get-key").addEventListener("click", async () => {
    const country = document.getElementById("server-select").value || "nl";
    try {
      const k = await api.post("/api/keys", { country });
      if (tg) tg.HapticFeedback && tg.HapticFeedback.notificationOccurred("success");
      alert("🗝 Ключ выдан. Найди его во вкладке «Ключи».");
      loadKeys();
    } catch (e) {
      alert("Ошибка: " + e.message);
    }
  });

  // ---- Поддержка ----
  document.getElementById("btn-support").addEventListener("click", async () => {
    const text = document.getElementById("support-text").value.trim();
    const status = document.getElementById("support-status");
    if (!text) {
      status.textContent = "Введи текст обращения.";
      return;
    }
    try {
      await api.post("/api/support", { text });
      document.getElementById("support-text").value = "";
      status.textContent = "✅ Отправлено. Мы свяжемся с тобой.";
      if (tg) tg.HapticFeedback && tg.HapticFeedback.notificationOccurred("success");
    } catch (e) {
      status.textContent = "Ошибка отправки: " + e.message;
    }
  });

  // ---- Стартовая загрузка ----
  loadMe();
  loadPlans();
})();

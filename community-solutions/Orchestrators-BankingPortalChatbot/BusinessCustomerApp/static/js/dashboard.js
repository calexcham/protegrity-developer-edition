/* ═══════════════════════════════════════════════════════════════
   Banking Cloud Portal — Dashboard & Chat JS
   ═══════════════════════════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();
    loadPrompts();
    setupChat();
});

// ── Formatting helpers ───────────────────────────────────────────

function fmt(n) {
    return new Intl.NumberFormat("en-US", {
        style: "currency", currency: "USD",
        minimumFractionDigits: 2,
    }).format(n);
}

function badge(status) {
    const cls = {
        active: "badge-active", pending: "badge-pending",
        closed: "badge-closed", completed: "badge-completed",
        paid_off: "badge-completed",
    }[status] || "badge-pending";
    return `<span class="badge ${cls}">${status}</span>`;
}

// ── Dashboard ────────────────────────────────────────────────────

async function loadDashboard() {
    try {
        const resp = await fetch("/bank/api/summary");
        if (resp.status === 401) { window.location.href = "/bank/login"; return; }
        const data = await resp.json();

        // Summary cards
        document.getElementById("totalBalance").textContent = fmt(data.totals.balance);
        document.getElementById("numAccounts").textContent = data.totals.num_accounts;
        document.getElementById("numCards").textContent = data.totals.num_cards;
        document.getElementById("numLoans").textContent = data.totals.num_loans;

        // Accounts table
        const acctBody = document.querySelector("#accountsTable tbody");
        acctBody.innerHTML = data.accounts.map(a => `
            <tr>
                <td><strong>${a.account_id}</strong></td>
                <td>${a.type}</td>
                <td>${a.account_number}</td>
                <td><strong>${fmt(a.balance)}</strong></td>
                <td>${badge(a.status)}</td>
            </tr>
        `).join("");

        // Credit cards table
        const cardBody = document.querySelector("#cardsTable tbody");
        cardBody.innerHTML = data.credit_cards.map(c => `
            <tr>
                <td><strong>${c.card_id}</strong></td>
                <td>${c.card_type} ${c.card_tier}</td>
                <td>${c.card_number}</td>
                <td>${fmt(c.current_balance)} / ${fmt(c.credit_limit)}</td>
                <td>${fmt(c.available_credit)}</td>
                <td>${(c.reward_points || 0).toLocaleString()}</td>
                <td>${badge(c.status)}</td>
            </tr>
        `).join("");

        // Loans table
        const loanBody = document.querySelector("#loansTable tbody");
        if (data.contracts.length === 0) {
            loanBody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#9ca3af;">No active loans</td></tr>`;
        } else {
            loanBody.innerHTML = data.contracts.map(l => `
                <tr>
                    <td><strong>${l.contract_id || l.loan_id || "—"}</strong></td>
                    <td>${l.loan_type || l.type || "—"}</td>
                    <td>${fmt(l.principal || l.amount || 0)}</td>
                    <td>${(l.interest_rate || 0)}%</td>
                    <td>${fmt(l.monthly_payment || 0)}</td>
                    <td>${fmt(l.remaining_balance || 0)}</td>
                    <td>${badge(l.status || "active")}</td>
                </tr>
            `).join("");
        }

        // Transactions table
        const txBody = document.querySelector("#transactionsTable tbody");
        txBody.innerHTML = data.recent_transactions.map(t => {
            const isPositive = t.amount > 0;
            const cls = isPositive ? "amount-positive" : "amount-negative";
            const sign = isPositive ? "+" : "";
            return `
                <tr>
                    <td>${t.date}</td>
                    <td>${t.merchant || t.description || "—"}</td>
                    <td>${t.category || "—"}</td>
                    <td class="${cls}">${sign}${fmt(Math.abs(t.amount))}</td>
                    <td>${badge(t.status)}</td>
                </tr>
            `;
        }).join("");

    } catch (err) {
        console.error("Dashboard load error:", err);
    }
}

// ── Chat Panel ───────────────────────────────────────────────────

function setupChat() {
    const panel = document.getElementById("chatPanel");
    const toggle = document.getElementById("chatToggle");
    const closeBtn = document.getElementById("closeChatBtn");
    const clearBtn = document.getElementById("clearChatBtn");
    const input = document.getElementById("chatInput");
    const sendBtn = document.getElementById("sendBtn");
    const dashboard = document.getElementById("dashboardPanel");

    function openChat() {
        panel.classList.add("open");
        toggle.classList.add("hidden");
        dashboard.classList.add("chat-open");
        input.focus();
    }

    function closeChat() {
        panel.classList.remove("open");
        toggle.classList.remove("hidden");
        dashboard.classList.remove("chat-open");
    }

    toggle.addEventListener("click", openChat);
    closeBtn.addEventListener("click", closeChat);

    clearBtn.addEventListener("click", async () => {
        await fetch("/bank/api/chat/clear", { method: "POST" });
        const messages = document.getElementById("chatMessages");
        messages.innerHTML = `
            <div class="chat-welcome">
                <p>👋 Chat history cleared. Ask me anything!</p>
                <div class="quick-prompts" id="quickPrompts"></div>
            </div>
        `;
        loadPrompts();
    });

    sendBtn.addEventListener("click", () => sendMessage());
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
}

async function sendMessage() {
    const input = document.getElementById("chatInput");
    const msg = input.value.trim();
    if (!msg) return;

    input.value = "";
    addBubble(msg, "user");

    // Show typing indicator
    const typingId = addTypingIndicator();

    try {
        const resp = await fetch("/bank/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msg }),
        });

        removeBubble(typingId);

        if (resp.status === 401) {
            window.location.href = "/bank/login";
            return;
        }

        const data = await resp.json();

        if (data.error) {
            addBubble("Sorry, something went wrong: " + data.error, "error");
        } else if (data.blocked) {
            addBubble(data.response, "error");
        } else {
            const duration = data.duration_ms ? `${(data.duration_ms / 1000).toFixed(1)}s` : "";
            addBubble(data.response, "assistant", duration);
        }
    } catch (err) {
        removeBubble(typingId);
        addBubble("Connection error. Please try again.", "error");
    }
}

function addBubble(text, type, meta) {
    const container = document.getElementById("chatMessages");
    const id = "bubble-" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = `chat-bubble ${type}`;

    // Convert newlines and basic markdown
    const formatted = text
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");
    div.innerHTML = formatted;

    if (meta) {
        const metaDiv = document.createElement("div");
        metaDiv.className = "chat-meta";
        metaDiv.textContent = meta;
        div.appendChild(metaDiv);
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
}

function addTypingIndicator() {
    const container = document.getElementById("chatMessages");
    const id = "typing-" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = "chat-bubble assistant";
    div.innerHTML = `<span class="typing-dots"><span></span><span></span><span></span></span>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeBubble(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// ── Quick Prompts ────────────────────────────────────────────────

async function loadPrompts() {
    try {
        const resp = await fetch("/bank/api/prompts");
        const data = await resp.json();
        const containers = document.querySelectorAll("#quickPrompts");
        containers.forEach(container => {
            container.innerHTML = data.prompts.map(p =>
                `<button class="quick-prompt" onclick="usePrompt(this)">${p}</button>`
            ).join("");
        });
    } catch (err) {
        console.error("Failed to load prompts:", err);
    }
}

function usePrompt(el) {
    const input = document.getElementById("chatInput");
    input.value = el.textContent;
    // Open chat if not open
    const panel = document.getElementById("chatPanel");
    if (!panel.classList.contains("open")) {
        document.getElementById("chatToggle").click();
    }
    sendMessage();
}

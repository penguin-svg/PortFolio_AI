// ============================================================
// ResumeAI — Client-Side Logic
// ============================================================

(() => {
    "use strict";

    // --- DOM Elements ---
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const chatArea = document.getElementById("chat-area");
    const messagesContainer = document.getElementById("messages-container");
    const welcomeScreen = document.getElementById("welcome-screen");
    const suggestionChips = document.getElementById("suggestion-chips");
    const statusDot = document.querySelector(".status-dot");
    const statusText = document.querySelector(".status-text");

    // --- State ---
    let isStreaming = false;

    // --- Helpers ---

    /** Format current time as HH:MM */
    function getTimeString() {
        return new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    /** Escape HTML to prevent XSS in user messages */
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    /** Scroll chat to the bottom */
    function scrollToBottom() {
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    /** Auto-resize textarea */
    function autoResize() {
        chatInput.style.height = "auto";
        chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + "px";
    }

    /** Update send button disabled state */
    function updateSendButton() {
        const hasText = chatInput.value.trim().length > 0;
        sendBtn.disabled = !hasText || isStreaming;
    }

    /** Set connection status UI */
    function setStatus(status, text) {
        statusDot.style.background =
            status === "online"
                ? "var(--color-success)"
                : status === "busy"
                ? "var(--color-accent)"
                : "var(--color-error)";
        statusDot.style.boxShadow =
            status === "online"
                ? "0 0 8px rgba(34,197,94,.5)"
                : status === "busy"
                ? "0 0 8px var(--color-accent-glow)"
                : "0 0 8px rgba(239,68,68,.5)";
        statusText.textContent = text;
    }

    // --- Message Rendering ---

    /** Hide welcome screen with animation */
    function hideWelcome() {
        if (welcomeScreen && welcomeScreen.style.display !== "none") {
            welcomeScreen.classList.add("welcome-hiding");
            setTimeout(() => {
                welcomeScreen.style.display = "none";
            }, 300);
        }
    }

    /** Append a user message bubble */
    function addUserMessage(text) {
        hideWelcome();

        const msgEl = document.createElement("div");
        msgEl.className = "message user-message";
        msgEl.innerHTML = `
            <div class="message-avatar">You</div>
            <div class="message-content">
                <div class="message-bubble">${escapeHtml(text)}</div>
                <div class="message-time">${getTimeString()}</div>
            </div>
        `;
        messagesContainer.appendChild(msgEl);
        scrollToBottom();
    }

    /** Create the AI message shell with typing indicator; returns the bubble element */
    function addAIMessageShell() {
        const msgEl = document.createElement("div");
        msgEl.className = "message ai-message";
        msgEl.innerHTML = `
            <div class="message-avatar">AI</div>
            <div class="message-content">
                <div class="message-bubble">
                    <div class="typing-indicator">
                        <span class="dot"></span>
                        <span class="dot"></span>
                        <span class="dot"></span>
                    </div>
                </div>
                <div class="message-time">${getTimeString()}</div>
            </div>
        `;
        messagesContainer.appendChild(msgEl);
        scrollToBottom();

        return msgEl.querySelector(".message-bubble");
    }

    // --- Streaming Chat ---

    async function sendMessage(question) {
        if (isStreaming || !question.trim()) return;

        isStreaming = true;
        updateSendButton();
        setStatus("busy", "Thinking…");

        addUserMessage(question);

        const bubble = addAIMessageShell();
        let fullText = "";

        try {
            const response = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question }),
            });

            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            // Replace typing indicator with empty text + cursor
            bubble.innerHTML = '<span class="streaming-cursor"></span>';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                fullText += chunk;

                // Render streamed text with cursor
                bubble.innerHTML =
                    escapeHtml(fullText) +
                    '<span class="streaming-cursor"></span>';
                scrollToBottom();
            }

            // Remove cursor when done
            bubble.textContent = fullText;
        } catch (err) {
            console.error("Chat error:", err);
            bubble.classList.add("error-bubble");
            bubble.textContent =
                "⚠ Something went wrong. Please check if the server is running and try again.";
        } finally {
            isStreaming = false;
            updateSendButton();
            setStatus("online", "Online");
            scrollToBottom();
        }
    }

    // --- Event Listeners ---

    // Form submission
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const question = chatInput.value.trim();
        if (question) {
            chatInput.value = "";
            chatInput.style.height = "auto";
            updateSendButton();
            sendMessage(question);
        }
    });

    // Textarea auto-resize and send-button toggle
    chatInput.addEventListener("input", () => {
        autoResize();
        updateSendButton();
    });

    // Enter to send, Shift+Enter for newline
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event("submit"));
        }
    });

    // Suggestion chips
    suggestionChips.addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (chip && !isStreaming) {
            const question = chip.dataset.question;
            chatInput.value = question;
            updateSendButton();
            sendMessage(question);
            chatInput.value = "";
            chatInput.style.height = "auto";
            updateSendButton();
        }
    });

    // Focus input on load
    chatInput.focus();
})();

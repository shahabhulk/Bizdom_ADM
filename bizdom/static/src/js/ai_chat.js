/** @odoo-module **/

import { Component, useState, useRef, onWillStart } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

const AI_STATUS_URL = "/api/ai/status";
const AI_ANALYZE_URL = "/api/ai/analyze";

export class AiChat extends Component {
    static template = "bizdom.AiChat";
    static props = {
        getContext: { type: Function },
        title: { type: String, optional: true },
    };
    static defaultProps = {
        title: "AI Insights",
    };

    setup() {
        this.scrollRef = useRef("messagesScroll");
        this.inputRef = useRef("chatInput");

        this.state = useState({
            open: false,
            statusChecked: false,
            enabled: false,
            configured: false,
            provider: "groq",
            sending: false,
            input: "",
            messages: [],
        });

        onWillStart(async () => {
            try {
                const status = await rpc(AI_STATUS_URL, {});
                this.state.enabled = !!status.enabled;
                this.state.configured = !!status.configured;
                this.state.provider = status.provider || "groq";
            } catch (err) {
                // Silently leave AI hidden if status check fails.
                console.warn("Bizdom AI: status check failed", err);
            } finally {
                this.state.statusChecked = true;
            }
        });
    }

    get providerLabel() {
        const map = {
            groq: "Groq",
            ollama: "Ollama (local)",
            openai: "OpenAI",
            openrouter: "OpenRouter",
            custom: "Custom",
        };
        return map[this.state.provider] || this.state.provider;
    }

    toggle() {
        this.state.open = !this.state.open;
        if (this.state.open && this.state.messages.length === 0) {
            const greeting = this.state.configured
                ? "Hi! I can analyse the dashboard data you're looking at. Try one of the suggestions below, or ask me anything in plain English."
                : "AI Insights is enabled, but a provider/API key isn't configured yet. Ask an admin to set it in Settings → Bizdom AI.";
            this.state.messages.push({ role: "assistant", content: greeting });
        }
        if (this.state.open) {
            setTimeout(() => {
                if (this.inputRef && this.inputRef.el) {
                    this.inputRef.el.focus();
                }
            }, 100);
        }
    }

    quickAsk(text) {
        if (this.state.sending) return;
        this.state.input = text;
        this.send();
    }

    async send() {
        const question = (this.state.input || "").trim();
        if (!question || this.state.sending) return;
        if (!this.state.configured) return;

        this.state.input = "";
        this.state.messages.push({ role: "user", content: question });
        this.state.sending = true;
        this._scrollSoon();

        try {
            const ctx = (this.props.getContext && this.props.getContext()) || {};
            // Pass prior turns (excluding the just-pushed user message) for short context.
            const priorMessages = this.state.messages
                .slice(0, -1)
                .filter((m) => m.role === "user" || m.role === "assistant")
                .filter((m) => !m.error)
                .slice(-8);

            const params = {
                question: question,
                scope: ctx.scope || "dashboard",
                filterType: ctx.filterType || "MTD",
                startDate: ctx.startDate || null,
                endDate: ctx.endDate || null,
                scoreId: ctx.scoreId || null,
                history: priorMessages.map((m) => ({
                    role: m.role,
                    content: m.content,
                })),
            };

            const result = await rpc(AI_ANALYZE_URL, params);

            if (result && result.statusCode === 200 && result.answer) {
                this.state.messages.push({
                    role: "assistant",
                    content: result.answer,
                });
            } else {
                const msg = (result && result.message) || "Could not get a response from the AI.";
                this.state.messages.push({
                    role: "assistant",
                    content: "⚠ " + msg,
                    error: true,
                });
            }
        } catch (err) {
            console.error("Bizdom AI: analyze failed", err);
            this.state.messages.push({
                role: "assistant",
                content: "⚠ Network error: " + (err && err.message ? err.message : err),
                error: true,
            });
        } finally {
            this.state.sending = false;
            this._scrollSoon();
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }

    clearChat() {
        this.state.messages = [
            {
                role: "assistant",
                content: "Conversation cleared. What would you like to know?",
            },
        ];
    }

    _scrollSoon() {
        setTimeout(() => {
            const el = this.scrollRef && this.scrollRef.el;
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        }, 50);
    }
}

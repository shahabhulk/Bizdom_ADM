/** @odoo-module **/

import { Component, EventBus, useState, onWillStart, onWillUpdateProps, onWillDestroy, onMounted, onPatched, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { useService } from "@web/core/utils/hooks";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { ListRenderer } from "@web/views/list/list_renderer";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";

export const timerBus = new EventBus();

// Patch Dialog dismiss to trigger cancel (resume work) if closing the Pause Job dialog via X, Escape or backdrop
patch(Dialog.prototype, {
    async dismiss() {
        const el = (this.modalRef && this.modalRef.el) || (this.el) || document.querySelector(".o_dialog:not(.o_inactive_modal)");
        if (el) {
            const confirmBtn = el.querySelector("button[name='action_confirm_pause']");
            const cancelBtn = el.querySelector("button[name='action_cancel']");
            if (confirmBtn && cancelBtn) {
                cancelBtn.click();
                return;
            }
        }
        return super.dismiss();
    },
});

if (typeof window !== "undefined") {
    document.addEventListener("click", (ev) => {
        const btn = ev.target && ev.target.closest && ev.target.closest("button[name='action_open_pause_wizard']");
        if (btn) {
            timerBus.trigger("PAUSE_ALL_TIMERS");
        }

        const closeBtn = ev.target && ev.target.closest && ev.target.closest(".btn-close, [data-bs-dismiss='modal']");
        if (closeBtn) {
            const modal = closeBtn.closest(".modal-content, .o_dialog") || document.querySelector(".o_dialog:not(.o_inactive_modal)");
            if (modal) {
                const cancelBtn = modal.querySelector("button[name='action_cancel']");
                const confirmBtn = modal.querySelector("button[name='action_confirm_pause']");
                if (cancelBtn && confirmBtn && cancelBtn !== closeBtn) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    cancelBtn.click();
                }
            }
        }
    }, true);
}

const { DateTime } = luxon;

function parseToLuxon(val) {
    if (!val) return false;
    if (val && val.isLuxonDateTime) {
        return val;
    }
    if (typeof val === "string") {
        try {
            const dt = deserializeDateTime(val);
            if (dt && dt.isValid) return dt;
        } catch (e) {}
        try {
            const dt = DateTime.fromSQL(val);
            if (dt && dt.isValid) return dt;
        } catch (e) {}
        try {
            const dt = DateTime.fromISO(val);
            if (dt && dt.isValid) return dt;
        } catch (e) {}
        return false;
    }
    if (val instanceof Date) {
        return DateTime.fromJSDate(val);
    }
    return false;
}

function formatSecondsToStopwatch(totalSeconds) {
    if (isNaN(totalSeconds) || totalSeconds < 0) totalSeconds = 0;
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = Math.floor(totalSeconds % 60);

    const pad = (num) => String(num).padStart(2, "0");
    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

/**
 * TimeOnlyWidget - Renders Datetime fields (timer_start / timer_end) as time only (HH:mm:ss) omitting date.
 */
export class TimeOnlyWidget extends Component {
    static template = xml`<span class="o_field_time_only" t-out="formattedTime"/>`;
    static props = {
        ...standardFieldProps,
    };

    get formattedTime() {
        const rawVal = this.props.record.data[this.props.name];
        if (!rawVal) {
            return "";
        }
        const dt = parseToLuxon(rawVal);
        if (!dt || !dt.isValid) {
            return "";
        }
        return dt.toFormat("HH:mm:ss");
    }
}

export const timeOnlyWidget = {
    component: TimeOnlyWidget,
};

registry.category("fields").add("time_only", timeOnlyWidget);

/**
 * FloatTimeHMSWidget - Renders float hour values (e.g. duration) as HH:mm:ss (hrs:min:sec)
 * Ticks live in sync with the running timer, matching the stopwatch duration exactly.
 */
export class FloatTimeHMSWidget extends Component {
    static template = xml`<span class="o_field_float_time_hms font-monospace" t-out="formattedTime"/>`;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            now: DateTime.now(),
        });
        this.interval = null;

        onWillStart(() => this.updateTicking());
        onWillUpdateProps(() => this.updateTicking());
        onWillDestroy(() => this.stopTicking());
    }

    updateTicking() {
        const isRunning = Boolean(this.props.record.data.is_timer_running);
        if (isRunning) {
            if (!this.interval) {
                this.state.now = DateTime.now();
                this.interval = setInterval(() => {
                    this.state.now = DateTime.now();
                }, 1000);
            }
        } else {
            this.stopTicking();
        }
    }

    stopTicking() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    get formattedTime() {
        const data = this.props.record.data;
        let totalSeconds = 0;

        if ("accumulated_seconds" in data || "is_timer_running" in data) {
            totalSeconds = Number(data.accumulated_seconds) || 0;
            if (data.is_timer_running && data.timer_last_start) {
                const startDt = parseToLuxon(data.timer_last_start);
                if (startDt && startDt.isValid) {
                    const now = this.state.now || DateTime.now();
                    totalSeconds += Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
                }
            } else if (!totalSeconds && data.start_datetime && !data.service_line_id) {
                const startDt = parseToLuxon(data.start_datetime);
                const endDt = data.end_datetime ? parseToLuxon(data.end_datetime) : (this.state.now || DateTime.now());
                if (startDt && startDt.isValid && endDt && endDt.isValid) {
                    totalSeconds = Math.max(0, Math.floor(endDt.diff(startDt, "seconds").seconds));
                }
            }
        } else {
            const val = data[this.props.name];
            if (val !== undefined && val !== null && !isNaN(val)) {
                totalSeconds = Math.max(0, Math.round(Number(val) * 3600));
            }
        }

        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }
}

export const floatTimeHMSWidget = {
    component: FloatTimeHMSWidget,
    supportedTypes: ["float"],
    fieldDependencies: [
        { name: "is_timer_running", type: "boolean" },
        { name: "timer_last_start", type: "datetime" },
        { name: "accumulated_seconds", type: "float" },
        { name: "start_datetime", type: "datetime" },
        { name: "end_datetime", type: "datetime" },
        { name: "service_line_id" },
    ],
};

registry.category("fields").add("float_time_hms", floatTimeHMSWidget);

/**
 * StopwatchTimerWidget - Renders Duration (time_diff) and ticks live every 1s like a stopwatch when timer is running.
 */
export class StopwatchTimerWidget extends Component {
    static template = xml`
        <span class="d-inline-flex align-items-center gap-2 o_stopwatch_wrapper me-4" t-on-click.stop="">
            <t t-if="isCollectiveRunning">
                <span class="badge text-bg-light border text-primary small py-1 px-2 d-inline-flex align-items-center" title="Running in Collective Timer (see top timer)">
                    <i class="fa fa-users me-1"/>In Collective Timer
                </span>
            </t>
            <t t-else="">
                <t t-if="hasButtons">
                    <button t-if="!state.isRunning" type="button" 
                            class="btn btn-link p-0 text-primary o_timer_btn" 
                            title="Start Timer" 
                            t-on-click="onStart"
                            t-on-pointerdown.stop=""
                            t-on-mousedown.stop="">
                        <i class="fa fa-play fa-fw"/>
                    </button>
                    <button t-else="" type="button" 
                            class="btn btn-link p-0 text-primary o_timer_btn" 
                            title="Pause Timer" 
                            t-on-click="onPause"
                            t-on-pointerdown.stop=""
                            t-on-mousedown.stop="">
                        <i class="fa fa-pause fa-fw"/>
                    </button>
                </t>
                <span class="o_field_stopwatch_timer fw-bold" t-att-class="timerColorClass" t-out="displayValue"/>
            </t>
        </span>
    `;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        const data = this.props.record.data;
        this.state = useState({
            now: DateTime.now(),
            isRunning: Boolean(data.is_timer_running),
            accumulatedSeconds: Number(data.accumulated_seconds) || 0,
            timerStart: data.timer_last_start || data.timer_start || false,
        });
        this.interval = null;
        this.isProcessing = false;
        this.pendingAction = null;

        this.onTimerReset = (ev) => {
            const detail = ev.detail || ev;
            const isMatch =
                (detail.recordId && this.props.record.id === detail.recordId) ||
                (detail.resId && this.props.record.resId === detail.resId) ||
                (detail.record && this.props.record === detail.record);
            if (isMatch) {
                this.clearInterval();
                this.state.isRunning = false;
                this.state.accumulatedSeconds = 0;
                this.state.timerStart = false;
                this.state.now = DateTime.now();
                this.props.record.data.timer_start = false;
                this.props.record.data.timer_last_start = false;
                this.props.record.data.timer_end = false;
                this.props.record.data.is_timer_running = false;
                this.props.record.data.is_timer_paused = false;
                this.props.record.data.accumulated_seconds = 0.0;
                this.props.record.data[this.props.name] = 0.0;
                this.props.record.data.fru_status = "green";
            }
        };
        this.onPauseAll = () => {
            this.clearInterval();
            this.state.isRunning = false;
            if (this.props.record && this.props.record.data) {
                this.props.record.data.is_timer_running = false;
                this.props.record.data.is_timer_paused = true;
            }
        };
        timerBus.addEventListener("RESET_TIMER", this.onTimerReset);
        timerBus.addEventListener("PAUSE_ALL_TIMERS", this.onPauseAll);

        onWillStart(() => this.updateTimerState());
        onWillUpdateProps((nextProps) => this.syncFromProps(nextProps));
        onWillDestroy(() => {
            this.clearInterval();
            timerBus.removeEventListener("RESET_TIMER", this.onTimerReset);
            timerBus.removeEventListener("PAUSE_ALL_TIMERS", this.onPauseAll);
        });
    }

    clearInterval() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    get isRunning() {
        return this.state.isRunning;
    }

    get isCollectiveRunning() {
        return Boolean(this.props.record.data?.is_collective && this.props.record.data?.is_timer_running);
    }

    get hasButtons() {
        return !(this.props.options && this.props.options.no_buttons);
    }

    syncFromProps(nextProps) {
        if (!this.isProcessing && nextProps.record && nextProps.record.data) {
            const data = nextProps.record.data;
            this.state.isRunning = Boolean(data.is_timer_running);
            this.state.accumulatedSeconds = Number(data.accumulated_seconds) || 0;
            this.state.timerStart = data.timer_last_start || data.timer_start || false;
        }
        this.updateTimerState();
    }

    updateTimerState() {
        if (this.state.isRunning) {
            if (!this.interval) {
                this.state.now = DateTime.now();
                this.interval = setInterval(() => {
                    this.state.now = DateTime.now();
                }, 1000);
            }
        } else {
            this.clearInterval();
        }
    }

    async onStart(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        // 1. Instant 0ms reactive UI update
        const nowDt = DateTime.now();
        this.state.isRunning = true;
        this.state.timerStart = nowDt;
        this.state.now = nowDt;
        this.updateTimerState();

        // Sync local record.data for other columns and formatters
        this.props.record.data.is_timer_running = true;
        this.props.record.data.is_timer_paused = false;
        if (!this.props.record.data.timer_start) {
            this.props.record.data.timer_start = nowDt;
        }
        this.props.record.data.timer_last_start = nowDt;

        // 2. Dispatch to server in background
        await this.executeTimerAction("action_start_timer");
    }

    async onPause(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        // 1. Instant 0ms reactive UI update
        const totalSec = this.currentTotalSeconds;
        const nowDt = DateTime.now();
        this.state.isRunning = false;
        this.state.accumulatedSeconds = totalSec;
        this.state.timerStart = false;
        this.state.now = nowDt;
        this.updateTimerState();

        // Sync local record.data for other columns and formatters
        this.props.record.data.is_timer_running = false;
        this.props.record.data.is_timer_paused = true;
        this.props.record.data.accumulated_seconds = totalSec;
        this.props.record.data.timer_end = nowDt;

        // 2. Dispatch to server in background
        await this.executeTimerAction("action_pause_timer");
    }

    async onReset(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        // 1. Instant 0ms reactive UI update to 00:00:00
        this.clearInterval();
        this.state.isRunning = false;
        this.state.accumulatedSeconds = 0;
        this.state.timerStart = false;
        this.state.now = DateTime.now();

        // Sync local record data
        this.props.record.data.is_timer_running = false;
        this.props.record.data.is_timer_paused = false;
        this.props.record.data.timer_start = false;
        this.props.record.data.timer_last_start = false;
        this.props.record.data.timer_end = false;
        this.props.record.data.accumulated_seconds = 0.0;
        this.props.record.data[this.props.name] = 0.0;
        this.props.record.data.fru_status = "green";
        if (this.props.record._values) {
            Object.assign(this.props.record._values, {
                is_timer_running: false,
                is_timer_paused: false,
                timer_start: false,
                timer_last_start: false,
                timer_end: false,
                accumulated_seconds: 0.0,
                [this.props.name]: 0.0,
                fru_status: "green",
            });
        }

        // Trigger on timerBus for any sibling components (e.g. Reset column)
        timerBus.trigger("RESET_TIMER", {
            resId: this.props.record.resId,
            recordId: this.props.record.id,
            record: this.props.record,
        });

        // 2. Dispatch to server in background
        await this.executeTimerAction("action_reset_timer");
    }

    async executeTimerAction(actionName) {
        if (this.isProcessing) {
            this.pendingAction = actionName;
            return;
        }
        this.isProcessing = true;
        try {
            const root = this.props.record.model?.root;
            if (root && (this.props.record.isNew || !this.props.record.resId)) {
                const saved = await root.save();
                if (saved === false) {
                    return;
                }
            }
            if (this.props.record.resId) {
                const isStarting = actionName === "action_start_timer";
                const isReset = actionName === "action_reset_timer";
                const result = await this.orm.call(
                    this.props.record.resModel,
                    actionName,
                    [[this.props.record.resId]],
                    { context: this.props.record.context }
                );

                if (result && typeof result === "object") {
                    if ("timer_start" in result) {
                        result.timer_start = parseToLuxon(result.timer_start);
                    }
                    if ("timer_last_start" in result) {
                        result.timer_last_start = parseToLuxon(result.timer_last_start);
                    }
                    if ("timer_end" in result) {
                        result.timer_end = parseToLuxon(result.timer_end);
                    }
                    Object.assign(this.props.record.data, result);
                    if (this.props.record._values) {
                        Object.assign(this.props.record._values, result);
                    }
                    if (isReset) {
                        this.state.isRunning = false;
                        this.state.accumulatedSeconds = 0;
                        this.state.timerStart = false;
                    } else if (!this.state.isRunning && "accumulated_seconds" in result) {
                        this.state.accumulatedSeconds = Number(result.accumulated_seconds) || 0;
                    }
                }

                if (isStarting && root && root.data && root.data.state && root.data.state !== "workorder" && root.data.state !== "done" && root.data.state !== "cancel") {
                    root.data.state = "workorder";
                    if (root._values) {
                        root._values.state = "workorder";
                    }
                }
            }
        } catch (error) {
            console.error("Error executing timer action:", error);
        } finally {
            this.isProcessing = false;
            if (this.pendingAction) {
                const nextAction = this.pendingAction;
                this.pendingAction = null;
                await this.executeTimerAction(nextAction);
            }
        }
    }

    get currentTotalSeconds() {
        const isRunning = this.state.isRunning;
        let totalSeconds = Number(this.state.accumulatedSeconds) || 0;

        if (isRunning && this.state.timerStart) {
            const startDt = parseToLuxon(this.state.timerStart);
            if (startDt && startDt.isValid) {
                const now = this.state.now || DateTime.now();
                let runSeconds = Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
                const isCollective = Boolean(this.props.record.data.is_collective);
                const memberCount = Number(this.props.record.data.collective_member_count) || 1;
                if (isCollective && memberCount > 1) {
                    runSeconds = Math.floor(runSeconds / memberCount);
                }
                totalSeconds += runSeconds;
            }
        }

        if (totalSeconds > 0) {
            return totalSeconds;
        }

        // If stopped and accumulated seconds is 0, do not fall back to old floatDiff if reset
        if (!isRunning && Number(this.state.accumulatedSeconds) === 0 && !this.state.timerStart) {
            const recAccum = Number(this.props.record.data.accumulated_seconds) || 0;
            if (recAccum === 0) {
                return 0;
            }
        }

        const floatDiff = this.props.record.data[this.props.name];
        if (typeof floatDiff === "number" && floatDiff > 0) {
            return Math.round(floatDiff * 3600);
        }

        return 0;
    }

    get timerColorClass() {
        const fru = ("alloted_fru" in this.props.record.data && this.props.record.data.alloted_fru)
            ? Number(this.props.record.data.alloted_fru)
            : 0;
        const totalSeconds = this.currentTotalSeconds;

        if (fru > 0) {
            const fruSeconds = fru * 300; // 1 FRU = 5 minutes = 300 seconds
            if (totalSeconds < fruSeconds) {
                return "text-success"; // Green [0, FRU)
            } else if (totalSeconds < 2 * fruSeconds) {
                return "text-warning"; // Yellow [FRU, 2FRU)
            } else {
                return "text-danger"; // Red [2FRU, ..)
            }
        }

        // When FRU is not mentioned or in Zero:
        // [0, y/2400) -> green, [y/2400, y/1200) -> yellow, [y/1200, infinity) -> red
        // where y is the price and 2400 is 2400 rs/hr (3600 sec/hr)
        // yellow threshold: (y / 2400) * 3600 = y * 1.5 seconds
        // red threshold: (y / 1200) * 3600 = y * 3.0 seconds
        const unitPrice = ("unit_price" in this.props.record.data && this.props.record.data.unit_price)
            ? Number(this.props.record.data.unit_price)
            : 0;

        if (unitPrice > 0) {
            const yellowThresholdSec = (unitPrice / 2400.0) * 3600.0;
            const redThresholdSec = (unitPrice / 1200.0) * 3600.0;

            if (totalSeconds < yellowThresholdSec) {
                return "text-success";
            } else if (totalSeconds < redThresholdSec) {
                return "text-warning";
            } else {
                return "text-danger";
            }
        }

        return "text-success";
    }

    get displayValue() {
        const totalSeconds = this.currentTotalSeconds;
        if (totalSeconds > 0) {
            return formatSecondsToStopwatch(totalSeconds);
        }
        return "00:00:00";
    }
}

export const stopwatchTimerWidget = {
    component: StopwatchTimerWidget,
    supportedTypes: ["float"],
    fieldDependencies: [
        { name: "timer_start", type: "datetime" },
        { name: "timer_last_start", type: "datetime" },
        { name: "timer_end", type: "datetime" },
        { name: "is_timer_running", type: "boolean" },
        { name: "is_timer_paused", type: "boolean" },
        { name: "accumulated_seconds", type: "float" },
        { name: "alloted_fru", type: "integer" },
    ],
};

registry.category("fields").add("stopwatch_timer", stopwatchTimerWidget);

/**
 * ResetTimerButtonWidget - Renders a reset icon button as an optional column in list views.
 */
export class ResetTimerButtonWidget extends Component {
    static template = xml`
        <button type="button" class="btn btn-link p-0 text-muted o_reset_timer_btn" 
                title="Reset Timer" 
                t-on-click="onReset"
                t-on-pointerdown.stop=""
                t-on-mousedown.stop="">
            <i class="fa fa-refresh fa-fw"/>
        </button>
    `;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.isProcessing = false;
    }

    async onReset(ev) {
        ev.stopPropagation();
        ev.preventDefault();
        if (this.isProcessing) {
            return;
        }
        this.isProcessing = true;
        try {
            // 1. Instant local reset across bus and record
            this.props.record.data.timer_start = false;
            this.props.record.data.timer_last_start = false;
            this.props.record.data.timer_end = false;
            this.props.record.data.is_timer_running = false;
            this.props.record.data.is_timer_paused = false;
            this.props.record.data.accumulated_seconds = 0.0;
            this.props.record.data.time_diff = 0.0;
            this.props.record.data.fru_status = "green";
            if (this.props.record._values) {
                Object.assign(this.props.record._values, {
                    timer_start: false,
                    timer_last_start: false,
                    timer_end: false,
                    is_timer_running: false,
                    is_timer_paused: false,
                    accumulated_seconds: 0.0,
                    time_diff: 0.0,
                    fru_status: "green",
                });
            }

            timerBus.trigger("RESET_TIMER", {
                resId: this.props.record.resId,
                recordId: this.props.record.id,
                record: this.props.record,
            });

            const root = this.props.record.model?.root;
            if (root && (this.props.record.isNew || !this.props.record.resId)) {
                const saved = await root.save();
                if (saved === false) {
                    this.isProcessing = false;
                    return;
                }
            }
            if (this.props.record.resId) {
                const result = await this.orm.call(
                    this.props.record.resModel,
                    "action_reset_timer",
                    [[this.props.record.resId]],
                    { context: this.props.record.context }
                );
                if (result && typeof result === "object") {
                    Object.assign(this.props.record.data, result);
                    if (this.props.record._values) {
                        Object.assign(this.props.record._values, result);
                    }
                    timerBus.trigger("RESET_TIMER", {
                        resId: this.props.record.resId,
                        recordId: this.props.record.id,
                        record: this.props.record,
                    });
                }
            }
        } catch (error) {
            console.error("Error executing reset action:", error);
        } finally {
            this.isProcessing = false;
        }
    }
}

export const resetTimerButtonWidget = {
    component: ResetTimerButtonWidget,
    supportedTypes: ["boolean"],
};

registry.category("fields").add("reset_timer_button", resetTimerButtonWidget);

/**
 * ActiveServiceTimerWidget - Displays active running duration in Job Card list view with a live ticking stopwatch and green indicator.
 */
export class ActiveServiceTimerWidget extends Component {
    static template = xml`
        <span t-if="displayValue" class="d-inline-flex align-items-center gap-1 fw-bold" t-att-class="timerColorClass">
            <i class="fa fa-circle me-1" style="font-size: 7px;"/>
            <span t-out="displayValue"/>
        </span>
    `;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            now: DateTime.now(),
        });
        this.interval = null;

        onWillStart(() => this.updateTimerState());
        onWillUpdateProps(() => this.updateTimerState());
        onWillDestroy(() => this.clearInterval());
    }

    clearInterval() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    get isRunning() {
        return Boolean(this.props.record.data.has_active_service_timer);
    }

    updateTimerState() {
        if (this.isRunning) {
            if (!this.interval) {
                this.state.now = DateTime.now();
                this.interval = setInterval(() => {
                    this.state.now = DateTime.now();
                }, 1000);
            }
        } else {
            this.clearInterval();
        }
    }

    get currentTotalSeconds() {
        const timerStartRaw = this.props.record.data.active_service_timer_last_start;
        const accumulated = Number(this.props.record.data.active_service_accumulated_seconds) || 0;
        let totalSeconds = accumulated;

        if (timerStartRaw) {
            const startDt = parseToLuxon(timerStartRaw);
            if (startDt && startDt.isValid) {
                const now = this.state.now || DateTime.now();
                const runSeconds = Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
                totalSeconds += runSeconds;
            }
        }

        if (totalSeconds > 0) {
            return totalSeconds;
        }

        const floatDiff = this.props.record.data[this.props.name];
        if (typeof floatDiff === "number" && floatDiff > 0) {
            return Math.round(floatDiff * 3600);
        }

        return 0;
    }

    get timerColorClass() {
        const fru = ("active_service_fru" in this.props.record.data && this.props.record.data.active_service_fru)
            ? Number(this.props.record.data.active_service_fru)
            : (("total_service_fru" in this.props.record.data && this.props.record.data.total_service_fru)
                ? Number(this.props.record.data.total_service_fru)
                : 0);
        const totalSeconds = this.currentTotalSeconds;

        if (fru > 0) {
            const fruSeconds = fru * 300; // 1 FRU = 5 minutes = 300 seconds
            if (totalSeconds < fruSeconds) {
                return "text-success"; // Green [0, FRU)
            } else if (totalSeconds < 2 * fruSeconds) {
                return "text-warning"; // Yellow [FRU, 2FRU)
            } else {
                return "text-danger"; // Red [2FRU, ..)
            }
        }

        // When FRU is not mentioned or in Zero:
        // [0, y/2400) -> green, [y/2400, y/1200) -> yellow, [y/1200, infinity) -> red
        const unitPrice = ("active_service_unit_price" in this.props.record.data && this.props.record.data.active_service_unit_price)
            ? Number(this.props.record.data.active_service_unit_price)
            : 0;

        if (unitPrice > 0) {
            const yellowThresholdSec = (unitPrice / 2400.0) * 3600.0;
            const redThresholdSec = (unitPrice / 1200.0) * 3600.0;

            if (totalSeconds < yellowThresholdSec) {
                return "text-success";
            } else if (totalSeconds < redThresholdSec) {
                return "text-warning";
            } else {
                return "text-danger";
            }
        }

        const fruStatus = ("active_service_fru_status" in this.props.record.data && this.props.record.data.active_service_fru_status)
            || this.props.record.data.wip_fru_status;
        if (fruStatus === "yellow") {
            return "text-warning";
        } else if (fruStatus === "red") {
            return "text-danger";
        }

        return "text-success";
    }

    get displayValue() {
        if (!this.isRunning) {
            return "";
        }
        const totalSeconds = this.currentTotalSeconds;
        if (totalSeconds > 0) {
            return formatSecondsToStopwatch(totalSeconds);
        }
        return "00:00:00";
    }
}

export const activeServiceTimerWidget = {
    component: ActiveServiceTimerWidget,
    supportedTypes: ["float"],
    fieldDependencies: [
        { name: "has_active_service_timer", type: "boolean" },
        { name: "active_service_timer_last_start", type: "datetime" },
        { name: "active_service_accumulated_seconds", type: "float" },
        { name: "total_service_fru", type: "float" },
        { name: "wip_fru_status", type: "selection" },
    ],
};

registry.category("fields").add("active_service_timer", activeServiceTimerWidget);

/**
 * EmployeeKanbanTimerWidget - Renders real-time ticking timers on Employee Kanban cards:
 * 1. Active Job (work_status == 'job'):
 *    - If service timer running (has_active_service_timer): ticks active service timer (green play badge e.g. 01:23:45)
 *    - If service timer paused/stopped: shows paused timer badge (dark badge with pause icon)
 * 2. Non-Job Statuses (Waiting for Car, Parts Unavailable, Tools Issue, Approval Pending, Idle)
 *    shows live status/downtime timer ticking from current_status_start (e.g. 00:15:42 with clock/warning indicator).
 */
export class EmployeeKanbanTimerWidget extends Component {
    static template = xml`
        <div class="o_employee_kanban_timer d-flex flex-column gap-1">
            <!-- Active Job with Running Service Timer -->
            <t t-if="isJobStatus and hasActiveServiceTimer">
                <div class="d-flex align-items-center justify-content-between">
                    <span class="badge px-2 py-1 d-inline-flex align-items-center rounded-pill shadow-sm" style="background-color: #198754 !important; color: #ffffff !important; border: 1px solid #146c43;">
                        <i class="fa fa-pause fa-fw small me-1" style="color: #ffffff !important;"/>
                        <span class="font-monospace fw-bold" style="font-size: 0.95rem; color: #ffffff !important;" t-out="serviceTimerDisplay"/>
                    </span>
                    <span class="badge text-bg-success px-2 py-1 d-inline-flex align-items-center">
                        <i class="fa fa-circle text-white me-1" style="font-size: 6px;"/>Job Running
                    </span>
                </div>
                <div t-if="activeServiceName" class="text-truncate text-muted small mt-1" t-att-title="activeServiceName">
                    <i class="fa fa-wrench me-1 text-primary"/>
                    <span class="fw-semibold text-dark" t-out="activeServiceName"/>
                </div>
            </t>

            <!-- Active Job but Timer Paused / Stopped (Static Display: Does NOT tick or start idle timer) -->
            <t t-elif="isJobStatus and !hasActiveServiceTimer">
                <div class="d-flex align-items-center justify-content-between">
                    <span class="badge px-2 py-1 d-inline-flex align-items-center rounded-pill shadow-sm" style="background-color: #495057 !important; color: #ffffff !important; border: 1px solid #343a40;">
                        <i class="fa fa-play fa-fw small me-1" style="color: #ffc107 !important;"/>
                        <span class="font-monospace fw-bold" style="font-size: 0.95rem; color: #ffffff !important;" t-out="pausedServiceTimerDisplay"/>
                    </span>
                    <span class="badge text-bg-warning text-dark px-2 py-1" t-out="pauseBadgeLabel"/>
                </div>
                <div t-if="activeServiceName" class="text-truncate text-muted small mt-1" t-att-title="activeServiceName">
                    <i class="fa fa-wrench me-1 text-secondary"/>
                    <span class="fw-semibold text-secondary" t-out="activeServiceName"/>
                </div>
            </t>

            <!-- Other Statuses (Waiting for Car, Parts Unavailable, Tools Issue, Approval Pending, Explicit Idle) WITH ACTIVE STATUS LOG -->
            <t t-elif="hasActiveStatusLog and hasStatusStart">
                <div class="d-flex align-items-center justify-content-between">
                    <span class="badge px-2 py-1 d-inline-flex align-items-center rounded-pill shadow-sm" t-att-style="statusBadgeStyle">
                        <i t-att-class="statusIconClass" t-att-style="statusIconStyle"/>
                        <span class="font-monospace fw-bold" t-att-style="statusTimerTextStyle" t-out="statusTimerDisplay"/>
                    </span>
                    <span t-att-class="statusPillClass" t-out="statusPillText"/>
                </div>
                <div t-if="statusNotes" class="text-truncate text-muted small mt-1" t-att-title="statusNotes">
                    <i class="fa fa-commenting-o me-1 text-secondary"/>
                    <span class="fst-italic" t-out="statusNotes"/>
                </div>
            </t>

            <!-- No Active Status Log in HR Employee Status Logs -->
            <t t-else="">
                <div class="d-flex align-items-center justify-content-between py-1">
                    <span class="text-muted small d-inline-flex align-items-center">
                        <i class="fa fa-circle-o fa-fw text-secondary me-1"/>No Active Timer
                    </span>
                    <span class="badge text-bg-light border text-muted px-2 py-1">Available</span>
                </div>
            </t>
        </div>
    `;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            now: DateTime.now(),
        });
        this.interval = null;

        onWillStart(() => this.startTicking());
        onWillUpdateProps(() => this.startTicking());
        onWillDestroy(() => this.stopTicking());
    }

    startTicking() {
        const shouldTick = this.hasActiveServiceTimer || (this.hasActiveStatusLog && this.hasStatusStart && !this.isJobStatus);
        if (shouldTick) {
            if (!this.interval) {
                this.state.now = DateTime.now();
                this.interval = setInterval(() => {
                    this.state.now = DateTime.now();
                }, 1000);
            }
        } else if (this.interval) {
            this.stopTicking();
        }
    }

    stopTicking() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    get hasActiveStatusLog() {
        return Boolean(this.props.record.data.has_active_status_log);
    }

    get hasStatusStart() {
        return Boolean(this.props.record.data.current_status_start);
    }

    get isJobStatus() {
        const data = this.props.record.data;
        const ws = data.work_status;
        return ws === 'job' || ws === 'paused' || Boolean(data.current_job_id) || Boolean(data.has_active_service_timer) || (Number(data.active_timer_accumulated_seconds) > 0);
    }

    get pauseBadgeLabel() {
        const pr = this.props.record.data.current_pause_reason;
        if (pr) {
            if (typeof pr === "string") return pr;
            if (pr.value) return pr.value;
        }
        return "Timer Paused";
    }

    get hasActiveServiceTimer() {
        return Boolean(this.props.record.data.has_active_service_timer);
    }

    get activeServiceName() {
        return this.props.record.data.active_service_name || "";
    }

    get statusNotes() {
        return this.props.record.data.status_notes || "";
    }

    get serviceTimerDisplay() {
        const data = this.props.record.data;
        let totalSeconds = Number(data.active_timer_accumulated_seconds) || 0;
        if (data.active_timer_last_start) {
            const startDt = parseToLuxon(data.active_timer_last_start);
            if (startDt && startDt.isValid) {
                const now = this.state.now || DateTime.now();
                totalSeconds += Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
            }
        }
        return formatSecondsToStopwatch(totalSeconds);
    }

    get pausedServiceTimerDisplay() {
        const totalSeconds = Number(this.props.record.data.active_timer_accumulated_seconds) || 0;
        return formatSecondsToStopwatch(totalSeconds);
    }

    get statusTimerSeconds() {
        const startRaw = this.props.record.data.current_status_start;
        if (!startRaw) return 0;
        const startDt = parseToLuxon(startRaw);
        if (!startDt || !startDt.isValid) return 0;
        const now = this.state.now || DateTime.now();
        return Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
    }

    get statusTimerDisplay() {
        return formatSecondsToStopwatch(this.statusTimerSeconds);
    }

    get statusBadgeStyle() {
        const status = this.props.record.data.work_status;
        switch(status) {
            case 'waiting_car':
                return 'background-color: #ffc107 !important; color: #000000 !important; border: 1px solid #d39e00;';
            case 'parts_unavailable':
            case 'tools_issue':
                return 'background-color: #dc3545 !important; color: #ffffff !important; border: 1px solid #b02a37;';
            case 'approval_pending':
                return 'background-color: #0dcaf0 !important; color: #000000 !important; border: 1px solid #0aa2c0;';
            case 'idle':
            default:
                return 'background-color: #212529 !important; color: #ffffff !important; border: 1px solid #000000;';
        }
    }

    get statusIconStyle() {
        const status = this.props.record.data.work_status;
        switch(status) {
            case 'waiting_car':
            case 'approval_pending':
                return 'color: #000000 !important; margin-right: 5px;';
            case 'idle':
                return 'color: #ffc107 !important; margin-right: 5px;';
            default:
                return 'color: #ffffff !important; margin-right: 5px;';
        }
    }

    get statusTimerTextStyle() {
        const status = this.props.record.data.work_status;
        switch(status) {
            case 'waiting_car':
            case 'approval_pending':
                return 'font-size: 0.95rem; color: #000000 !important; font-weight: bold;';
            case 'idle':
            default:
                return 'font-size: 0.95rem; color: #ffffff !important; font-weight: bold;';
        }
    }

    get statusPillText() {
        const status = this.props.record.data.work_status;
        switch(status) {
            case 'waiting_car': return 'Waiting for Car';
            case 'parts_unavailable': return 'Parts Arrival / Downtime';
            case 'tools_issue': return 'Tools Downtime';
            case 'approval_pending': return 'Pending Approval';
            case 'idle': return 'Idle Timer';
            default: return 'Status Active';
        }
    }

    get statusPillClass() {
        const status = this.props.record.data.work_status;
        switch(status) {
            case 'waiting_car': return 'badge text-bg-warning text-dark px-2 py-1';
            case 'parts_unavailable':
            case 'tools_issue': return 'badge text-bg-danger px-2 py-1';
            case 'approval_pending': return 'badge text-bg-info text-dark px-2 py-1';
            case 'idle':
            default: return 'badge text-bg-dark px-2 py-1';
        }
    }

    get statusIconClass() {
        const status = this.props.record.data.work_status;
        switch(status) {
            case 'waiting_car': return 'fa fa-clock-o fa-fw small';
            case 'parts_unavailable': return 'fa fa-exclamation-triangle fa-fw small';
            case 'tools_issue': return 'fa fa-wrench fa-fw small';
            case 'approval_pending': return 'fa fa-hourglass-half fa-fw small';
            case 'idle':
            default: return 'fa fa-coffee fa-fw small';
        }
    }
}

export const employeeKanbanTimerWidget = {
    component: EmployeeKanbanTimerWidget,
    supportedTypes: ["datetime", "float", "char", "selection"],
    fieldDependencies: [
        { name: "work_status", type: "selection" },
        { name: "current_status_start", type: "datetime" },
        { name: "has_active_status_log", type: "boolean" },
        { name: "has_active_service_timer", type: "boolean" },
        { name: "active_timer_last_start", type: "datetime" },
        { name: "active_timer_accumulated_seconds", type: "float" },
        { name: "active_timer_fru_status", type: "selection" },
        { name: "active_service_name", type: "char" },
        { name: "status_notes", type: "char" },
    ],
};

registry.category("fields").add("employee_kanban_timer", employeeKanbanTimerWidget);

/**
 * CollectiveLiveTimerWidget
 * Displays the live collective countdown timer in the Collective Timer control bar.
 * Computes target countdown time from the sum of Hrs of selected services,
 * shows target hours while selecting, and counts down while running.
 */
export class CollectiveLiveTimerWidget extends Component {
    static template = xml`
        <t t-if="hasTarget or isRunning or elapsedSeconds > 0">
            <span class="d-inline-flex align-items-center gap-2 px-2 py-1 rounded font-monospace fs-6 fw-bold shadow-sm"
                  t-att-class="containerClass">
                <i t-if="isOvertime" class="fa fa-exclamation-triangle fa-spin text-danger"/>
                <i t-elif="isRunning" class="fa fa-hourglass-half fa-spin text-success"/>
                <i t-elif="isPaused" class="fa fa-pause-circle text-warning"/>
                <i t-else="" class="fa fa-hourglass-start text-primary"/>
                <span t-out="displayValue"/>
                <span t-att-class="badgeClass" t-out="badgeLabel"/>
            </span>
        </t>
        <t t-else="">
            <span class="text-muted small fst-italic py-1 px-2">
                <i class="fa fa-info-circle me-1"/>Select services to start
            </span>
        </t>
    `;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            now: DateTime.now(),
        });
        this.interval = null;
        this.isLocallyPaused = false;

        this.onPauseAll = () => {
            this.isLocallyPaused = true;
            if (this.interval) {
                clearInterval(this.interval);
                this.interval = null;
            }
            this.render();
        };
        timerBus.addEventListener("PAUSE_ALL_TIMERS", this.onPauseAll);

        onMounted(() => this.updateInterval());
        onPatched(() => this.updateInterval());
        onWillUpdateProps((nextProps) => {
            if (nextProps.record && nextProps.record.data) {
                if (nextProps.record.data.is_collective_timer_running) {
                    this.isLocallyPaused = false;
                }
            }
            this.updateInterval();
        });
        onWillDestroy(() => {
            if (this.interval) clearInterval(this.interval);
            timerBus.removeEventListener("PAUSE_ALL_TIMERS", this.onPauseAll);
        });
    }

    updateInterval() {
        const shouldRun = this.isRunning;
        if (shouldRun && !this.interval) {
            this.interval = setInterval(() => {
                this.state.now = DateTime.now();
            }, 1000);
        } else if (!shouldRun && this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    getSelectedLines() {
        const data = this.props.record.data;
        if (!data || !data.service_line_ids || !data.service_line_ids.records) {
            return [];
        }
        const records = data.service_line_ids.records;
        const running = records.filter(r => Boolean(r.data.is_timer_running && r.data.is_collective));
        if (running.length > 0) {
            return running;
        }
        return records.filter(r => Boolean(r.data.is_group_selected));
    }

    get targetHours() {
        const lines = this.getSelectedLines();
        let sumHrs = 0;
        for (const l of lines) {
            let h = Number(l.data.hours ?? l.data.hrs) || 0;
            if (!h && l.data.alloted_fru) {
                h = (Number(l.data.alloted_fru) * 5) / 60.0;
            }
            if (!h && l.data.subtotal) {
                h = Number(l.data.subtotal) / 2400.0;
            }
            sumHrs += h;
        }
        if (sumHrs === 0 && this.props.record.data.collective_target_hours) {
            sumHrs = Number(this.props.record.data.collective_target_hours) || 0;
        }
        return Math.round(sumHrs * 100) / 100;
    }

    get targetSeconds() {
        if (this.targetHours > 0) {
            return Math.round(this.targetHours * 3600);
        }
        const targetSec = Number(this.props.record.data.collective_target_seconds) || 0;
        return targetSec;
    }

    get elapsedSeconds() {
        const data = this.props.record.data;
        let total = Number(data.collective_accumulated_seconds) || 0;
        if (!total && (!this.isRunning || !data.collective_timer_last_start)) {
            const lines = this.getSelectedLines();
            total = lines.reduce((acc, l) => acc + (Number(l.data.accumulated_seconds) || 0), 0);
        }
        if (this.isRunning && data.collective_timer_last_start) {
            const startDt = parseToLuxon(data.collective_timer_last_start);
            if (startDt && startDt.isValid) {
                const now = this.state.now || DateTime.now();
                const delta = Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
                total += delta;
            }
        }
        return total;
    }

    get remainingSeconds() {
        const target = this.targetSeconds;
        if (target > 0) {
            return target - this.elapsedSeconds;
        }
        return 0;
    }

    get isRunning() {
        if (this.isLocallyPaused) return false;
        return Boolean(this.props.record.data.is_collective_timer_running);
    }

    get isPaused() {
        return !this.isRunning && this.elapsedSeconds > 0 && (this.targetSeconds > 0 || this.props.record.data.collective_selected_count > 0);
    }

    get hasTarget() {
        return this.targetSeconds > 0;
    }

    get isOvertime() {
        return this.hasTarget && this.remainingSeconds < 0;
    }

    get displayValue() {
        if (this.hasTarget) {
            const rem = this.remainingSeconds;
            if (rem < 0) {
                return `-${formatSecondsToStopwatch(Math.abs(rem))}`;
            }
            return formatSecondsToStopwatch(rem);
        }
        return formatSecondsToStopwatch(this.elapsedSeconds);
    }

    get hrsDisplay() {
        const target = this.targetHours;
        if (target <= 0) return "";
        if (this.isOvertime) {
            return `${target.toFixed(2)} Hrs exceeded`;
        }
        if (this.isRunning || this.isPaused) {
            const remHrs = Math.max(0, Math.round((this.remainingSeconds / 3600) * 100) / 100);
            return `${remHrs.toFixed(2)} / ${target.toFixed(2)} Hrs`;
        }
        return `${target.toFixed(2)} Hrs`;
    }

    get containerClass() {
        if (this.isOvertime) {
            return "bg-danger-subtle border border-danger text-danger";
        }
        if (this.isRunning) {
            return "bg-white border border-success text-success";
        }
        if (this.isPaused) {
            return "bg-warning-subtle border border-warning text-dark";
        }
        return "bg-primary-subtle border border-primary text-primary";
    }

    get badgeClass() {
        if (this.isOvertime) return "badge text-bg-danger";
        if (this.isRunning) return "badge text-bg-success";
        if (this.isPaused) return "badge text-bg-warning text-dark";
        return "badge text-bg-primary";
    }

    get badgeLabel() {
        if (this.isOvertime) {
            return `Overtime (${this.hrsDisplay})`;
        }
        if (this.isRunning) {
            return `Countdown (${this.hrsDisplay})`;
        }
        if (this.isPaused) {
            return `Paused (${this.hrsDisplay})`;
        }
        return `Target (${this.hrsDisplay})`;
    }
}

export const collectiveLiveTimerWidget = {
    component: CollectiveLiveTimerWidget,
    supportedTypes: ["float"],
    fieldDependencies: [
        { name: "is_collective_timer_running", type: "boolean" },
        { name: "collective_timer_last_start", type: "datetime" },
        { name: "collective_accumulated_seconds", type: "float" },
        { name: "collective_selected_count", type: "integer" },
        { name: "collective_target_hours", type: "float" },
        { name: "collective_target_seconds", type: "float" },
        { name: "collective_remaining_seconds", type: "float" },
    ],
};

registry.category("fields").add("collective_live_timer", collectiveLiveTimerWidget);

/**
 * KanbanLiveTimerWidget - Ticking live stopwatch timer for Kanban cards.
 * Uses active_timer_last_start + active_timer_accumulated_seconds when has_active_service_timer is true.
 */
export class KanbanLiveTimerWidget extends Component {
    static template = xml`
        <span class="o_kanban_live_timer font-monospace" t-out="displayValue"/>
    `;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            now: DateTime.now(),
        });
        this.interval = null;
        this.mountTime = DateTime.now();

        onWillStart(() => this.updateTimerState());
        onMounted(() => this.updateTimerState());
        onPatched(() => this.updateTimerState());
        onWillUpdateProps(() => this.updateTimerState());
        onWillDestroy(() => this.clearInterval());
    }

    clearInterval() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    get isRunning() {
        const d = this.props.record.data;
        if (this.props.name === "idle_duration") {
            return Boolean(d.is_idle_running || (d.work_status === "idle" && d.idle_timer_start));
        }
        if (
            this.props.name === "current_pause_duration" ||
            this.props.name === "current_pause_time_display" ||
            this.props.name === "pause_duration" ||
            this.props.name === "pause_time_display"
        ) {
            return Boolean(
                d.is_pause_running ||
                ((d.work_status === "paused" || d.job_status === "paused" || d.status === "paused") &&
                 (d.current_pause_reason || d.pause_reason || d.pause_timer_start)) ||
                d.current_pause_reason ||
                d.pause_reason
            );
        }
        return Boolean(d.has_active_service_timer);
    }

    updateTimerState() {
        if (this.isRunning) {
            if (!this.interval) {
                this.state.now = DateTime.now();
                this.interval = setInterval(() => {
                    this.state.now = DateTime.now();
                }, 1000);
            }
        } else {
            this.clearInterval();
        }
    }

    get currentTotalSeconds() {
        const data = this.props.record.data;

        // Idle timer running - ONLY when widget is rendering idle_duration
        if (this.props.name === "idle_duration") {
            let total = Number(data.idle_accumulated_seconds) || 0;
            if (data.idle_timer_start && (data.is_idle_running || data.work_status === "idle")) {
                const startDt = parseToLuxon(data.idle_timer_start);
                if (startDt && startDt.isValid) {
                    const now = this.state.now || DateTime.now();
                    const runSeconds = Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
                    total += runSeconds;
                }
            }
            if (total > 0) return total;
            const floatDiff = this.props.record.data[this.props.name];
            if (typeof floatDiff === "number" && floatDiff > 0) {
                return Math.round(floatDiff * 3600);
            }
            return 0;
        }

        // Pause timer running - when rendering current_pause_duration / pause_duration / current_pause_time_display / pause_time_display
        if (
            this.props.name === "current_pause_duration" ||
            this.props.name === "current_pause_time_display" ||
            this.props.name === "pause_duration" ||
            this.props.name === "pause_time_display"
        ) {
            let total = Number(data.pause_accumulated_seconds) || 0;
            const pauseStart = data.pause_timer_start;
            const isPaused = Boolean(
                data.is_pause_running ||
                ((data.work_status === "paused" || data.job_status === "paused" || data.status === "paused") &&
                 (data.current_pause_reason || data.pause_reason || pauseStart)) ||
                data.current_pause_reason ||
                data.pause_reason
            );

            if (isPaused && pauseStart) {
                const startDt = parseToLuxon(pauseStart);
                if (startDt && startDt.isValid) {
                    const now = this.state.now || DateTime.now();
                    const runSeconds = Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
                    total += runSeconds;
                    return total;
                }
            }

            // Fallback if pause_timer_start is missing or parsing, but we have base pause value
            let baseSeconds = 0;
            const val = this.props.record.data[this.props.name];
            if (typeof val === "number" && val > 0) {
                baseSeconds = Math.round(val * 3600);
            } else if (typeof val === "string" && val.includes(":")) {
                const parts = val.split(":").map(Number);
                if (parts.length === 3 && !parts.some(isNaN)) {
                    baseSeconds = parts[0] * 3600 + parts[1] * 60 + parts[2];
                }
            }

            if (isPaused && baseSeconds > 0) {
                if (!this.mountTime) {
                    this.mountTime = DateTime.now();
                }
                const now = this.state.now || DateTime.now();
                const runSeconds = Math.max(0, Math.floor(now.diff(this.mountTime, "seconds").seconds));
                return baseSeconds + runSeconds;
            }

            return baseSeconds;
        }

        // Active service timer running
        const accumulated = Number(data.active_timer_accumulated_seconds) || 0;
        let totalSeconds = accumulated;

        if (this.isRunning && data.active_timer_last_start) {
            const startDt = parseToLuxon(data.active_timer_last_start);
            if (startDt && startDt.isValid) {
                const now = this.state.now || DateTime.now();
                const runSeconds = Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
                totalSeconds += runSeconds;
            }
        }

        if (totalSeconds > 0) {
            return totalSeconds;
        }

        const floatDiff = this.props.record.data[this.props.name];
        if (typeof floatDiff === "number" && floatDiff > 0) {
            return Math.round(floatDiff * 3600);
        }

        return 0;
    }

    get displayValue() {
        const totalSeconds = this.currentTotalSeconds;
        return formatSecondsToStopwatch(totalSeconds);
    }
}

export const kanbanLiveTimerWidget = {
    component: KanbanLiveTimerWidget,
    supportedTypes: ["float", "char"],
    fieldDependencies: [
        { name: "has_active_service_timer", type: "boolean" },
        { name: "active_timer_last_start", type: "datetime" },
        { name: "active_timer_accumulated_seconds", type: "float" },
        { name: "is_idle_running", type: "boolean" },
        { name: "idle_timer_start", type: "datetime" },
        { name: "idle_accumulated_seconds", type: "float" },
        { name: "is_pause_running", type: "boolean" },
        { name: "pause_timer_start", type: "datetime" },
        { name: "pause_accumulated_seconds", type: "float" },
        { name: "current_pause_reason", type: "selection" },
        { name: "work_status", type: "selection" },
    ],
};

export const pauseLiveTimerWidget = {
    component: KanbanLiveTimerWidget,
    supportedTypes: ["float", "char"],
    fieldDependencies: [
        { name: "is_pause_running", type: "boolean" },
        { name: "pause_timer_start", type: "datetime" },
        { name: "pause_accumulated_seconds", type: "float" },
        { name: "pause_reason", type: "selection" },
        { name: "job_status", type: "selection" },
        { name: "status", type: "selection" },
    ],
};

registry.category("fields").add("kanban_live_timer", kanbanLiveTimerWidget);
registry.category("fields").add("pause_live_timer", pauseLiveTimerWidget);







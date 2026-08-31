/** @odoo-module **/

import { Component, EventBus, useState, onWillStart, onWillUpdateProps, onWillDestroy, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { useService } from "@web/core/utils/hooks";

export const timerBus = new EventBus();

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
 * StopwatchTimerWidget - Renders Duration (time_diff) and ticks live every 1s like a stopwatch when timer is running.
 */
export class StopwatchTimerWidget extends Component {
    static template = xml`
        <span class="d-inline-flex align-items-center gap-2 o_stopwatch_wrapper me-4" t-on-click.stop="">
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
            <span class="o_field_stopwatch_timer fw-bold" t-att-class="timerColorClass" t-out="displayValue"/>
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
        timerBus.addEventListener("RESET_TIMER", this.onTimerReset);

        onWillStart(() => this.updateTimerState());
        onWillUpdateProps((nextProps) => this.syncFromProps(nextProps));
        onWillDestroy(() => {
            this.clearInterval();
            timerBus.removeEventListener("RESET_TIMER", this.onTimerReset);
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
                const runSeconds = Math.max(0, Math.floor(now.diff(startDt, "seconds").seconds));
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
            : (("quantity" in this.props.record.data) ? (Number(this.props.record.data.quantity) || 0) : 0);
        const fruSeconds = fru * 300; // 1 FRU = 5 minutes = 300 seconds
        const totalSeconds = this.currentTotalSeconds;

        if (fruSeconds > 0) {
            if (totalSeconds <= fruSeconds) {
                return "text-success"; // Green [0, FRU]
            } else if (totalSeconds <= 2 * fruSeconds) {
                return "text-warning"; // Yellow (FRU, 2FRU]
            } else {
                return "text-danger"; // Red (2FRU, ..]
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
        const fru = Number(this.props.record.data.total_service_fru) || 0;
        const fruSeconds = fru * 300; // 1 FRU = 5 minutes = 300 seconds
        const totalSeconds = this.currentTotalSeconds;

        if (fruSeconds > 0) {
            if (totalSeconds <= fruSeconds) {
                return "text-success"; // Green [0, FRU]
            } else if (totalSeconds <= 2 * fruSeconds) {
                return "text-warning"; // Yellow (FRU, 2FRU]
            } else {
                return "text-danger"; // Red (2FRU, ..]
            }
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
    ],
};

registry.category("fields").add("active_service_timer", activeServiceTimerWidget);



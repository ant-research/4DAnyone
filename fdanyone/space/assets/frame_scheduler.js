// One Rerun instance, one pending browser frame. Eframe's recursive rAF request
// stays queued while idle; input, new data and decoded frames wake it explicitly.
export function createFrameScheduler(fps) {
    const callbacks = new Map();
    const observers = new Set();
    let nextId = 0, timer = null, frame = null, disposed = false;
    let loading = true, playing = false, visible = true;
    let awakeUntil = 0, interactiveUntil = 0;
    let deadline = 0, lastFrame = -Infinity, interval = 0;

    function cancelPending() {
        if (timer !== null) clearTimeout(timer);
        if (frame !== null) cancelAnimationFrame(frame);
        timer = frame = null;
    }
    function active(now) {
        return visible && (loading || playing || now < awakeUntil);
    }
    function schedule() {
        if (disposed || !callbacks.size) return;
        const now = performance.now();
        if (!active(now)) { cancelPending(); return; }
        const period = 1000 / (loading || now < interactiveUntil ? Math.max(60, fps) : fps);
        if (period !== interval) {
            interval = period;
            deadline = lastFrame + period;
            cancelPending();
        }
        if (timer !== null || frame !== null) return;
        const enqueue = () => {
            timer = null;
            frame = requestAnimationFrame(draw);
        };
        // Queue rAF slightly early: browser timers may be coalesced with vsync,
        // and requesting at the deadline can otherwise miss an entire video frame.
        const delay = deadline - now - Math.min(1000 / 60, interval / 2);
        if (delay > 0) timer = setTimeout(enqueue, delay);
        else enqueue();
    }
    function draw(now) {
        frame = null;
        if (disposed || !active(now)) return;
        lastFrame = now;
        // Keep the cadence when the display rate is not a multiple of the video
        // rate. Skip missed slots after a stall instead of drawing catch-up frames.
        deadline = now - deadline >= interval ? now + interval : deadline + interval;
        const batch = [...callbacks.keys()];
        for (const id of batch) {
            const callback = callbacks.get(id);
            callbacks.delete(id);
            callback?.(now);
        }
        for (const callback of observers) callback(now);
        schedule();
    }
    function invalidate() {
        if (disposed) return;
        awakeUntil = performance.now() + 1000;
        schedule();
    }
    return {
        request(callback) {
            if (disposed) return 0;
            const id = ++nextId;
            callbacks.set(id, callback);
            schedule();
            return id;
        },
        cancel(id) {
            callbacks.delete(id);
            if (!callbacks.size) cancelPending();
        },
        invalidate,
        onFrame(callback) {
            observers.add(callback);
            return () => observers.delete(callback);
        },
        alignTime(seconds) {
            if (!playing || performance.now() < interactiveUntil || !Number.isFinite(seconds)) return;
            // Present near the middle of the next video frame, not its boundary.
            // Display/vsync jitter would otherwise repeat one frame and skip the next.
            deadline = lastFrame + ((Math.floor(seconds * fps) + 1.5) / fps - seconds) * 1000;
            cancelPending();
            schedule();
        },
        interact() {
            interactiveUntil = performance.now() + 250;
            invalidate();
        },
        setPlaying(value) {
            loading = false;
            playing = value;
            invalidate();
        },
        setVisible(value) {
            visible = value;
            if (visible) invalidate();
            else cancelPending();
        },
        dispose() {
            disposed = true;
            cancelPending();
            callbacks.clear();
            observers.clear();
        }
    };
}

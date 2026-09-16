import {WebViewer} from './rerun/index.js';
import {fetchBytes} from './media_cache.js';
import {createFrameScheduler} from './frame_scheduler.js';

// One recording owns the Rerun viewer, channel and rendering schedule.
export async function openScene(host, wasm, data, signal) {
    const viewer = new WebViewer();
    const frames = createFrameScheduler(data.fps);
    const listeners = new AbortController();
    const events = {signal: listeners.signal, capture: true, passive: true};
    let recording, playing = false, seekTime = null;
    function applyPlayback() {
        const visible = !document.hidden;
        frames.setVisible(visible);
        if (recording) frames.setPlaying(playing && visible);
    }
    let dragging = false;
    host.addEventListener('pointerdown', () => { dragging = true; frames.interact(); }, events);
    document.addEventListener('pointermove', () => { if (dragging) frames.interact(); }, events);
    for (const name of ['pointerup', 'pointercancel']) {
        document.addEventListener(name, () => { if (dragging) frames.interact(); dragging = false; }, events);
    }
    for (const name of ['pointermove', 'pointerleave', 'wheel', 'keydown', 'keyup', 'focus', 'blur']) {
        host.addEventListener(name, () => frames.interact(), events);
    }
    document.addEventListener('visibilitychange', applyPlayback, events);
    applyPlayback();
    function dispose() {
        listeners.abort();
        // Destroy wasm while its queued callbacks still exist, then drop the scheduler.
        try { viewer.stop(); } finally { frames.dispose(); }
    }
    try {
        const [download, initialization] = await Promise.allSettled([
            fetchBytes(data.recording, signal),
            viewer.start(null, host, {
                base_url: new URL(wasm, document.baseURI).href, hide_welcome_screen: true,
                allow_fullscreen: false, theme: 'dark', width: '100%', height: '100%',
                frame_scheduler: frames
            })
        ]);
        signal.throwIfAborted();
        if (download.status === 'rejected') throw download.reason;
        if (initialization.status === 'rejected') throw initialization.reason;
        for (const panel of ['top', 'blueprint', 'selection', 'time']) viewer.override_panel_state(panel, 'hidden');
        const channel = viewer.open_channel('4danyone-space');
        channel.send_rrd(new Uint8Array(download.value));
        for (let index = 0; index < 300; index++) {
            await new Promise(resolve => requestAnimationFrame(resolve));
            signal.throwIfAborted();
            const active = viewer.get_active_recording_id();
            if (active && (viewer.get_time_range(active, 'time') || !data.frames)) {
                recording = active;
                break;
            }
        }
        if (!recording) throw new Error('The Scene Recording Did Not Open');
        applyPlayback();
        frames.onFrame(() => {
            // Rerun applies commands during rendering. Reconcile the latest
            // intent afterward so queued pauses and seeks cannot overwrite it.
            const seconds = viewer.get_current_time(recording, 'time') / 1e9;
            if (seekTime !== null) {
                if (Math.abs(seconds - seekTime) < 0.001) seekTime = null;
                else viewer.set_current_time(recording, 'time', seekTime * 1e9);
            }
            const desired = playing && !document.hidden && seekTime === null;
            if (viewer.get_playing(recording) !== desired) viewer.set_playing(recording, desired);
            frames.alignTime(seconds);
        });
        return {
            get time() { return seekTime ?? viewer.get_current_time(recording, 'time') / 1e9; },
            set time(seconds) {
                seekTime = Math.max(0, Math.min(seconds, (data.frames - 1) / data.fps));
                frames.invalidate();
            },
            get playing() { return playing; },
            set playing(value) {
                // Playback intent survives hidden tabs and queued Rerun commands.
                playing = value;
                applyPlayback();
            },
            focus() { viewer.canvas.focus({preventScroll: true}); },
            onFrame: frames.onFrame,
            async append(update, signal) {
                if (data.recording_id !== update.recording_id) throw new Error('Reload The Page To Restore The Camera Preview');
                const bytes = await fetchBytes(update.recording, signal);
                signal.throwIfAborted();
                channel.send_rrd(new Uint8Array(bytes));
                frames.invalidate();
            },
            dispose
        };
    } catch (error) {
        dispose();
        throw error;
    }
}

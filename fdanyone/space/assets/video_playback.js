// Native videos run continuously; the scene clock only corrects their phase.
export function createVideoPlayback(video, fps, period) {
    let aligned = false, pausedTarget = null;
    function pause() { if (!video.paused) video.pause(); }
    function setPlaying(playing) {
        // A suspended decoder may need play() before it can finish a seek.
        if (playing && video.paused) video.play().catch(() => {});
        else if (!playing) pause();
    }
    function setRate(rate) {
        if (rate === 1 ? video.playbackRate !== 1 : Math.abs(video.playbackRate - rate) > 0.01) video.playbackRate = rate;
    }
    return {
        pause,
        reset() { aligned = false; pausedTarget = null; },
        sync(seconds, playing) {
            setPlaying(playing);
            if (video.readyState < 2 || video.seeking) return false;
            if (seconds === null) { setRate(1); return true; }
            const wanted = Math.max(0, Math.min(seconds, Math.max(0, video.duration - 0.001)));
            const difference = wanted - video.currentTime;
            const samePausedTarget = pausedTarget !== null && Math.abs(wanted - pausedTarget) < 0.25 / fps;
            const seek = (!aligned || (!playing && !samePausedTarget)) && Math.abs(difference) > 0.5 / fps;
            aligned = true;
            pausedTarget = playing ? null : wanted;
            if (seek) {
                setRate(1);
                video.currentTime = wanted;
                return !video.seeking;
            }
            // Wrap phase at the clip boundary so each native loop needs no seek.
            const phase = period > 0 ? difference - Math.round(difference / period) * period : difference;
            setRate(playing ? 1 + Math.max(-0.25, Math.min(0.25, phase * 0.8)) : 1);
            return true;
        }
    };
}

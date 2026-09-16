import {createOverlay} from './overlay.js';
import {createVideoCache} from './video_cache.js';
import {createVideoPlayback} from './video_playback.js';

export function createMediaView(root, data, showNote) {
    const sourceHost = root.querySelector('.source-preview');
    const grid = root.querySelector('.target-grid');
    const scroller = root.querySelector('.target-scroll');
    const enlarged = root.querySelector('.media-enlarged');
    const playButton = root.querySelector('.scene-play');
    const listeners = new AbortController();
    const events = {signal: listeners.signal};
    const cache = createVideoCache();
    const media = [];
    const period = Math.max(1 / data.fps, (data.frames - 1) / data.fps);
    let source, overlay, scene, stopFrames, disposed = false, connected = false;
    let tickHandle = null, viewportHandle = null, maximized = null, enlargedPlayback = null;

    function requestTick() {
        if (!disposed && tickHandle === null) tickHandle = requestAnimationFrame(tick);
    }
    function requestViewport() {
        if (!disposed && viewportHandle === null) viewportHandle = requestAnimationFrame(updateViewport);
    }
    function releaseVideo(item) {
        clearTimeout(item.releaseTimer);
        item.releaseTimer = null;
        item.onLoaded?.(false);
        item.onLoaded = null;
        const lease = item.lease;
        item.lease = null;
        item.preparing = null;
        item.playback.pause();
        item.playback.reset();
        item.video.removeAttribute('src');
        item.video.load();
        lease?.release();
        item.presentedTime = null;
    }
    function prepareVideo(item) {
        clearTimeout(item.releaseTimer);
        item.releaseTimer = null;
        if (item.preparing) return item.preparing;
        const lease = item.lease = cache.acquire(item.url);
        item.preparing = (async () => {
            const url = await lease.ready;
            if (disposed || item.lease !== lease) return false;
            const decoded = new Promise(resolve => { item.onLoaded = resolve; });
            item.video.src = url;
            item.video.load();
            return await decoded;
        })().catch(error => {
            if (!disposed && item.lease === lease && error.name !== 'AbortError') showNote(`Cannot Play ${item.id}: ${error.message}`);
            return false;
        });
        return item.preparing;
    }
    function masterTime() {
        if (maximized) return enlargedPlayback.ready ? maximized.video.currentTime : enlargedPlayback.time;
        return scene?.time ?? 0;
    }
    function isPlaying() { return maximized ? enlargedPlayback.playing : !!scene?.playing; }
    function togglePlayback() {
        if (root.dataset.ready !== 'true') return;
        const playing = !isPlaying();
        if (maximized) enlargedPlayback.playing = playing;
        else scene.playing = playing;
        if (!playing) for (const item of media) item.playback.pause();
        requestTick();
    }
    playButton.addEventListener('click', event => {
        event.stopPropagation();
        scene.playing = true;
        scene.focus();
        requestTick();
    }, events);

    function updateViewport() {
        cancelAnimationFrame(viewportHandle);
        viewportHandle = null;
        if (disposed) return;
        const bounds = scroller.getBoundingClientRect();
        const nearby = [];
        for (const item of media) {
            if (item === source) continue;
            const tile = item.tile.getBoundingClientRect();
            const overlap = Math.min(tile.bottom, bounds.bottom) - Math.max(tile.top, bounds.top);
            const visible = overlap > Math.min(24, tile.height * 0.1);
            const center = (tile.top + tile.bottom) / 2;
            const near = center > bounds.top - bounds.height && center < bounds.bottom + bounds.height;
            if (near) nearby.push(item.url);
            if (visible) {
                if (!item.visible) item.playback.reset();
                prepareVideo(item);
            } else if (item !== maximized) {
                item.playback.pause();
                if (!near && item.lease) releaseVideo(item);
                else if (item.lease && item.releaseTimer === null) {
                    // Retain a just-hidden decoder briefly for quick scroll reversals.
                    item.releaseTimer = setTimeout(() => {
                        if (!item.visible && item !== maximized) releaseVideo(item);
                    }, 1500);
                }
            }
            item.visible = visible;
        }
        // Offscreen clips must not compete with the initial scene download.
        if (connected) cache.prefetch(nearby);
        requestTick();
    }
    scroller.addEventListener('scroll', requestViewport, {...events, passive: true});
    function resizeMedia() {
        const style = getComputedStyle(grid);
        const gap = parseFloat(style.columnGap);
        const minimum = parseFloat(style.getPropertyValue('--target-min-width'));
        const columns = style.gridTemplateColumns.split(' ').filter(size => parseFloat(size) > 0).length
            || Math.max(1, Math.floor((grid.clientWidth + gap) / (minimum + gap)));
        const width = Math.max(1, (grid.clientWidth - (columns - 1) * gap) / columns - 2);
        const aspect = data.targets.length ? Math.max(...data.targets.map(video => video.width / video.height)) : 0.55;
        const height = width / aspect;
        root.style.setProperty('--target-panel-height', `${Math.min(Math.max(180, height + 54), root.clientHeight * 0.55)}px`);
        root.dataset.targetColumns = String(columns);
        const sourceAspect = source?.aspect || 9 / 16;
        const stage = root.querySelector('.scene-stage');
        const sourceHeight = Math.max(1, Math.min(height, stage.clientHeight - 26, (stage.clientWidth * 0.4 - 2) / sourceAspect));
        root.style.setProperty('--source-tile-width', `${sourceHeight * sourceAspect}px`);
        root.style.setProperty('--source-tile-height', `${sourceHeight}px`);
        requestViewport();
    }
    const sizes = new ResizeObserver(resizeMedia);
    sizes.observe(scroller);
    sizes.observe(grid);
    sizes.observe(root.querySelector('.scene-stage'));

    function maximize(item) {
        restore();
        enlargedPlayback = {time: masterTime(), playing: isPlaying(), ready: false};
        maximized = item;
        playButton.hidden = true;
        scene.playing = false;
        for (const other of media) other.playback.pause();
        item.playback.reset();
        prepareVideo(item);
        item.placeholder = document.createComment('video-position');
        item.content.before(item.placeholder);
        enlarged.querySelector('.enlarged-content').append(item.content);
        enlarged.querySelector('.enlarged-title').textContent = item === source ? 'Source Video' : `View ${item.id}`;
        enlarged.hidden = false;
        enlarged.querySelector('.media-back').focus();
        requestTick();
    }
    function restore() {
        if (!maximized) return;
        const seconds = masterTime(), playing = isPlaying();
        const item = maximized;
        item.placeholder.replaceWith(item.content);
        maximized = null;
        enlargedPlayback = null;
        enlarged.hidden = true;
        scene.time = Math.min(seconds, period);
        scene.playing = playing;
        for (const video of media) video.playback.reset();
        item.button.focus({preventScroll: true});
        requestViewport();
        requestTick();
    }
    enlarged.querySelector('.media-back').addEventListener('click', restore, events);
    root.addEventListener('keydown', event => {
        if (event.code === 'Space' && !event.isComposing
            && !event.target.closest('input, textarea, select, [contenteditable="true"]')) {
            event.preventDefault();
            event.stopPropagation();
            if (!event.repeat) togglePlayback();
        }
        if (event.key === 'Escape' && maximized) {
            event.preventDefault();
            event.stopPropagation();
            restore();
        }
    }, {...events, capture: true});
    sourceHost.addEventListener('wheel', event => event.stopPropagation(), events);
    sourceHost.addEventListener('pointerdown', event => event.stopPropagation(), events);

    function createVideo(description, isSource = false) {
        const tile = document.createElement('div');
        tile.className = 'media-tile';
        const aspect = description.width / description.height;
        tile.style.setProperty('--video-aspect', aspect);
        const content = document.createElement('div');
        content.className = 'video-content';
        const video = document.createElement('video');
        video.muted = true;
        video.playsInline = true;
        video.loop = true;
        video.preload = 'auto';
        video.disablePictureInPicture = true;
        video.disableRemotePlayback = true;
        video.setAttribute('aria-label', isSource ? 'Source Video' : `Target View ${description.id}`);
        content.append(video);
        const id = isSource ? 'Source Video' : String(description.id).padStart(2, '0');
        const title = document.createElement('span');
        title.className = isSource ? 'source-title' : 'view-number';
        title.textContent = id;
        const button = document.createElement('button');
        button.className = 'video-enlarge';
        button.type = 'button';
        button.textContent = '↗';
        button.setAttribute('aria-label', isSource ? 'Enlarge Source Video' : `Enlarge View ${id}`);
        tile.append(content, title, button);
        const playback = createVideoPlayback(video, data.fps, period);
        const item = {tile, content, video, playback, button, id, aspect, url: description.url,
            visible: isSource, lease: null, preparing: null, onLoaded: null, releaseTimer: null};
        button.addEventListener('click', () => maximize(item), events);
        video.addEventListener('loadeddata', () => {
            item.onLoaded?.(true);
            item.onLoaded = null;
            requestTick();
        }, events);
        video.addEventListener('error', () => {
            item.onLoaded?.(false);
            item.onLoaded = null;
            if (item.lease) showNote(`Cannot Play ${id}`);
        }, events);
        if (isSource && data.overlay) {
            const onFrame = (_, metadata) => {
                item.presentedTime = metadata.mediaTime;
                if (overlay && (!maximized || maximized === source)) overlay.draw(metadata.mediaTime);
                if (!disposed) item.frameCallback = video.requestVideoFrameCallback(onFrame);
            };
            item.frameCallback = video.requestVideoFrameCallback(onFrame);
        }
        for (const name of ['timeupdate', 'seeked']) video.addEventListener(name, requestTick, events);
        media.push(item);
        if (isSource) {
            sourceHost.append(tile);
            sourceHost.hidden = false;
        } else grid.append(tile);
        return item;
    }

    document.addEventListener('visibilitychange', () => {
        for (const item of media) {
            if (document.hidden) item.playback.pause();
            else item.playback.reset();
        }
        requestTick();
    }, events);
    if (data.source) {
        source = createVideo(data.source, true);
        prepareVideo(source);
    }
    for (const target of data.targets) createVideo(target);
    resizeMedia();
    updateViewport();
    root.querySelector('.target-count').textContent = data.targets.length ? `${data.targets.length} Views` : '';
    root.querySelector('.target-empty').hidden = !!data.targets.length;

    function tick() {
        tickHandle = null;
        if (disposed) return;
        const seconds = masterTime(), playing = isPlaying() && !document.hidden;
        const hidePlay = playing || !!maximized || document.hidden || root.dataset.ready !== 'true';
        if (playButton.hidden !== hidePlay) playButton.hidden = hidePlay;
        root.dataset.time = seconds.toFixed(4);
        for (const item of media) {
            const visible = !document.hidden && (item === maximized || (!maximized && item.visible));
            if (!visible) { item.playback.pause(); continue; }
            if (!item.video.getAttribute('src')) continue;
            const clock = item === maximized && enlargedPlayback.ready ? null : seconds;
            const ready = item.playback.sync(clock, playing);
            if (ready && item === maximized) enlargedPlayback.ready = true;
        }
        if (overlay && source && (!maximized || maximized === source)) overlay.draw(source.presentedTime ?? source.video.currentTime);
    }

    return {
        async connect(viewer, signal) {
            scene = viewer;
            stopFrames = scene.onFrame(requestTick);
            updateViewport();
            await Promise.all(media.filter(item => item.visible).map(prepareVideo));
            signal.throwIfAborted();
            connected = true;
            scene.playing = true;
            updateViewport();
            requestTick();
        },
        async loadOverlay(signal) {
            if (data.overlay && source) overlay = await createOverlay(source.content, data.overlay, data.fps, signal);
            requestTick();
        },
        dispose() {
            if (disposed) return;
            disposed = true;
            stopFrames?.();
            cancelAnimationFrame(tickHandle);
            cancelAnimationFrame(viewportHandle);
            listeners.abort();
            sizes.disconnect();
            for (const item of media) {
                if (item.frameCallback) item.video.cancelVideoFrameCallback(item.frameCallback);
                releaseVideo(item);
            }
            cache.dispose();
            overlay?.dispose();
            sourceHost.replaceChildren();
            sourceHost.hidden = true;
            grid.replaceChildren();
            enlarged.querySelector('.enlarged-content').replaceChildren();
            enlarged.hidden = true;
        }
    };
}

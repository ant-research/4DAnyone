// Gradio boundary: replace recordings, serialize camera deltas and own teardown.
const root = element.querySelector('.space-display');
const loading = root.querySelector('.scene-loading');
const note = root.querySelector('.display-note');
const modules = Promise.all(['scene', 'media'].map(key => import(new URL(props.assets[key], document.baseURI).href)));
let scene, media, revision = 0, disposed = false;
let abort = new AbortController(), queue = Promise.resolve();

function showNote(message) {
    note.textContent = message || '';
    note.hidden = !message;
}
function setLoading(message = 'Loading Scene', failed = false) {
    loading.querySelector('.scene-loading-text').textContent = message;
    loading.classList.toggle('failed', failed);
    loading.setAttribute('aria-busy', String(!failed));
    loading.hidden = false;
    root.querySelector('.scene-play').hidden = true;
    root.dataset.ready = 'false';
}
function clear() {
    media?.dispose(); scene?.dispose();
    media = scene = null;
}
async function load(data, token, signal) {
    if (token !== revision || disposed) return;
    if (data?.layout_only) {
        if (!scene) throw new Error('Reload The Page To Restore The Camera Preview');
        await scene.append(data, signal);
        root.dataset.cameraCount = String(data.camera_count);
        return;
    }
    clear();
    if (!data) { setLoading('Preparing Preview'); return; }
    const [{openScene}, {createMediaView}] = await modules;
    signal.throwIfAborted();
    showNote(data.notes.join(' '));
    media = createMediaView(root, data, showNote);
    const overlay = media.loadOverlay(signal).catch(error => {
        if (!signal.aborted) showNote(`Source Overlay Unavailable: ${error.message}`);
    });
    scene = await openScene(root.querySelector('.rerun-canvas'), props.assets.wasm, data, signal);
    if (token !== revision || disposed) { clear(); return; }
    await media.connect(scene, signal);
    if (token !== revision || disposed) { clear(); return; }
    root.dataset.cameraCount = String(data.camera_count);
    root.dataset.recording = data.recording_id;
    root.dataset.ready = 'true';
    loading.hidden = true;
    await overlay;
}
function update() {
    const data = props.value;
    // Camera edits retain the current recording; a new scene cancels old work.
    if (!data?.layout_only) {
        revision++;
        abort.abort(); abort = new AbortController();
        setLoading();
    }
    const token = revision, signal = abort.signal;
    queue = queue.catch(() => {}).then(() => load(data, token, signal)).catch(error => {
        if (signal.aborted || token !== revision || disposed) return;
        clear();
        console.error('4DAnyone display:', error);
        setLoading('Cannot Open Scene', true); showNote(error.message);
    });
}
function dispose() {
    if (disposed) return;
    disposed = true; revision++;
    abort.abort(); removal.disconnect();
    clear();
    window.removeEventListener('pagehide', dispose);
}
const removal = new MutationObserver(() => { if (!root.isConnected) dispose(); });
removal.observe(document.body, {childList: true, subtree: true});
window.addEventListener('pagehide', dispose);
watch('value', update);
update();

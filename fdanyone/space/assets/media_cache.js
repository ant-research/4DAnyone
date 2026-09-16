// Large RRD/WASM files exceed some browsers' normal HTTP cache entry limits.
// Keep a bounded, per-origin cache; URL revisions identify immutable previews.
const CACHE_NAME = '4danyone-space-media-v1';
const MAX_BYTES = 256 * 1024 * 1024;
const VIDEO_CACHE_NAME = '4danyone-space-videos-v1';
const VIDEO_MAX_BYTES = 128 * 1024 * 1024;
let pruning = Promise.resolve();

export async function fetchBytes(url, signal) {
    const response = await fetchCached(url, {signal});
    if (!response.ok) throw new Error(`Cannot Load Media (${response.status})`);
    return response.arrayBuffer();
}

async function trim(cache, maximum) {
    const keys = await cache.keys();
    const runtime = [...keys].reverse().find(key => new URL(key.url).pathname.endsWith('.wasm'))?.url;
    const sizes = await Promise.all(keys.map(async key => Number((await cache.match(key))?.headers.get('content-length')) || 0));
    let total = sizes.reduce((sum, bytes) => sum + bytes, 0);
    for (let index = 0; total > maximum && index < keys.length; index++) {
        // Retain the shared runtime when replacing older scene previews.
        if (keys[index].url === runtime) continue;
        await cache.delete(keys[index]);
        total -= sizes[index];
    }
}

export async function fetchCached(url, options = {}) {
    options.signal?.throwIfAborted();
    const address = new URL(url, document.baseURI).href;
    const video = new URL(address).pathname.endsWith('.mp4');
    const maximum = video ? VIDEO_MAX_BYTES : MAX_BYTES;
    let cache;
    try {
        cache = await globalThis.caches?.open(video ? VIDEO_CACHE_NAME : CACHE_NAME);
        const hit = await cache?.match(address);
        options.signal?.throwIfAborted();
        if (hit) return hit;
    } catch (error) {
        if (options.signal?.aborted) throw error;
        // Storage restrictions must not prevent playback.
    }
    const response = await fetch(address, options);
    const size = Number(response.headers.get('content-length'));
    if (cache && response.status === 200 && size > 0 && size <= maximum) {
        // Read the network response and store its clone concurrently, so WASM
        // compilation can still stream while the download is in progress.
        cache.put(address, response.clone()).then(() => {
            pruning = pruning.catch(() => {}).then(() => trim(cache, maximum));
            return pruning;
        }).catch(() => {});
    }
    return response;
}

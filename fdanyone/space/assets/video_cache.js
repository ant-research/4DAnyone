import {fetchCached} from './media_cache.js';

// Keep compressed media across scrolls; only visible cards own native decoders.
export function createVideoCache({maxBytes = 64 * 1024 * 1024, concurrency = 3} = {}) {
    const entries = new Map();
    let warm = new Set(), active = 0, sequence = 0, disposed = false;
    function remove(entry) {
        entries.delete(entry.address);
        entry.abort.abort();
        if (entry.url) URL.revokeObjectURL(entry.url);
        if (entry.state === 'queued') entry.reject(new DOMException('Media released', 'AbortError'));
    }
    function trim() {
        let bytes = [...entries.values()].reduce((sum, entry) => sum + entry.bytes, 0);
        const unused = [...entries.values()].filter(entry => !entry.users && entry.state === 'ready')
            .sort((a, b) => Number(warm.has(a.address)) - Number(warm.has(b.address)) || a.used - b.used);
        for (const entry of unused) {
            if (bytes <= maxBytes) break;
            bytes -= entry.bytes;
            remove(entry);
        }
    }
    async function load(entry) {
        active++;
        entry.state = 'loading';
        try {
            const response = await fetchCached(entry.address, {signal: entry.abort.signal});
            if (!response.ok) throw new Error(`Cannot Load Video (${response.status})`);
            const blob = await response.blob();
            entry.abort.signal.throwIfAborted();
            entry.url = URL.createObjectURL(blob);
            entry.bytes = blob.size;
            entry.state = 'ready';
            entry.resolve(entry.url);
            trim();
        } catch (error) {
            if (entries.get(entry.address) === entry) entries.delete(entry.address);
            entry.reject(error);
        } finally {
            active--;
            pump();
        }
    }
    function pump() {
        if (disposed) return;
        const queue = [...entries.values()].filter(entry => entry.state === 'queued')
            .sort((a, b) => b.priority - a.priority || a.used - b.used);
        while (active < concurrency && queue.length) void load(queue.shift());
    }
    function ensure(address, priority) {
        if (disposed) throw new Error('Video Cache Is Closed');
        let entry = entries.get(address);
        if (!entry) {
            let resolve, reject;
            const ready = new Promise((yes, no) => { resolve = yes; reject = no; });
            ready.catch(() => {}); // Consumers still receive the original rejection.
            entry = {address, ready, resolve, reject, abort: new AbortController(),
                users: 0, bytes: 0, url: null, state: 'queued', priority, used: ++sequence};
            entries.set(address, entry);
        }
        entry.priority = Math.max(entry.priority, priority);
        entry.used = ++sequence;
        return entry;
    }
    return {
        acquire(address) {
            const entry = ensure(address, 1);
            entry.users++;
            pump();
            let released = false;
            return {
                ready: entry.ready,
                release() {
                    if (released) return;
                    released = true;
                    entry.users--;
                    if (!entry.users && !warm.has(address) && entry.state !== 'ready') remove(entry);
                    trim();
                }
            };
        },
        prefetch(addresses) {
            const previous = warm;
            warm = new Set(addresses);
            for (const entry of entries.values()) {
                if (!entry.users && !warm.has(entry.address) && entry.state !== 'ready') remove(entry);
            }
            // Do not repeatedly reload nearby clips evicted by the byte budget.
            for (const address of addresses) if (!previous.has(address) || entries.has(address)) ensure(address, 0);
            trim();
            pump();
        },
        dispose() {
            disposed = true;
            for (const entry of entries.values()) remove(entry);
            warm.clear();
        }
    };
}

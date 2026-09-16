const root = element.querySelector('.run-monitor');
const stages = [...root.querySelectorAll('.run-stage')];
const detail = root.querySelector('.run-step');
const elapsed = root.querySelector('.run-elapsed');
const consolePanel = root.querySelector('.run-console');
const log = root.querySelector('.console-log');
const toggle = root.querySelector('.console-toggle');
const followButton = root.querySelector('.console-follow');
const runName = root.querySelector('.console-run');
let token, follow = true, expanded = true, latest = '', drawn = '', placeholder = '';

function drawLog() {
    const text = latest || placeholder;
    if (!follow || !expanded || text === drawn) return;
    log.textContent = text;
    drawn = text;
    log.scrollTop = log.scrollHeight;
}
function setExpanded(value) {
    expanded = value;
    consolePanel.dataset.expanded = String(value);
    toggle.setAttribute('aria-expanded', String(value));
    toggle.querySelector('span').textContent = value ? '▾' : '▸';
    if (value) drawLog();
}
toggle.addEventListener('click', () => setExpanded(!expanded));
log.addEventListener('scroll', () => {
    if (!expanded) return;
    follow = log.scrollHeight - log.scrollTop - log.clientHeight < 24;
    followButton.hidden = follow;
    if (follow) drawLog();
});
followButton.addEventListener('click', () => {
    follow = true;
    followButton.hidden = true;
    drawLog();
    log.scrollTop = log.scrollHeight;
});

function render() {
    const value = props.value;
    root.hidden = !value;
    if (!value) {
        token = undefined;
        latest = drawn = '';
        return;
    }
    const active = ['starting', 'queued', 'running'].includes(value.state);
    placeholder = active ? 'Waiting For Console Output…' : 'No Console Output';
    if (token !== value.token) {
        const submitting = token === 'preparing' && active;
        token = value.token;
        latest = '';
        follow = true;
        drawn = null;
        followButton.hidden = true;
        if (!submitting) setExpanded(active);
    }
    root.dataset.state = value.state;
    stages.forEach((stage, index) => {
        const done = index < value.stage || value.state === 'complete';
        const current = index === value.stage && !done;
        stage.dataset.state = done ? 'complete' : current ? value.state : 'pending';
        stage.querySelector('.stage-icon').textContent = done ? '✓' : value.state === 'failed' && current ? '!' : String(index + 1);
        stage.querySelector('.stage-fill').style.width = `${Math.round(value.progress[index] * 100)}%`;
        const bar = stage.querySelector('[role="progressbar"]');
        bar.setAttribute('aria-valuenow', String(Math.round(value.progress[index] * 100)));
        bar.setAttribute('aria-valuetext', done ? 'Complete' : current ? value.detail : 'Waiting');
    });
    detail.textContent = value.detail;
    if (value.elapsed == null) elapsed.textContent = '';
    else {
        const seconds = Math.floor(value.elapsed);
        elapsed.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    }
    elapsed.title = 'Elapsed Time';
    runName.textContent = value.name;
    runName.title = value.name ? `Run ${value.name}` : '';
    if (typeof value.log === 'string') latest = value.log;
    drawLog();
}
watch('value', render);
render();

const root = element.querySelector('.inline-slider');
const range = root.querySelector('input');
const output = root.querySelector('output');
root.querySelector('.slider-label').innerHTML = props.label_html;
range.id = props.input_id;
function choices() { return Array.isArray(props.counts) && props.counts.length ? props.counts : null; }
function publishViewCount() {
  element.closest('#settings-grid')?.querySelector('.pitches-control')?.dispatchEvent(
    new CustomEvent('view-count', {detail: props.value, bubbles: true})
  );
}
function update() {
  const counts = choices();
  const minimum = counts ? 0 : Number(props.minimum);
  const maximum = counts ? counts.length - 1 : Number(props.maximum);
  const value = Number(props.value ?? minimum);
  const position = counts ? Math.max(0, counts.indexOf(value)) : value;
  range.min = minimum; range.max = maximum; range.step = counts ? 1 : props.step;
  range.value = position;
  range.disabled = props.interactive === false || maximum <= minimum;
  const text = value.toLocaleString('en-US', {
    minimumFractionDigits: props.minimum_decimals ?? 0,
    maximumFractionDigits: props.precision ?? 0,
    useGrouping: false,
  }) + (props.suffix || '');
  range.setAttribute('aria-label', props.label);
  range.setAttribute('aria-valuetext', text);
  output.textContent = text;
  const fraction = maximum > minimum ? Math.max(0, Math.min(1, (position - minimum) / (maximum - minimum))) : 0;
  root.style.setProperty('--range-progress', `${fraction * 100}%`);
  root.style.setProperty('--tick-count', counts?.length || 0);
  root.classList.toggle('discrete', !!counts);
  root.classList.toggle('disabled', range.disabled);
}
element.addEventListener('view-counts', event => {
  const counts = event.detail;
  const current = Number(props.value);
  props.counts = counts;
  props.value = counts.reduce((best, value) => Math.abs(value - current) < Math.abs(best - current) ? value : best);
  update();
  publishViewCount();
});
range.addEventListener('input', () => {
  if (range.disabled) return;
  const counts = choices();
  props.value = counts ? counts[Number(range.value)] : Number(range.value);
  update();
  if (counts) {
    publishViewCount();
  }
  if (!props.commit_on_change) trigger('input');
});
range.addEventListener('change', () => {
  if (!range.disabled && props.commit_on_change) trigger('input');
});
watch(['value', 'minimum', 'maximum', 'step', 'precision', 'minimum_decimals', 'suffix', 'counts', 'interactive'], update);
update();

const fields = element.querySelector('.pitch-fields');
const row = element.querySelector('.layer-count');
const count = row.querySelector('input');
let dirty = false;

function update() {
  const pitches = props.value;
  count.value = pitches.length;
  count.max = props.max_layers;
  count.disabled = props.interactive === false;
  count.setAttribute('aria-valuetext', String(pitches.length));
  row.querySelector('output').textContent = pitches.length;
  row.style.setProperty('--range-progress', `${(Number(count.value) - 1) / (props.max_layers - 1) * 100}%`);
  row.style.setProperty('--tick-count', props.max_layers);
  row.classList.toggle('disabled', count.disabled);
  fields.style.setProperty('--pitch-columns', pitches.length);
  while (fields.children.length > pitches.length) fields.lastElementChild.remove();
  pitches.forEach((value, i) => {
    if (!fields.children[i]) {
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'number'; input.step = 1; input.required = true;
      input.dataset.pitch = i;
      input.setAttribute('aria-label', `Pitch ${i + 1} In Degrees`);
      label.append(input);
      fields.append(label);
    }
    const input = fields.children[i].querySelector('input');
    input.min = props.min_pitch; input.max = props.max_pitch;
    input.title = `Layer ${i + 1} · ${props.min_pitch}° To ${props.max_pitch}°`;
    if (document.activeElement !== input) input.value = value ?? '';
    input.style.width = `${Math.max(1, input.value.length)}ch`;
    input.disabled = count.disabled;
    input.setCustomValidity(pitches.some((other, index) => index !== i && other === value)
      ? 'Use a different angle for each layer.' : '');
  });
  if (count.disabled) dirty = false;
  const total = element.closest('#settings-grid')?.querySelector('.camera-view-count');
  if (total) total.textContent = `${pitches.length * props.views} views in total`;
}

function changeCount() {
  if (count.disabled || !Number.isFinite(count.valueAsNumber)) return;
  const layers = Math.max(1, Math.min(props.max_layers, Math.round(count.valueAsNumber)));
  if (layers === props.value.length) return;
  dirty = false;
  props.value = [...props.pitch_presets[layers - 1]];
  update();
  // Both controls must be current before Gradio snapshots the layout.
  element.closest('#settings-grid')?.querySelector('#camera-views .inline-slider')?.dispatchEvent(
    new CustomEvent('view-counts', {detail: props.view_counts[layers], bubbles: true})
  );
  trigger('input');
}

function commit() {
  if (!dirty || props.interactive === false) return;
  dirty = false;
  if (!fields.querySelector('input:invalid')) props.value = [...props.value].sort((a, b) => b - a);
  update();
  trigger('input');
}

count.addEventListener('input', changeCount);
fields.addEventListener('input', event => {
  const input = event.target;
  if (input.dataset.pitch === undefined || props.interactive === false) return;
  const pitches = [...props.value];
  pitches[Number(input.dataset.pitch)] = Number.isFinite(input.valueAsNumber) ? input.valueAsNumber : null;
  dirty = true;
  props.value = pitches;
  update();
});
fields.addEventListener('focusout', event => {
  if (!fields.contains(event.relatedTarget)) commit();
});
fields.addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); event.target.blur(); }
});
element.addEventListener('view-count', event => {
  props.views = Number(event.detail);
  update();
});
watch(['value', 'min_pitch', 'max_pitch', 'max_layers', 'views', 'interactive'], update);
update();

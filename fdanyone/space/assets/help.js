const sidebar = element.closest('#space-sidebar');
sidebar.addEventListener('beforetoggle', event => {
  const card = event.target;
  if (!card.matches('.option-help') || event.newState !== 'open') return;
  const anchor = sidebar.querySelector(`.help-button[popovertarget="${card.id}"]`);
  const box = anchor.getBoundingClientRect();
  const width = Math.min(320, window.innerWidth - 24);
  card.style.visibility = 'hidden';
  card.style.width = `${width}px`;
  card.style.left = `${Math.max(12, Math.min(box.left - width - 12, window.innerWidth - width - 12))}px`;
  card.style.top = `${Math.max(12, box.top)}px`;
}, true);
sidebar.addEventListener('toggle', event => {
  const card = event.target;
  if (!card.matches('.option-help')) return;
  const anchor = sidebar.querySelector(`.help-button[popovertarget="${card.id}"]`);
  anchor?.setAttribute('aria-expanded', String(event.newState === 'open'));
  if (event.newState === 'open') {
    const box = card.getBoundingClientRect();
    card.style.top = `${Math.max(12, Math.min(box.top, window.innerHeight - box.height - 12))}px`;
    card.style.visibility = 'visible';
  }
}, true);
sidebar.addEventListener('keydown', event => {
  const card = sidebar.querySelector('.option-help:popover-open');
  if (!card) return;
  // Description shortcuts must not reach the scene's keyboard controls.
  event.stopPropagation();
  if (event.key === 'Escape') {
    event.preventDefault();
    card.hidePopover();
    sidebar.querySelector(`.help-button[popovertarget="${card.id}"]`)?.focus();
  }
});
for (const type of ['wheel', 'touchmove']) {
  sidebar.addEventListener(type, event => {
    if (!event.target.closest('.option-help')) {
      sidebar.querySelector('.option-help:popover-open')?.hidePopover();
    }
  }, {capture: true, passive: true});
}

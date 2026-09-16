const button = element.querySelector('.delete-output');
const dialog = element.querySelector('dialog');
dialog.addEventListener('keydown', event => event.stopPropagation());
function update() {
  dialog.close();
  button.disabled = !props.value;
  dialog.querySelector('.delete-path').textContent = props.value?.output || '';
}
button.addEventListener('click', () => dialog.showModal());
dialog.querySelector('.keep-output').addEventListener('click', () => dialog.close());
dialog.querySelector('.confirm-delete').addEventListener('click', () => {
  dialog.close();
  button.disabled = true;
  trigger('click');
});
watch('value', update);
update();

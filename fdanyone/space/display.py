"""One Rerun scene and a synchronized, independently scrollable media surface."""

from pathlib import Path

DISPLAY_HTML = """
<div class="space-display" aria-label="Scene And Videos">
  <div class="scene-stage">
    <div class="rerun-canvas" aria-label="Rerun Scene"></div>
    <button class="scene-play" type="button" aria-label="Play" aria-keyshortcuts="Space" title="Play (Space)" hidden>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
    </button>
    <div class="source-preview" hidden></div>
    <div class="scene-loading" role="status" aria-busy="true">
      <span class="scene-spinner" aria-hidden="true"></span><span class="scene-loading-text">Loading Scene</span>
    </div>
  </div>
  <section class="target-panel" aria-label="Target Videos">
    <div class="media-heading"><span>Target Videos</span><span class="target-count"></span></div>
    <div class="target-scroll"><div class="target-grid"></div><div class="target-empty">No Results Yet</div></div>
  </section>
  <div class="media-enlarged" hidden>
    <div class="media-heading"><span class="enlarged-title"></span>
      <button type="button" class="media-back">Back</button></div>
    <div class="enlarged-content"></div>
  </div>
  <div class="display-note" role="status" hidden></div>
</div>
"""

DISPLAY_JS = Path(__file__).with_name("assets").joinpath("display.js").read_text()

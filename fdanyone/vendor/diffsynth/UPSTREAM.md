# DiffSynth-Studio provenance

This directory is a deliberately small inference-only extract from [modelscope/DiffSynth-Studio](https://github.com/modelscope/DiffSynth-Studio), licensed under Apache-2.0.

- Public base revision: `04e39f7de53df7276a7b40ca1791c2a393e05ff3`
- Research fork revision used by the original experiment: `c00782d90c872c97bda4745a9e6a41a0a4a7c4db`
- `UPSTREAM.patch` SHA-256: `178e6035e451f94a2122fa4d2c876a488546964768b90275549cbf609f97daba`
- Extracted: 2026-07-16

The research fork revision was not anonymously reachable when the release contract was audited. `UPSTREAM.patch` therefore records the exact binary-safe diff from the public base to the research revision for the Wan/SpaTem/scheduler sources from which the reader graph was derived. Unrelated research-fork changes are deliberately excluded. `VENDORED_FILES.txt` is the reviewable final runtime manifest.

4DAnyone subsequently reduced the generic Wan implementation to the one checkpoint-key-compatible reader graph: video attention, MVS attention in every block, ViewPack source tokens, fixed prompt context, and precomputed RGB-pose features. Registry, downloader, text encoder/tokenizer, generic pipeline, training adapters, camera/control modules, VRAM wrappers, and alternate schedulers are not part of the reader closure. The retained automatic attention fallback remains observable in run metadata.

The reader inference path bounds the temporary FP64 RoPE workspace and reuses PoseEncoder/FFN activation storage when gradients are disabled. These release-specific memory-lifetime changes preserve checkpoint parameter keys and the full-group attention and FFN matrix-multiplication shapes. The offline UMT5 conversion implementation used to generate the frozen prompt asset is development-only and not part of the reader distribution; it retains this license and provenance.

To reproduce the retained research sources before pruning:

```bash
git clone https://github.com/modelscope/DiffSynth-Studio.git
git -C DiffSynth-Studio checkout 04e39f7de53df7276a7b40ca1791c2a393e05ff3
git -C DiffSynth-Studio apply --check /path/to/UPSTREAM.patch
git -C DiffSynth-Studio apply /path/to/UPSTREAM.patch
```

The patch contains research-code additions and is itself source code. It must remain covered by this directory's Apache-2.0 `LICENSE` and attribution.

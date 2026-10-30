# PerceptualTAA-V2

How do Temporal Anti-Aliasing (TAA) settings affect perceived video quality, and does the best setting depend on resolution and scene content?

Scenes are rendered in Unreal Engine 5.6 over a full grid of TAA settings and resolutions. Each render is scored against a 16× supersampled reference with the CGVQM video quality metric. The results are then analysed per patch (¼ × ¼ of the frame, over 30 frames) against content features (motion, detail, newly visible pixels) and artifact measures (flicker, detail loss).

This is the revision of our HPG submission. The submitted version is tagged `hpg-submission` in the old repository.

---

## Repository layout

```
PerceptualTAA-V2/
  pipeline/                 all scripts (run order below)
  src/cgvqm/                CGVQM metric: git submodule of IntelLabs/CGVQM (code + weights)
  results/                  small outputs, synced from the data folder and committed
  notes/                    decisions, render log, reviewer-response tracking
  requirements.txt
```

**Videos and frames are not in this repo.** They live in a data folder on the render machine, or on the external SSD (see [Data](#data)).

### What's saved in the repo, and how it gets there

| In the repo | Not in the repo (stays in the data folder) |
|---|---|
| `pipeline/`, `src/cgvqm/`, README, notes | videos, PNG / EXR frames |
| `results/<scene>/manifest.json` | `.npz` files (per-patch scores, caches) |
| `results/<scene>/scores/cgvqm.json` (+ `cvvdp.json`) | `visuals/` (images / videos from the visualizers) |
| `results/<scene>/features/content.csv`, `content_frames.csv`, `patch_table.csv` | `dashboard.html` (rebuild it any time) |
| `results/scores_all.csv` | |
| `results/v1_hpg/`: the HPG (v1) scores, archived, kept separate | |

About 2 MB per scene. **`score_taa.py` and `compute_features.py` copy their results into `results/` automatically** when they finish, as long as they're run from this repo's `pipeline/` folder. Only run `pipeline/sync_results.py` by hand if you used `--no-sync`, or for data scored before auto-sync existed.

**Routine:**
- **Render PC, after a session:** `git add results && git commit -m "Results: <what changed>" && git push`
- **Any other computer:** `git pull`, then `python pipeline/build_dashboard.py --root results`

`results/v1_hpg/` holds the v1 pipeline's scores: one parameter at a time, no warm-up, a different reference setup. Use it for comparison only; don't merge it with v2.

---

## Setup on a new computer

Clone **with the submodule** (CGVQM lives in `src/cgvqm`):

```
git clone --recurse-submodules https://github.com/mariabeatrizsilva/PerceptualTAA-V2.git
```

Already cloned without it? From inside the repo: `git submodule update --init`.
Check: `src/cgvqm/weights/` should contain `cgvqm-2.pickle` and `cgvqm-5.pickle`.

Install the Python packages (Python 3.11+):

```
pip install -r requirements.txt
```

- **GPU machine:** install the CUDA build of PyTorch first ([pytorch.org](https://pytorch.org/get-started/locally/)), then the rest.
- **FFmpeg** must be installed and on `PATH` (used for encoding and decoding).
- **Render machine only:** Unreal Engine 5.6 with the Movie Render Queue and Python Editor Script plugins enabled.

**Analysis only** (e.g. a laptop without the videos): you just need `pandas numpy plotly`, then `git pull` and build the dashboard from `results/` (see step 8).

---

## Data

Renders go to `OUTPUT_ROOT`, set at the top of `pipeline/generate_taa_jobs.py` (currently `~/Documents/PerceptualTAA/data_v2`). Every other script takes the same folder as `--root` / `--data`.

```
data_v2/
  scores_all.csv                            all scores, one row per render × reference × metric
  <scene>/
    manifest.json                           every job and its exact settings (scripts read this, not folder names)
    videos/reference/ssaa16_sp100.mkv       16× SSAA reference, 100% resolution  <- keep a copy on every computer
    videos/taa/<config>.mkv                 one lossless video per render
    aux/motion_depth/                       (optional) engine motion vectors + depth, EXR
    scores/cgvqm.json                       score, per-frame error, flags per render
    scores/cgvqm_emaps/*.npz                per-patch CGVQM scores (5 clips × 4 × 4) + coarse error map
    features/                               content.csv, content_frames.csv, artifacts.csv, patch_table.csv
    visuals/                                images and videos from the visualizers
```

**Config names** contain every TAA parameter, in a fixed order and at fixed width, e.g.
`sp050_aw0.040_hp100_ns08_fs1.00` = screen percentage 50, alpha weight 0.04, history 100%, 8 samples, filter size 1.0.

**Videos** are lossless RGB H.264 (`libx264rgb -qp 0`): bit-identical to the rendered PNGs, about half the size. Most players can't play them; use VLC or mpv.

**Backups:** keep at least two copies of `data_v2`, one in a different place. The reference videos are small (~0.3 GB per scene) and are all the content analysis needs, so keep them on every computer.

---

## Pipeline: run order

All commands are run from the repo root. `ROOT` = your data folder.

| # | Step | Where | Command |
|---|---|---|---|
| 1 | Queue renders | Unreal (Python console) | run `pipeline/generate_taa_jobs.py` |
| 2 | Render | Unreal | Movie Render Queue → Render (Remote) |
| 3 | Encode + verify | render PC | `python pipeline/encode_and_verify.py --root ROOT --all --delete-pngs` |
| 4 | Score | GPU machine | `python pipeline/score_taa.py --root ROOT --all` |
| 5 | Features | any machine with the videos | `python pipeline/compute_features.py --root ROOT --all` |
| 6 | Look at it | any machine with the videos | `scene_content_view.py`, `visualize_artifacts.py` |
| 7 | Commit results | machine with the data | automatic copy into `results/` after steps 4–5; then `git add results`, commit, push |
| 8 | Dashboard | anywhere | `python pipeline/build_dashboard.py --root results` → open `results/dashboard.html` |

Every step is **resumable**: re-running it skips work that's already done.

### 1–2 · Render (`generate_taa_jobs.py`)
- Edit `SCENES` (and `SWEEP` if needed) at the top. Each scene names its Unreal project. The script only queues scenes belonging to the project that's open, so run it once per project.
- It writes `manifest.json` per scene and fills the Movie Render Queue.
- **If Unreal stops partway:** restart the editor and run the script again. It clears the queue and re-queues only missing or half-finished renders. Don't re-render the old queue.

### 3 · Encode + verify (`encode_and_verify.py`)
- Turns each PNG folder into a lossless video, checks every frame is bit-identical, and checks frame counts against the reference.
- `--delete-pngs` frees the space, and only deletes after the video passes the check.
- Safe to run while Unreal is still rendering: folders still being written are skipped.

### 4 · Score (`score_taa.py`)
- CGVQM-2, patch scale 4, mean pooling, 30-frame clips: identical to the paper's settings.
- Strict: renders whose frame count or resolution doesn't match the reference are reported, not scored. Scores outside 0–100 are flagged.
- Options:
  - `--metrics cgvqm cvvdp`: also score with ColorVideoVDP
  - `--only <config> ...`: re-score just those renders
  - `--overwrite`: re-score everything
  - `--old-scores <scene>=<old scores.json>`: compare the legacy check with the old factorial study

### 5 · Features (`compute_features.py`)
Computed on CGVQM's patch grid, so every patch score has matching features.

- **Content**, from the reference only: `motion_mean` (DIS optical flow, px/frame), `disocc_frac` (newly visible pixels), `detail_hf`, `detail_grad`, `contrast`, `luma_mean`, `temporal_change`.
- **Artifacts**, each render vs. the reference:
  - `flicker`: frame-to-frame change of the error, after following the motion
  - `hf_ratio`: fine detail of the render ÷ the reference (< 1 = blur, > 1 = aliasing)
  - `err_mae`, `err_disocc`, `err_nondisocc`
- `features/patch_table.csv` = one row per render × patch, with settings, CGVQM patch score, artifacts and content. This is the main analysis table.

### 6 · Visual checks
- `python pipeline/scene_content_view.py --root ROOT --all`: per scene, `visuals/content_sheet.png` (one row per clip) and `content_view.mp4`. Needs only the reference video.
- `python pipeline/visualize_artifacts.py --root ROOT --scene oldmine --sp 50 --hp 100 --aw 0.04 1.0 --frame 75`: the reference next to renders, with error, flicker and detail maps and per-patch values. Use `--clip 2` to get a video instead.

### 7–8 · Share and analyse
Scoring and feature extraction copy their small outputs into `results/` automatically (see [What's saved](#whats-saved-in-the-repo-and-how-it-gets-there)). Commit and push them, `git pull` on another computer, and build the dashboard. For a manual full re-sync: `python pipeline/sync_results.py --data ROOT`.

Dashboard tabs:
- **Overview:** data checks, outliers, legacy check, patch ↔ score check
- **Scenes:** content per scene and over time
- **Parameters:** quality vs. alpha × history × resolution
- **Trade-offs:** settings vs. flicker and detail
- **Artifacts:** why the quality curve peaks
- **Content:** best alpha, and the effect of a setting change, vs. content
- **Interactions:** alpha × history × resolution × content; held-out gain from content-aware alpha
- **Metrics:** CGVQM vs. CVVDP

---

## Study design (v2)

| | Values |
|---|---|
| Alpha weight (`r.TemporalAACurrentFrameWeight`) | 0.02, 0.04, 0.08, 0.12, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0 |
| History % (`r.TemporalAA.HistoryScreenPercentage`) | 100, 125, 150, 200 |
| Screen % (`r.ScreenPercentage`) | 100, 87, 50 in the pilot (= 100/75/25% of pixels); add 71 (= 50%) in `SWEEP` for the full run |
| Fixed | samples = 8, filter size = 1.0 (UE defaults; negligible effect in the factorial study) |
| Reference | 16× spatial SSAA, no TAA, **always at 100%** screen percentage |
| Output | 1920×1080, 30 fps, 150 frames, 60 warm-up frames (so the TAA history is filled before recording) |
| Metric | CGVQM-2 ([IntelLabs/CGVQM](https://github.com/IntelLabs/CGVQM); commit pinned by the submodule) |

Changes from the HPG version:
- the reference is always at 100% (the old factorial test used 87%)
- warm-up frames before recording
- alpha × history × resolution as a full grid, instead of one parameter at a time
- lossless video instead of lossy H.264
- strict frame-count checks before scoring

Record further design decisions in `notes/`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Oodle "corruption detected" / decompression errors, renders stop | Hardware instability (13th/14th-gen Intel). Update the BIOS (microcode 0x129+), turn off overclocking/XMP. Treat renders made before the fix as provisional. |
| Unreal renders ~40 jobs, then the preview window closes | The render process crashed. Check the newest `Saved/Logs/*.log`, then re-run the generator to resume. |
| "Insufficient storage", renders slow down | Disk nearly full. Run `encode_and_verify.py --delete-pngs`; move `OUTPUT_ROOT` to the external SSD. |
| `No module named src` / `cgvqm is not a package` | Run `git submodule update --init`; keep the scripts in `pipeline/`; `pip install av`. |
| Dashboard Overview shows "Patch ↔ score ⚠" | The patch data doesn't belong to the current scores. Re-score that scene with `--overwrite`, re-run `compute_features.py`, then rebuild. |
| A render is a possible outlier | Check it with `visualize_artifacts.py`. Re-score with `--only`; if the score is unchanged, delete its video and re-render. |

---

## Citation

CGVQM:

```
@article{jindal2025cgvqm,
  title   = {{CGVQM+D}: Computer Graphics Video Quality Metric and Dataset},
  author  = {Jindal, Akshay and Sadaka, Nabil and Thomas, Manu Mathew and Sochenov, Anton and Kaplanyan, Anton},
  journal = {Computer Graphics Forum},
  year    = {2025},
  doi     = {10.1111/cgf.70221}
}
```
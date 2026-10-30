"""
sync_results.py
---------------
Copies the SMALL outputs of the pipeline from the data folder (videos live there)
into the repo's results/ folder, keeping the same layout, so they can be committed
and the dashboard can be built on any computer.

Copied per scene (only if they exist):
  manifest.json
  scores/cgvqm.json, scores/cvvdp.json           scores + per-frame errors
  features/content.csv                           content per patch
  features/content_frames.csv                    content per frame
  features/patch_table.csv                       the analysis table
and at the top level: scores_all.csv
NOT copied: videos, PNG/EXR frames, .npz caches, visuals (they stay in the data folder).

USAGE  (run on the machine that has the data, then commit results/)
  python pipeline/sync_results.py --data ~/Documents/PerceptualTAA/data_v2
  git add results && git commit -m "Results: <what changed>" && git push

On any other computer:
  git pull
  python pipeline/build_dashboard.py --root results
"""

import os
import glob
import shutil
import argparse

PER_SCENE = ["manifest.json", "scores/cgvqm.json", "scores/cvvdp.json",
             "features/content.csv", "features/content_frames.csv", "features/patch_table.csv"]
TOP = ["scores_all.csv"]


def copy_if_newer(src, dst):
    if not os.path.exists(src):
        return 0
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src) and \
            os.path.getsize(dst) == os.path.getsize(src):
        return 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return os.path.getsize(dst)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="data folder, e.g. ~/Documents/PerceptualTAA/data_v2")
    ap.add_argument("--dest", default=os.path.join(os.path.dirname(here), "results"),
                    help="destination (default: <repo>/results)")
    ap.add_argument("--scene", nargs="*", default=None, help="only these scenes (default: all)")
    args = ap.parse_args()

    data, dest = os.path.expanduser(args.data), os.path.expanduser(args.dest)
    scenes = args.scene or sorted(d for d in os.listdir(data)
                                  if os.path.exists(os.path.join(data, d, "manifest.json")))
    total, n = 0, 0
    for rel in TOP:
        b = copy_if_newer(os.path.join(data, rel), os.path.join(dest, rel))
        total += b; n += b > 0
    for s in scenes:
        copied = []
        for rel in PER_SCENE:
            b = copy_if_newer(os.path.join(data, s, rel), os.path.join(dest, s, rel))
            if b:
                copied.append(rel); total += b; n += 1
        print(f"  {s}: {', '.join(copied) if copied else 'up to date'}")
    size = sum(os.path.getsize(f) for f in glob.glob(os.path.join(dest, "**", "*"), recursive=True) if os.path.isfile(f))
    print(f"\nCopied {n} file(s), {total / 1e6:.1f} MB. results/ is now {size / 1e6:.1f} MB in total.")
    print("Next: git add results && git commit -m \"Results: ...\" && git push")


if __name__ == "__main__":
    main()

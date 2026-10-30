"""
check_patches.py
----------------
Checks, render by render, that the three places a CGVQM score lives agree:

  A  scores/cgvqm.json                 the render's score
  B  scores/cgvqm_emaps/*.npz          mean of its 80 per-patch scores (written in the same scoring run as A)
  C  features/patch_table.csv          mean of the patch scores copied in by compute_features.py

With mean pooling, A = B = C (up to rounding). Which pair disagrees tells you where the problem is:
  A != B  -> the .npz and the score come from different scoring runs (or a scorer bug: send the files)
  B != C  -> patch_table.csv is stale: re-run compute_features.py for that scene (no --overwrite needed)

USAGE
  python pipeline/check_patches.py --root <data_v2> --scene lightfoliage
  python pipeline/check_patches.py --root <data_v2> --all
"""

import os
import csv
import json
import argparse
from collections import defaultdict

import numpy as np

MAIN_REF = "ssaa16_sp100"
TOL = 0.05


def check_scene(scene_dir):
    name = os.path.basename(os.path.normpath(scene_dir))
    jpath = os.path.join(scene_dir, "scores", "cgvqm.json")
    if not os.path.exists(jpath):
        print(f"{name}: no scores/cgvqm.json"); return
    scores = {e["config"]: e["score"] for e in json.load(open(jpath)).values()
              if e.get("kind") == "taa" and e.get("ref") == MAIN_REF}

    npz_mean, npz_missing = {}, 0
    for cfg in scores:
        f = os.path.join(scene_dir, "scores", "cgvqm_emaps", f"taa__{cfg}__{MAIN_REF}.npz")
        if os.path.exists(f):
            d = np.load(f)
            if "patch_quality" in d.files:
                npz_mean[cfg] = float(np.mean(d["patch_quality"]))
                continue
        npz_missing += 1

    table = defaultdict(list)
    tpath = os.path.join(scene_dir, "features", "patch_table.csv")
    if os.path.exists(tpath):
        for r in csv.DictReader(open(tpath)):
            if r.get("kind") == "taa" and r.get("cgvqm_patch_quality") not in (None, ""):
                table[r["config"]].append(float(r["cgvqm_patch_quality"]))
    table_mean = {k: float(np.mean(v)) for k, v in table.items()}

    ab = [(c, scores[c], npz_mean[c]) for c in scores if c in npz_mean]
    bc = [(c, npz_mean[c], table_mean[c]) for c in npz_mean if c in table_mean]
    bad_ab = [x for x in ab if abs(x[1] - x[2]) > TOL]
    bad_bc = [x for x in bc if abs(x[1] - x[2]) > TOL]

    print(f"\n=== {name}: {len(scores)} scored renders ===")
    print(f"  A vs B  score vs .npz patch mean     : {len(ab) - len(bad_ab)}/{len(ab)} match"
          + (f"  ({npz_missing} renders have no .npz patch scores)" if npz_missing else ""))
    print(f"  B vs C  .npz vs patch_table.csv mean : {len(bc) - len(bad_bc)}/{len(bc)} match"
          + ("" if os.path.exists(tpath) else "  (no patch_table.csv yet)"))
    for label, bad in (("A vs B", bad_ab), ("B vs C", bad_bc)):
        for c, x, y in bad[:3]:
            print(f"    {label} differs: {c}: {x:.3f} vs {y:.3f}")
    if bad_ab:
        print("  -> A != B: the .npz files don't come from the same scoring run as the scores.\n"
              "     Re-score with --overwrite. If it still differs, send me one .npz and cgvqm.json.")
    elif bad_bc:
        print("  -> B != C: patch_table.csv is out of date. Run compute_features.py for this scene, then rebuild the dashboard.")
    elif ab and bc:
        print("  -> all consistent.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--scene", nargs="+")
    g.add_argument("--all", action="store_true")
    args = ap.parse_args()
    root = os.path.expanduser(args.root)
    scenes = (sorted(d for d in os.listdir(root) if os.path.exists(os.path.join(root, d, "manifest.json")))
              if args.all else args.scene)
    for s in scenes:
        check_scene(os.path.join(root, s))


if __name__ == "__main__":
    main()
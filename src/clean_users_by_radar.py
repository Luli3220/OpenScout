import argparse
import json
import os
import shutil
from typing import Any, Dict, List, Tuple


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_users_list(users: Any) -> Tuple[List[str], bool]:
    if isinstance(users, list) and all(isinstance(u, str) for u in users):
        return users, False
    if isinstance(users, list) and all(isinstance(u, dict) for u in users):
        normalized: List[str] = []
        for u in users:
            login = u.get("login")
            if isinstance(login, str) and login:
                normalized.append(login)
        return normalized, True
    raise ValueError("users_list.json format not supported: expected list[str] or list[dict{login}]")


def mean(values: Any) -> float:
    if not isinstance(values, list) or not values:
        return float("nan")
    numeric: List[float] = []
    for v in values:
        if isinstance(v, (int, float)):
            numeric.append(float(v))
    if not numeric:
        return float("nan")
    return sum(numeric) / len(numeric)


def is_path_within(parent_dir: str, path: str) -> bool:
    parent = os.path.abspath(parent_dir)
    candidate = os.path.abspath(path)
    parent_with_sep = parent if parent.endswith(os.sep) else parent + os.sep
    return candidate == parent or candidate.startswith(parent_with_sep)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--threshold", type=float, default=60.0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--users-list", default=None)
    parser.add_argument("--radar-scores", default=None)
    parser.add_argument("--raw-users-dir", default=None)
    args = parser.parse_args()

    src_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(src_dir)
    data_dir = os.path.join(root_dir, "data")

    users_list_path = args.users_list or os.path.join(data_dir, "users_list.json")
    radar_scores_path = args.radar_scores or os.path.join(data_dir, "radar_scores.json")
    raw_users_dir = args.raw_users_dir or os.path.join(data_dir, "raw_users")

    users_list_raw = load_json(users_list_path)
    users_list, was_dict_list = normalize_users_list(users_list_raw)
    radar_scores: Dict[str, Any] = load_json(radar_scores_path)
    if not isinstance(radar_scores, dict):
        raise ValueError("radar_scores.json format not supported: expected object/dict")

    removed: List[Tuple[str, float]] = []
    kept: List[str] = []
    missing_in_radar: List[str] = []

    for u in users_list:
        if u not in radar_scores:
            kept.append(u)
            missing_in_radar.append(u)
            continue
        avg = mean(radar_scores.get(u))
        if avg != avg:
            kept.append(u)
            continue
        if avg < args.threshold:
            removed.append((u, avg))
        else:
            kept.append(u)

    removed_set = {u for u, _ in removed}
    new_radar_scores = {u: radar_scores[u] for u in radar_scores.keys() if u not in removed_set}

    removed.sort(key=lambda x: x[1])

    print(f"Threshold: {args.threshold}")
    print(f"Users in list: {len(users_list)}")
    print(f"Kept: {len(kept)}")
    print(f"Removed (avg < threshold): {len(removed)}")
    if missing_in_radar:
        print(f"Missing in radar_scores.json (kept as-is): {len(missing_in_radar)}")

    preview_n = min(20, len(removed))
    if preview_n:
        sample = ", ".join([f"{u}({avg:.1f})" for u, avg in removed[:preview_n]])
        print(f"Removed sample (lowest {preview_n}): {sample}")

    if not args.apply:
        print("Dry-run only. Re-run with --apply to write files and delete directories.")
        return 0

    if was_dict_list:
        users_list_out: Any = [{"login": u} for u in kept]
    else:
        users_list_out = kept

    save_json(users_list_path, users_list_out)
    save_json(radar_scores_path, new_radar_scores)

    deleted_dirs = 0
    skipped_dirs = 0
    if os.path.exists(raw_users_dir):
        for u, _avg in removed:
            user_dir = os.path.join(raw_users_dir, u)
            if not is_path_within(raw_users_dir, user_dir):
                skipped_dirs += 1
                continue
            if os.path.isdir(user_dir):
                shutil.rmtree(user_dir)
                deleted_dirs += 1
            else:
                skipped_dirs += 1

    print(f"Updated: {users_list_path}")
    print(f"Updated: {radar_scores_path}")
    print(f"Deleted raw user dirs: {deleted_dirs}")
    if skipped_dirs:
        print(f"Skipped raw user dirs (not found or not directory): {skipped_dirs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


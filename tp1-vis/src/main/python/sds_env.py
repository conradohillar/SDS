"""
Load paths from SDS/.env so scripts work from any working directory.
Looks for .env in the SDS repo root (directory containing .env).
"""
import os


def _find_sds_root():
    """Walk up from cwd and __file__ to find a directory containing .env."""
    candidates = [os.getcwd()]
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    for start in candidates:
        d = os.path.abspath(start)
        for _ in range(10):
            if os.path.isfile(os.path.join(d, ".env")):
                return d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return None


def _load_env():
    root = _find_sds_root()
    if not root:
        return
    env_path = os.path.join(root, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)


def get_tp1_bin_path():
    """TP1 bin directory (static/dynamic/neighbors/benchmark output)."""
    _load_env()
    path = os.environ.get("TP1_BIN_PATH")
    if path:
        return os.path.normpath(path)
    # Fallback: tp1-bin relative to SDS root or cwd
    root = _find_sds_root()
    if root:
        return os.path.normpath(os.path.join(root, "tp1-bin"))
    return os.path.normpath(os.path.join(os.getcwd(), "tp1-bin"))

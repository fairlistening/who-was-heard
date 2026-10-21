"""임베딩 — 공개 모델 기본값, API 키 불필요.

Embeddings with an open multilingual model by default (no API key).
The model is one of the choices that shapes the map; it is printed in the report.
"""
from __future__ import annotations

from typing import List

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


MODEL_INFO = {
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": {
        "size": "1.1 GB", "license": "Apache-2.0", "langs": "50+",
        "url": "https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2"},
}


def default_cache_dir() -> str:
    import os
    return os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface"), "hub")


def cache_dir_hint() -> str:
    """모델을 둘 곳 — WWH_MODEL_DIR(분석 화면에서 고른 곳)이 있으면 그곳, 없으면 허깅페이스 기본 위치."""
    import os
    return os.environ.get("WWH_MODEL_DIR") or default_cache_dir()


def model_path(model: str = DEFAULT_MODEL) -> str:
    import os
    return os.path.join(cache_dir_hint(), "models--" + model.replace("/", "--"))


def model_cached(model: str = DEFAULT_MODEL) -> bool:
    """모델이 이미 이 PC에 내려받아져 있는지. Whether the model is already on this computer."""
    import os
    d = os.path.join(model_path(model), "snapshots")
    if not os.path.isdir(d):
        return False
    with os.scandir(d) as it:
        return any(it)


def model_size(model: str = DEFAULT_MODEL) -> int:
    import os
    seen, tot = set(), 0
    for root, _, files in os.walk(model_path(model)):
        for f in files:
            rp = os.path.realpath(os.path.join(root, f))
            if rp not in seen and os.path.isfile(rp):
                seen.add(rp)
                tot += os.path.getsize(rp)
    return tot


def load_model(model: str = DEFAULT_MODEL, max_tokens: int = 256):
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("임베딩에는 sentence-transformers가 필요합니다: pip install 'who-was-heard[full]'") from e
    import os
    m = SentenceTransformer(model, cache_folder=os.environ.get("WWH_MODEL_DIR") or None)
    m.max_seq_length = max_tokens
    return m


def _key(t, model, max_chars):
    import hashlib
    return hashlib.sha1(f"{model}|{max_chars}|{t[:max_chars]}".encode("utf-8")).hexdigest()


class Stopped(Exception):
    """사용자가 멈춤을 눌렀다. The user pressed stop."""


class VecStore:
    """글 하나에 벡터 하나 — 원문은 저장하지 않고 해시만 키로 쓴다.
    조각(vec_*.npz)으로 나눠 쓰므로 중간에 멈춰도 그때까지 계산한 것은 남는다.
    예전 형식(embeddings.npz, 키마다 배열 하나)도 읽는다.

    One vector per text, keyed by a hash (raw text is never stored). Written in chunks
    so whatever was computed survives a stop or crash. Reads the older single-file format too."""

    def __init__(self, d):
        import os
        import numpy as np
        self.d = d
        os.makedirs(d, exist_ok=True)
        self.v = {}
        for fn in sorted(os.listdir(d)):
            fp = os.path.join(d, fn)
            try:
                if fn.startswith("vec_") and fn.endswith(".npz"):
                    z = np.load(fp)
                    for k, v in zip(z["keys"], z["vecs"]):
                        self.v[str(k)] = v
                elif fn == "embeddings.npz":
                    self.v.update(dict(np.load(fp)))
            except Exception:  # 깨진 조각은 건너뛴다 · skip a broken chunk
                continue

    def absorb(self, path, keys):
        """다른 곳(예전 프로젝트별 캐시)에 있는 벡터 중 필요한 것만 가져와 이 저장소에 남긴다."""
        import os
        import numpy as np
        need = [k for k in keys if k not in self.v]
        if not need or not os.path.exists(path):
            return 0
        try:
            z = np.load(path)
        except Exception:
            return 0
        have = set(z.files)
        got = [k for k in dict.fromkeys(need) if k in have]
        if got:
            self.add(got, [z[k] for k in got])
        return len(got)

    def add(self, keys, vecs):
        import os
        import time
        import numpy as np
        if not len(keys):
            return
        V = np.asarray(vecs, dtype="float32")
        for k, v in zip(keys, V):
            self.v[k] = v
        name = f"vec_{int(time.time() * 1000)}_{os.getpid()}_{len(self.v)}.npz"
        tmp = os.path.join(self.d, name + ".tmp")
        with open(tmp, "wb") as f:
            np.savez(f, keys=np.array(keys), vecs=V)
        os.replace(tmp, os.path.join(self.d, name))


def embed(texts: List[str], model: str = DEFAULT_MODEL, max_chars: int = 400,
          max_tokens: int = 256, batch_size: int = 32, cache_dir: str | None = None,
          also_read=(), progress=None, should_stop=None, chunk: int = 512):
    """cache_dir를 주면 글마다 벡터를 저장해 두고 다시 쓴다(같은 글·모델·길이일 때만).
    also_read: 예전 캐시 파일들 — 필요한 벡터만 cache_dir로 옮겨 온다.
    progress(done, total, reused): 조각마다 불린다. should_stop(): 참이면 멈춘다(계산한 것은 남음).

    With cache_dir, vectors are stored per text and reused later (same text, model and length).
    progress(done, total, reused) is called after every chunk; should_stop() stops between chunks."""
    import numpy as np
    keys = [_key(t, model, max_chars) for t in texts]
    store = VecStore(cache_dir) if cache_dir else None
    if store is not None:
        for pth in also_read or ():
            store.absorb(pth, keys)
        todo = [i for i, k in enumerate(keys) if k not in store.v]
    else:
        todo = list(range(len(texts)))
    # 같은 글은 한 번만 계산 · compute each distinct text once
    first, uniq = {}, []
    for i in todo:
        if keys[i] not in first:
            first[keys[i]] = i
            uniq.append(i)
    total, reused = len(texts), len(texts) - len(todo)
    if progress:
        progress(reused, total, reused)
    out = {} if store is None else store.v
    if uniq:
        m = load_model(model, max_tokens)
        prefix = "query: " if "e5" in model.lower() else ""
        # 길이순으로 묶으면 덧댐(padding)이 줄어 빨라진다 · length-sorted chunks pad less
        uniq.sort(key=lambda i: len(texts[i][:max_chars]))
        done_u = 0
        for a in range(0, len(uniq), chunk):
            if should_stop and should_stop():
                raise Stopped("임베딩을 멈췄습니다 — 계산한 만큼은 저장해 두었습니다 · stopped; computed vectors were kept")
            part = uniq[a:a + chunk]
            E = m.encode([prefix + texts[i][:max_chars] for i in part], batch_size=batch_size,
                         normalize_embeddings=True, show_progress_bar=False)
            ks = [keys[i] for i in part]
            if store is not None:
                store.add(ks, E)
            else:
                out.update(zip(ks, np.asarray(E, dtype="float32")))
            done_u += len(part)
            if progress:
                progress(min(total, reused + round(done_u / len(uniq) * len(todo))), total, reused)
    return np.stack([out[k] for k in keys]).astype("float32")

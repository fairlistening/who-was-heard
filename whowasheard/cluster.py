"""배치·묶기·흔들림.

같은 설정으로 무작위 출발점만 바꿔 여러 번 돌리고, 묶음마다 몇 번 다시 나오는지 센다
(원칙 ② 흔들림을 같이 낸다). 묶음 수는 자료가 정한다 — 상한이 없다(원칙 ⑥).
안 묶인 글은 -1로 남겨 숨기지 않는다(원칙 ①).

묶기는 UMAP으로 5차원까지만 줄인 공간에서 하고(2차원으로 줄이면 버려지는 정보가 너무 많다),
2차원은 지도를 그릴 때만 쓴다. 그래서 지도 위 위치와 묶음 경계가 조금 어긋나 보일 수 있다 — 그게 실제에 더 가깝다.

Clustering happens in a 5-dimensional UMAP space; the 2-D layout is for drawing only.
Layout (UMAP), clustering (HDBSCAN) and stability across random seeds.
The number of clusters is decided by the data — no hidden cap.
Unclustered points stay visible as -1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

import numpy as np


@dataclass
class ClusterParams:
    n_neighbors: int = 15
    min_dist: float = 0.05
    metric: str = "cosine"
    min_cluster_size: int | None = None   # None → max(15, n ÷ 200)
    seeds: Sequence[int] = field(default_factory=lambda: (42, 1, 7, 11, 23))
    same_cluster_jaccard: float = 0.5
    cluster_dims: int = 5            # 묶기에 쓰는 차원 / dimensions used for clustering
    selection: str = "eom"           # HDBSCAN 묶음 고르기: eom(큰 덩어리) · leaf(잘게) / cluster selection

    def resolved_mcs(self, n: int) -> int:
        return self.min_cluster_size or max(15, n // 200)


def _layout(E, p: ClusterParams, seed: int, dims: int = 2):
    import umap  # type: ignore
    return umap.UMAP(n_neighbors=p.n_neighbors, min_dist=(p.min_dist if dims == 2 else 0.0), metric=p.metric,
                     n_components=dims, random_state=seed).fit_transform(E)


def _cluster(xy, mcs: int, selection: str = "eom"):
    import hdbscan  # type: ignore
    # core_dist_n_jobs=1 — 병렬 작업자를 띄우지 않는다. 윈도에서 창 없이(pythonw) 돌 때 작업자 프로세스가
    # 죽는 문제(TerminatedWorkerError)를 피한다. 결과는 같고, 5차원이라 속도 차이도 작다.
    # No worker processes: avoids TerminatedWorkerError on Windows/pythonw. Same result.
    return hdbscan.HDBSCAN(min_cluster_size=mcs, cluster_selection_method=selection,
                           core_dist_n_jobs=1).fit_predict(xy)


def run_many(E, p: ClusterParams | None = None, layout_fn=None, cluster_fn=None):
    """무작위 출발점마다 (seed, xy, labels). 묶기는 cluster_dims 차원에서, xy(2차원)는 첫 판만 그림용으로.
    layout_fn(E, seed, dims) / cluster_fn(Z)은 시험용으로 갈아끼울 수 있다."""
    p = p or ClusterParams()
    layout_fn = layout_fn or (lambda E_, s, d: _layout(E_, p, s, d))
    mcs = p.resolved_mcs(len(E))
    cluster_fn = cluster_fn or (lambda Z: _cluster(Z, mcs, p.selection))
    runs = []
    for i, s in enumerate(p.seeds):
        Z = np.asarray(layout_fn(E, s, p.cluster_dims))
        lab = np.asarray(cluster_fn(Z))
        xy = np.asarray(layout_fn(E, s, 2)) if i == 0 else None
        runs.append((s, xy, lab))
    return runs


def _sets(labels):
    d = {}
    for i, c in enumerate(labels):
        if c >= 0:
            d.setdefault(int(c), set()).add(i)
    return d


def stability(runs, threshold: float = 0.5):
    """첫 판의 묶음마다 '몇 판에서 다시 나왔나'(자기 자신 포함)."""
    base = _sets(runs[0][2])
    others = [_sets(r[2]) for r in runs[1:]]
    app = {}
    for c, s in base.items():
        k = 1
        for o in others:
            if o and max(len(s & t) / len(s | t) for t in o.values()) >= threshold:
                k += 1
        app[c] = k
    return app


def pairwise_ari(runs):
    from sklearn.metrics import adjusted_rand_score as ARI  # type: ignore
    v = [ARI(runs[a][2], runs[b][2]) for a in range(len(runs)) for b in range(a + 1, len(runs))]
    if not v:
        return {"mean": 1.0, "min": 1.0, "max": 1.0}
    return {"mean": round(float(np.mean(v)), 3), "min": round(float(min(v)), 3), "max": round(float(max(v)), 3)}


def run_summary(runs) -> List[dict]:
    out = []
    for s, _, lab in runs:
        k = len(set(lab.tolist())) - (1 if -1 in lab else 0)
        out.append({"seed": int(s), "clusters": int(k), "unclustered_pct": round(float((lab == -1).mean() * 100), 1)})
    return out


def hull(points, keep: float = 0.9):
    """묶음 점의 90%를 감싸는 윤곽(볼록 껍질). 점이 적으면 빈 목록."""
    pts = np.asarray(points)
    if len(pts) < 4:
        return []
    cen = pts.mean(0)
    d = np.linalg.norm(pts - cen, axis=1)
    core = pts[d <= np.quantile(d, keep)]
    try:
        from scipy.spatial import ConvexHull  # type: ignore
        return core[ConvexHull(core).vertices].round(3).tolist()
    except Exception:
        return []

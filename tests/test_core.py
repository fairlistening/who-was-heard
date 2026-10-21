"""알려진 값으로 되돌려 센다. 무거운 모델 없이 돈다 (임베딩·배치·묶기를 가짜로 갈아끼움).

Known-value tests. They run without heavy models: embedding, layout and
clustering are replaced with deterministic stand-ins.
    python -m unittest discover tests
"""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whowasheard.clean import CleanRules, clean  # noqa: E402
from whowasheard.concentration import concentration, gini  # noqa: E402
from whowasheard.cluster import ClusterParams, run_many, stability  # noqa: E402
from whowasheard.report import diagnose, write_reports  # noqa: E402
from whowasheard.reviews import agreement, fleiss_kappa  # noqa: E402
from whowasheard.rules import draft  # noqa: E402
from whowasheard import presets  # noqa: E402

TOPICS = {
    "housing": "rent prices housing supply zoning reform for families in the city",
    "schools": "public schools teachers classroom funding and student reading scores",
    "climate": "flooding heat waves climate adaptation and energy grid upgrades",
}


def corpus(n_per=40):
    rows = []
    for gi, g in enumerate(["North", "South"]):
        for t, base in TOPICS.items():
            for i in range(n_per):
                rows.append({"txt": f"{base} — comment {g} {t} number {i} with some extra words here",
                             "grp": g, "who": f"{g[0]}{i % 7}"})
    rows.append({"txt": "ok", "grp": "North", "who": "N1"})                       # 짧음
    rows.append({"txt": rows[0]["txt"], "grp": "North", "who": "N1"})              # 중복
    rows.append({"txt": "Thank you, I yield back the balance of my time to the chair now.", "grp": "South", "who": "S1"})
    return rows


def fake_embed(texts):
    keys = list(TOPICS)
    E = np.zeros((len(texts), 8), dtype="float32")
    rnd = np.random.default_rng(0)
    for i, t in enumerate(texts):
        k = next((j for j, x in enumerate(keys) if TOPICS[x][:12] in t), 3)
        E[i, k] = 1.0
        E[i] += rnd.normal(0, 0.01, 8)
    return E


def fake_layout(E, seed, dims):
    return E[:, :dims] + np.random.default_rng(seed).normal(0, 0.001, (len(E), dims))


def fake_cluster(Z):
    lab = np.argmax(Z[:, :3], axis=1)
    lab[Z[:, :3].max(1) < 0.5] = -1
    return lab


def run(policy="private", rules=None):
    return diagnose(corpus(), "txt", "grp", "who", rules=rules or CleanRules(min_chars=20), per_group=0,
                    params=ClusterParams(seeds=(42, 1, 7)), embed_fn=fake_embed,
                    layout_fn=fake_layout, cluster_fn=fake_cluster, text_policy=policy, context=("grp",))


class Clean(unittest.TestCase):
    def test_counts(self):
        rules = CleanRules(min_chars=20, exclude_patterns=(r"I yield back",))
        kept, st = clean(corpus(), "txt", "grp", "who", rules)
        self.assertEqual(st["North"]["short"], 1)
        self.assertEqual(st["North"]["dup"], 1)
        self.assertEqual(st["South"]["rule"], 1)
        self.assertEqual(len(kept), 240)


class Concentration(unittest.TestCase):
    def test_values(self):
        c = concentration([{"g": "A", "s": "x"}] * 9 + [{"g": "A", "s": "y"}, {"g": "A", "s": ""}], "g", "s")
        self.assertEqual(c["A"]["speakers"], 2)
        self.assertEqual(c["A"]["blank"], 1)
        self.assertEqual(c["A"]["top10_pct"], 100.0)
        self.assertEqual(gini([1, 1, 1, 1]), 0.0)


class Stability(unittest.TestCase):
    def test_same_every_time(self):
        E = fake_embed([TOPICS[k] for k in TOPICS for _ in range(30)])
        runs = run_many(E, ClusterParams(seeds=(1, 2, 3)), fake_layout, fake_cluster)
        self.assertEqual(set(stability(runs).values()), {3})


class PublicReportHasNoPrivateText(unittest.TestCase):
    """★ 가장 중요한 시험: 원문 비공개 자료는 공개판에 한 문장도 들어가지 않는다."""

    def test_private(self):
        rep = run("private")
        with tempfile.TemporaryDirectory() as d:
            p = write_reports(rep, d, "t")
            pub = open(p["public_html"], encoding="utf-8").read() + open(p["public_json"], encoding="utf-8").read()
            internal = open(p["internal_html"], encoding="utf-8").read()
        for r in corpus():
            if len(r["txt"]) >= 20:
                self.assertNotIn(r["txt"], pub)
        self.assertNotIn("comment North", pub)
        self.assertIn("comment", internal)  # 내부 검토판에는 표본이 있다

    def test_public_policy_has_reps(self):
        rep = run("public")
        self.assertTrue(all(c.get("reps") for c in rep.public["clusters"]))
        self.assertEqual(rep.public["text_policy"], "public")

    def test_no_cap_and_unclustered_kept(self):
        rep = run()
        self.assertEqual(len(rep.public["clusters"]), 3)
        self.assertIn(-1, [p[3] for p in rep.public["points"]] + [-1])


class Reviews(unittest.TestCase):
    def test_kappa_perfect(self):
        self.assertEqual(fleiss_kappa([[2, 0], [0, 2], [2, 0]]), 1.0)

    def test_majority(self):
        rv = [{"reviewer": "A", "exclude": [1, 2], "labels": {"0": "주거"}},
              {"reviewer": "B", "exclude": [1], "labels": {"0": "주거"}},
              {"reviewer": "C", "exclude": [1, 2], "labels": {"0": "집값"}}]
        a = agreement(rv, [0, 1, 2])
        self.assertEqual(a["excluded"], [1, 2])
        self.assertEqual(agreement(rv, [0, 1, 2], "all")["excluded"], [1])
        self.assertEqual(a["labels"]["0"], "주거 / 집값")


class Rules(unittest.TestCase):
    def test_draft(self):
        m = {0: ["I yield back the balance of my time"] * 5, 1: ["housing supply and rent"] * 20}
        c = draft(m, [0])
        self.assertTrue(any("yield back" in x["phrase"] for x in c))

    def test_presets(self):
        for n in presets.available():
            p = presets.load(n)
            self.assertIn(p["text_policy"], ("private", "public"))
            self.assertEqual(len(p["_sha256"]), 12)


class QuotesPolicy(unittest.TestCase):
    def test_quotes_without_authors(self):
        rep = run("quotes")
        pub = json.dumps(rep.public, ensure_ascii=False)
        self.assertTrue(any(c.get("reps") for c in rep.public["clusters"]))   # 원문은 실림
        for c in rep.public["clusters"]:
            self.assertNotIn("top_speakers", c)
            for r in c.get("reps", []):
                self.assertNotIn("speaker", r)                                  # 작성자는 없음
        for who in ("N1", "S3", "N4"):
            self.assertNotIn(f'"{who}"', pub)


if __name__ == "__main__":
    unittest.main()


class EmbedStore(unittest.TestCase):
    """조각 저장·이어 계산·멈춤·예전 캐시 흡수 — 진짜 모델 대신 가짜 모델로."""

    def setUp(self):
        import whowasheard.embed as E
        self.E = E
        self.calls = []
        calls = self.calls

        class Fake:
            def encode(self, xs, **kw):
                calls.append(len(xs))
                return np.array([[len(x), 1.0, 0.0] for x in xs], dtype="float32")
        self._orig = E.load_model
        E.load_model = lambda *a, **k: Fake()

    def tearDown(self):
        self.E.load_model = self._orig

    def test_resume_progress_stop_legacy(self):
        E = self.E
        texts = [f"글 {i} " * (i % 7 + 1) for i in range(50)] + ["같은 글"] * 5
        with tempfile.TemporaryDirectory() as d:
            store = os.path.join(d, "shared")
            # 멈춤: 두 조각 뒤에 멈추면 그만큼은 남는다
            n = {"k": 0}

            def stop():
                n["k"] += 1
                return n["k"] > 2
            with self.assertRaises(E.Stopped):
                E.embed(texts, cache_dir=store, chunk=10, should_stop=stop)
            self.assertEqual(sum(self.calls), 20)
            # 이어서: 남은 것만 계산, 같은 글은 한 번만
            self.calls.clear()
            seen = []
            V = E.embed(texts, cache_dir=store, chunk=10, progress=lambda a, t, r: seen.append((a, t, r)))
            self.assertEqual(sum(self.calls), 51 - 20)
            self.assertEqual(V.shape, (55, 3))
            self.assertGreaterEqual(seen[0][2], 20)
            self.assertEqual(seen[-1][0], 55)
            # 다시: 전혀 계산하지 않음
            self.calls.clear()
            V2 = E.embed(texts, cache_dir=store)
            self.assertEqual(self.calls, [])
            np.testing.assert_allclose(V, V2)
            # 예전 형식 캐시 흡수
            legacy = os.path.join(d, "old.npz")
            np.savez(legacy, **{E._key("옛 글", E.DEFAULT_MODEL, 400): np.array([9, 9, 9], dtype="float32")})
            V3 = E.embed(["옛 글"], cache_dir=store, also_read=[legacy])
            self.assertEqual(self.calls, [])
            self.assertEqual(V3[0].tolist(), [9, 9, 9])
            self.assertIn(E._key("옛 글", E.DEFAULT_MODEL, 400), E.VecStore(store).v)

"""특징어 — 묶음마다 c-TF-IDF로 뽑은 잠정 단어.

이것은 묶음의 이름이 아니다. 이름은 사람이 표본을 읽고 붙인다.
Provisional keywords per cluster (c-TF-IDF). They are NOT cluster names;
a person names clusters after reading samples in the internal report.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List

# 한국어 조사·어미 단순 제거 (형태소 분석기 없이). Crude Korean suffix stripping.
_JOSA = re.compile(r"(으로서|으로써|에서는|에게서|으로|에서|에게|께서|까지|부터|이라는|라는|이라고|라고|하고|이나|이며"
                   r"|입니다|합니다|습니다|했습니다|하셨습니까|하는|하게|해서|하면|되는|되어|된|은|는|이|가|을|를|에|의|와|과|도|만|로|며)$")
_KO = re.compile(r"[가-힣]{2,}")
_EN = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")

STOP_KO = set("""그리고 그러면 그래서 그런데 그러니까 저희 우리 지금 이제 이렇게 그렇게 이런 그런 저런 있습니다 없습니다
생각 정도 부분 문제 관련 다음 이것 그것 저것 여기 거기 하나 사실 정말 그냥 많이 같이 아니 그거 이거
하겠습니다 드리겠습니다 있는 없는 대한 대해서 대해 통해서 통해 그게 이게 때문 경우 이번 지난 오늘 계속 아까 바로 다시
해서 하는데 있고 없고 것은 것이 것을 것입니다 거죠 거예요 거든요 그다음 말씀 있지 있으시면 주시기 바랍니다""".split())
STOP_EN = set("""the and for that this with are was were have has had not but you your they their them our out
from what when which who will would can could there here been being into about than then just also""".split())


def tokens(text: str, extra_stop: Iterable[str] = ()) -> List[str]:
    stop = STOP_KO | set(extra_stop)
    out = []
    for w in _KO.findall(text):
        w2 = _JOSA.sub("", w)
        if len(w2) >= 2 and w2 not in stop and w not in stop:
            out.append(w2)
    for w in _EN.findall(text.lower()):
        if w not in STOP_EN:
            out.append(w)
    return out


def ctfidf(texts: List[str], labels, top: int = 4, min_count: int = 3,
           extra_stop: Iterable[str] = ()) -> Dict[int, List[str]]:
    docs = defaultdict(Counter)
    allc = Counter()
    for t, c in zip(texts, labels):
        if c < 0:
            continue
        tk = tokens(t, extra_stop)
        docs[int(c)].update(tk)
        allc.update(tk)
    if not docs:
        return {}
    avgw = sum(sum(v.values()) for v in docs.values()) / len(docs)
    out = {}
    for c, tf in docs.items():
        tot = sum(tf.values()) or 1
        sc = {w: (n / tot) * math.log(1 + avgw / allc[w]) for w, n in tf.items() if n >= min_count}
        out[c] = [w for w, _ in sorted(sc.items(), key=lambda x: -x[1])[:top]]
    return out

# -*- coding: utf-8 -*-
"""분석 화면(스튜디오)의 뒷단 — CSV 하나로 1차 → 판단 → 규칙 → 2차 … 를 브라우저에서 돌린다.
Back end of the analysis screen: run round 1 → review → rules → round 2 … from the browser.

★ 모든 것이 이 PC 안에서 돈다. 작업 폴더는 기본으로 「문서\\who-was-heard」.
  원문은 이 PC의 브라우저 화면과 작업 폴더에만 있다. 대화(MCP)로는 나가지 않는다.
  All work stays on this computer, in Documents/who-was-heard by default.

작업 폴더 구조 · project layout
  <작업>/<프로젝트>/project.json         설정과 차수 기록
                   input.<csv|xlsx>     올린 자료 (경로로 지정하면 복사하지 않음)
                   rounds/rN_*           차수별 보고서
                   reviews/rN_<채점자>.json
                   rules/rN.json         N차에 쓸 규칙 (rN-draft.json = 도구가 쓴 초안)
                   cache/                임베딩 (다음 차수에 다시 계산하지 않게)
"""
import datetime as _dt
import json
import os
import re
import shutil
import sys
import threading
import time
import traceback
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MAX_UPLOAD = 1024 * 1024 * 1024  # 1GB
_LOCK = threading.Lock()
JOBS = {}
_PLOCKS = {}


def _plock(pid):
    """프로젝트마다 하나 — 보고서를 다시 쓰는 동안 같은 프로젝트의 다른 읽기·쓰기를 기다리게 한다."""
    with _LOCK:
        return _PLOCKS.setdefault(pid, threading.RLock())


# ── 작업 폴더 · workspace ──────────────────────────────────────────────

def work_root():
    if os.environ.get("WWH_WORK"):
        d = os.environ["WWH_WORK"]
    else:
        home = os.environ.get("WWH_TEST_HOME") or os.path.expanduser("~")
        docs = os.path.join(home, "Documents")
        d = os.path.join(docs if os.path.isdir(docs) else home, "who-was-heard")
    os.makedirs(d, exist_ok=True)
    return d


def _slug(name):
    s = re.sub(r"[^\w\-]+", "-", name.strip(), flags=re.UNICODE).strip("-")[:60]
    return s or "project"


def _pdir(pid):
    if not re.fullmatch(r"[\w\-]{1,80}", pid or "", flags=re.UNICODE):
        raise ValueError("bad project id")
    d = os.path.join(work_root(), pid)
    if not os.path.isdir(d):
        raise FileNotFoundError(pid)
    return d


def _load(pid):
    with open(os.path.join(_pdir(pid), "project.json"), encoding="utf-8") as f:
        return json.load(f)


def _save(pid, proj):
    d = _pdir(pid)
    tmp = os.path.join(d, "project.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(proj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(d, "project.json"))


def _input_path(pid, proj):
    i = proj.get("input") or {}
    if not i:
        return None
    return i["path"] if not i.get("copied") else os.path.join(_pdir(pid), i["path"])


def list_projects():
    out = []
    root = work_root()
    for name in sorted(os.listdir(root)):
        pj = os.path.join(root, name, "project.json")
        if os.path.exists(pj):
            try:
                with open(pj, encoding="utf-8") as f:
                    p = json.load(f)
                out.append({"id": name, "name": p.get("name", name), "created": p.get("created"),
                            "rounds": len(p.get("rounds", [])), "input": (p.get("input") or {}).get("filename")})
            except Exception:
                continue
    return {"root": root, "projects": out}


def create_project(name):
    root = work_root()
    base = _slug(name)
    pid, k = base, 2
    while os.path.exists(os.path.join(root, pid)):
        pid, k = f"{base}-{k}", k + 1
    d = os.path.join(root, pid)
    for sub in ("rounds", "reviews", "rules", "cache", "source"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    proj = {"name": name.strip() or pid, "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "input": None, "columns": None, "setup": {}, "rounds": []}
    with open(os.path.join(d, "project.json"), "w", encoding="utf-8") as f:
        json.dump(proj, f, ensure_ascii=False, indent=2)
    return {"id": pid, "project": proj}


def get_project(pid):
    proj = _load(pid)
    d = _pdir(pid)
    rules = sorted(f for f in os.listdir(os.path.join(d, "rules")) if f.endswith(".json"))
    revs = {}
    for f in sorted(os.listdir(os.path.join(d, "reviews"))):
        m = re.fullmatch(r"r(\d+)_(.+)\.json", f)
        if m:
            revs.setdefault(m.group(1), []).append(m.group(2))
    return {"id": pid, "dir": d, "project": proj, "rules_files": rules, "reviews": revs}


# ── 자료 · input ───────────────────────────────────────────────────────

def _columns_info(path):
    from whowasheard.data import columns, load_table
    info = columns(path)
    # 값이 적은 열(집단·구분 열 후보)만 값과 건수를 보여 준다. 글 열의 값은 보여 주지 않는다.
    rows = load_table(path)
    vals = {}
    for c in info["columns"]:
        if info["distinct"][c] <= 40 and info["avg_chars"][c] <= 40:
            cnt = {}
            for r in rows:
                v = str(r.get(c, "")).strip()
                cnt[v] = cnt.get(v, 0) + 1
            vals[c] = sorted(([v, n] for v, n in cnt.items()), key=lambda x: -x[1])
    info["values"] = vals
    return info


def is_nanet_workbook(path):
    """국회도서관 회의록 데이터셋인지 — 시트 몇 개의 앞 몇 줄에서 「회의번호 … 발언자」 머리줄을 찾는다.
    첫 시트는 「회의록 목록리스트」라서 그대로 읽으면 표가 엉뚱하게 잡힌다."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        try:
            for ws in wb.worksheets[:4]:
                ws.reset_dimensions()
                for k, r in enumerate(ws.iter_rows(values_only=True, max_row=6)):
                    if r and "회의번호" in [str(c).strip() for c in r if c] and "발언자" in [str(c).strip() for c in r if c]:
                        return True
        finally:
            wb.close()
    except Exception:
        return False
    return False


def _nanet_redirect(pid, src_path, filename):
    """국회도서관 엑셀을 「파일」로 올렸으면 「직접 받기 → 국회도서관」 변환으로 돌린다."""
    d = os.path.join(_pdir(pid), "source")
    os.makedirs(d, exist_ok=True)
    name = re.sub(r"[^\w.\-]+", "_", os.path.basename(filename), flags=re.UNICODE)[:80]
    if os.path.abspath(src_path) != os.path.abspath(os.path.join(d, name)):
        shutil.copyfile(src_path, os.path.join(d, name))
    job = start_fetch(pid, "korean-nanet", {"files": [name]})
    return dict(get_project(pid), job=job, redirected="korean-nanet")


def set_input_upload(pid, filename, data):
    d = _pdir(pid)
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in (".csv", ".tsv", ".xlsx", ".xlsm"):
        raise ValueError("CSV·TSV·XLSX만 받습니다 · CSV, TSV or XLSX only")
    if ext in (".xlsx", ".xlsm"):
        tmp = os.path.join(d, "upload-check" + ext)
        with open(tmp, "wb") as f:
            f.write(data)
        try:
            if is_nanet_workbook(tmp):
                return _nanet_redirect(pid, tmp, filename)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    for f in os.listdir(d):
        if f.startswith("input."):
            os.remove(os.path.join(d, f))
    name = "input" + ext
    with open(os.path.join(d, name), "wb") as f:
        f.write(data)
    return _after_input(pid, {"path": name, "copied": True, "filename": os.path.basename(filename)})


def set_input_path(pid, path):
    path = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if os.path.splitext(path)[1].lower() not in (".csv", ".tsv", ".xlsx", ".xlsm"):
        raise ValueError("CSV·TSV·XLSX만 받습니다 · CSV, TSV or XLSX only")
    if os.path.splitext(path)[1].lower() in (".xlsx", ".xlsm") and is_nanet_workbook(path):
        return _nanet_redirect(pid, path, os.path.basename(path))
    return _after_input(pid, {"path": path, "copied": False, "filename": os.path.basename(path)})


def _after_input(pid, inp):
    proj = _load(pid)
    if proj.get("rounds"):
        raise ValueError("이미 차수를 돌린 프로젝트는 자료를 바꿀 수 없습니다. 새 프로젝트를 만드세요. · "
                         "This project already has rounds; create a new project for new data.")
    proj["input"] = inp
    path = inp["path"] if not inp["copied"] else os.path.join(_pdir(pid), inp["path"])
    proj["columns"] = _columns_info(path)
    _save(pid, proj)
    return get_project(pid)


def save_setup(pid, setup):
    proj = _load(pid)
    cols = (proj.get("columns") or {}).get("columns", [])
    for k in ("text", "group"):
        if setup.get(k) not in cols:
            raise ValueError(f"{k} 열을 고르세요 · choose the {k} column")
    if setup.get("speaker") and setup["speaker"] not in cols:
        raise ValueError("speaker column not found")
    if setup.get("text_policy") not in ("private", "quotes", "public"):
        raise ValueError("text_policy")
    keep = ("text", "group", "speaker", "context", "text_policy", "per_group", "min_chars", "drop",
            "group_order", "selection", "min_cluster_size", "embed_chars", "min_group_size", "title", "subject", "source")
    proj["setup"] = {k: setup.get(k) for k in keep}
    _save(pid, proj)
    return get_project(pid)


# ── 임베딩 모델 · embedding model (위치 고르기·미리 받기·지우기) ─────────────

def _settings_path():
    return os.path.join(work_root(), "settings.json")


def load_settings():
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        st = {}
    if st.get("model_dir"):
        os.environ["WWH_MODEL_DIR"] = st["model_dir"]
    else:
        os.environ.pop("WWH_MODEL_DIR", None)
    return st


def model_status():
    from whowasheard import embed as E
    load_settings()
    cached = E.model_cached()
    info = E.MODEL_INFO.get(E.DEFAULT_MODEL, {})
    return {"name": E.DEFAULT_MODEL, "dir": E.cache_dir_hint(), "default_dir": E.default_cache_dir(),
            "custom": bool(os.environ.get("WWH_MODEL_DIR")), "cached": cached,
            "size_bytes": E.model_size() if cached else 0, "size": info.get("size", ""),
            "license": info.get("license", ""), "url": info.get("url", "")}


def set_model_dir(path):
    """모델을 둘 폴더를 바꾼다. 빈 값이면 기본 위치로. 이미 받아 둔 모델은 옮기지 않는다(필요하면 지우고 새로 받기)."""
    if any(j["state"] == "running" for j in JOBS.values()):
        raise RuntimeError("작업이 도는 동안에는 바꿀 수 없습니다 · not while a job is running")
    st = load_settings()
    path = (path or "").strip().strip('"')
    if path:
        path = os.path.abspath(os.path.expanduser(path))
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".wwh-write-test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
        except OSError as e:
            raise ValueError(f"그 폴더에 쓸 수 없습니다 · cannot write there: {e}")
        st["model_dir"] = path
    else:
        st.pop("model_dir", None)
    with open(_settings_path(), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    return model_status()


def delete_model():
    from whowasheard import embed as E
    if any(j["state"] == "running" for j in JOBS.values()):
        raise RuntimeError("작업이 도는 동안에는 지울 수 없습니다 · not while a job is running")
    load_settings()
    d = E.model_path()
    if os.path.basename(d) != "models--" + E.DEFAULT_MODEL.replace("/", "--"):
        raise ValueError("unexpected model path")
    if os.path.isdir(d):
        shutil.rmtree(d)
    return model_status()


def start_model_download():
    with _LOCK:
        if any(j["state"] == "running" for j in JOBS.values()):
            raise RuntimeError("이미 돌고 있는 작업이 있습니다 · a job is already running")
        jid = uuid.uuid4().hex[:12]
        JOBS[jid] = {"id": jid, "kind": "model", "project": "", "state": "running", "stage": "model",
                     "started": time.time(), "error": "", "log": "", "stop": False}

    def run():
        job = JOBS[jid]
        try:
            from whowasheard.embed import load_model
            load_settings()
            load_model()
            job["state"] = "done"
            job["stage"] = "done"
        except Exception as e:
            job["state"] = "error"
            job["error"] = f"{type(e).__name__}: {e}"
        job["finished"] = time.time()

    threading.Thread(target=run, daemon=True).start()
    return job_status(jid)


# ── 직접 받기 · fetch from a source ─────────────────────────────────────

def save_source_file(pid, filename, data):
    """국회도서관 엑셀처럼 변환 전 원본 파일을 받아 둔다."""
    d = os.path.join(_pdir(pid), "source")
    os.makedirs(d, exist_ok=True)
    name = re.sub(r"[^\w.\-]+", "_", os.path.basename(filename or "source.xlsx"), flags=re.UNICODE)[:80]
    if os.path.splitext(name)[1].lower() not in (".xlsx", ".xlsm", ".csv"):
        raise ValueError("XLSX·CSV만 · XLSX or CSV only")
    with open(os.path.join(d, name), "wb") as f:
        f.write(data)
    return {"file": name}


def start_fetch(pid, source, params):
    import sources
    if source not in sources.SOURCES:
        raise ValueError("unknown source")
    proj = _load(pid)
    if proj.get("rounds"):
        raise ValueError("이미 차수를 돌린 프로젝트는 자료를 바꿀 수 없습니다. 새 프로젝트를 만드세요. · "
                         "This project already has rounds; create a new project for new data.")
    params = dict(params or {})
    if source == "korean-nanet":
        names = params.get("files") or ([params["file"]] if params.get("file") else [])
        paths = [os.path.join(_pdir(pid), "source", os.path.basename(f)) for f in names]
        if not paths or not all(os.path.isfile(x) for x in paths):
            raise ValueError("국회도서관 엑셀 파일을 먼저 올리세요 · upload the workbook(s) first")
        params["files"] = paths
        params.pop("file", None)
    with _LOCK:
        if any(j["state"] == "running" for j in JOBS.values()):
            raise RuntimeError("이미 돌고 있는 작업이 있습니다 · a job is already running")
        jid = uuid.uuid4().hex[:12]
        JOBS[jid] = {"id": jid, "kind": "fetch", "source": source, "project": pid, "state": "running", "stage": "fetch",
                     "detail": "", "count": 0, "pct": None, "started": time.time(), "error": "", "log": "", "stop": False}
    threading.Thread(target=_run_fetch, args=(jid, pid, source, params), daemon=True).start()
    return job_status(jid)


def _run_fetch(jid, pid, source, params):
    import sources
    job = JOBS[jid]
    d = _pdir(pid)
    out = os.path.join(d, "fetch.csv")
    try:
        res = sources.SOURCES[source](params, out, job, work_root())
        made = res.get("file") or "fetch.csv"
        for f in os.listdir(d):
            if f.startswith("input."):
                os.remove(os.path.join(d, f))
        ext = os.path.splitext(made)[1].lower()
        os.replace(os.path.join(d, made), os.path.join(d, "input" + ext))
        if os.path.exists(out + ".names.csv"):
            os.makedirs(os.path.join(d, "source"), exist_ok=True)
            os.replace(out + ".names.csv", os.path.join(d, "source", "speaker_names_inferred.csv"))
        safe = {k: ([os.path.basename(x) for x in v] if k == "files" else v) for k, v in params.items() if k not in sources.SECRET_KEYS}
        rec = {"source": source, "params": safe, "fetched": _dt.datetime.now().isoformat(timespec="seconds"),
               "rows": res.get("rows"), "note": res.get("note", "")}
        with open(os.path.join(d, "source.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        job["stage"] = "columns"
        _after_input(pid, {"path": "input" + ext, "copied": True,
                           "filename": f"{source} · {rec['fetched'][:10]}"})
        proj = _load(pid)
        if rec["rows"] is None:
            rec["rows"] = (proj.get("columns") or {}).get("rows")
        proj["suggest"] = res.get("suggest") or {}
        proj["fetched"] = rec
        _save(pid, proj)
        job["log"] = res.get("note", "")
        job["count"] = res.get("rows") or job.get("count")
        job["state"] = "done"
        job["stage"] = "done"
    except Exception as e:
        job["state"] = "error"
        job["error"] = f"{type(e).__name__}: {e}"
        job["log"] = traceback.format_exc()[-3000:]
        if os.path.exists(out):
            os.remove(out)
    job["finished"] = time.time()


def stop_job(jid):
    j = JOBS.get(jid)
    if not j:
        raise FileNotFoundError(jid)
    j["stop"] = True
    return job_status(jid)


# ── 차수 실행 · run a round ─────────────────────────────────────────────

def start_round(pid, preset_file=None):
    """preset_file: None(규칙 없음) 또는 rules/ 안의 파일 이름."""
    with _LOCK:
        busy = [j for j in JOBS.values() if j["state"] == "running"]
        if busy:
            raise RuntimeError("이미 돌고 있는 작업이 있습니다 · a job is already running")
        proj = _load(pid)
        if not proj.get("setup", {}).get("text"):
            raise ValueError("자료와 열을 먼저 정하세요 · set up the data first")
        if preset_file:
            if not re.fullmatch(r"[\w\-.]+\.json", preset_file):
                raise ValueError("bad rules file")
            if not os.path.exists(os.path.join(_pdir(pid), "rules", preset_file)):
                raise FileNotFoundError(preset_file)
        n = len(proj.get("rounds", [])) + 1
        jid = uuid.uuid4().hex[:12]
        JOBS[jid] = {"id": jid, "kind": "round", "project": pid, "round": n, "state": "running", "stage": "load",
                     "started": time.time(), "error": "", "log": ""}
    threading.Thread(target=_run_round, args=(jid, pid, n, preset_file), daemon=True).start()
    return JOBS[jid]


def shared_cache():
    """임베딩 저장소 — 모든 프로젝트가 함께 쓴다(같은 글이면 다시 계산하지 않음). 원문은 없고 해시와 벡터만.
    Embedding store shared by all projects (hash → vector, no raw text)."""
    return os.path.join(work_root(), "_cache", "embeddings")


def _legacy_caches():
    """예전 판이 프로젝트마다 남긴 캐시 — 필요한 벡터만 공용 저장소로 옮겨 온다."""
    root = work_root()
    out = []
    try:
        for nm in os.listdir(root):
            fp = os.path.join(root, nm, "cache", "embeddings.npz")
            if os.path.isfile(fp):
                out.append(fp)
    except OSError:
        pass
    return out


def _run_round(jid, pid, n, preset_file):
    job = JOBS[jid]
    try:
        from whowasheard import presets as P
        from whowasheard.cluster import ClusterParams
        from whowasheard.data import load_table
        from whowasheard.report import diagnose, summary_text, write_reports
        proj = _load(pid)
        d = _pdir(pid)
        s = proj["setup"]
        preset = P.load(os.path.join(d, "rules", preset_file)) if preset_file else P.load("none")
        if s.get("min_chars") is not None:  # 0도 그대로 쓴다 · 0 is a valid choice
            preset = dict(preset, min_chars=int(s["min_chars"]))
        load_settings()
        rows = load_table(_input_path(pid, proj))
        prev = None
        if proj["rounds"]:
            with open(os.path.join(d, proj["rounds"][-1]["run"] + "_public.json"), encoding="utf-8") as f:
                prev = json.load(f)
        params = ClusterParams(min_cluster_size=(int(s["min_cluster_size"]) if s.get("min_cluster_size") else None),
                               selection=s.get("selection") or "eom")
        drop = {}
        for item in s.get("drop") or []:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                drop.setdefault(item[0], []).append(item[1])

        def progress(stage):
            job["stage"] = stage
            if stage == "embed":
                from whowasheard.embed import DEFAULT_MODEL, MODEL_INFO, cache_dir_hint, model_cached
                info = MODEL_INFO.get(DEFAULT_MODEL, {})
                job["model"] = {"name": DEFAULT_MODEL, "cached": model_cached(DEFAULT_MODEL), "cache_dir": cache_dir_hint(),
                                "size": info.get("size", ""), "license": info.get("license", ""),
                                "langs": info.get("langs", ""), "url": info.get("url", "")}

        def eprog(done, total, reused):
            now = time.time()
            if "e_t0" not in job:
                job["e_t0"], job["e_d0"] = now, done
            job["e_done"], job["e_total"], job["e_reused"] = done, total, reused
            rate = (done - job["e_d0"]) / max(1e-6, now - job["e_t0"])
            job["e_eta"] = round((total - done) / rate) if rate > 0 and done > job["e_d0"] else None

        rep = diagnose(rows, s["text"], s["group"], s.get("speaker") or None,
                       per_group=int(s.get("per_group") or 0), params=params,
                       text_policy=s.get("text_policy") or "private",
                       context=tuple(s.get("context") or ()),
                       title=s.get("title") or "공론 지도 · Map of the discourse",
                       subject=s.get("subject") or "", source=s.get("source") or (proj.get("input") or {}).get("filename", ""),
                       preset=preset, previous=prev,
                       embed_max_chars=(int(s["embed_chars"]) if s.get("embed_chars") else None),
                       cache_dir=shared_cache(), also_read=_legacy_caches(), drop=drop or None,
                       embed_progress=eprog, should_stop=lambda: bool(job.get("stop")),
                       min_group_size=int(s.get("min_group_size") or 0),
                       group_order=tuple(s.get("group_order") or ()), progress=progress)
        job["stage"] = "write"
        name = f"r{n}"
        with _plock(pid):
            write_reports(rep, os.path.join(d, "rounds"), name)
        pub = rep.public
        summary = {
            "topics": len(pub["clusters"]),
            "topics_range": [min(r["clusters"] for r in pub["runs"]), max(r["clusters"] for r in pub["runs"])],
            "unclustered_range": [min(r["unclustered_pct"] for r in pub["runs"]), max(r["unclustered_pct"] for r in pub["runs"])],
            "ari": (pub.get("ari") or {}).get("mean"),
            "groups": pub["groups"],
            "dropped_pct": [pub["clean"][g]["dropped_pct"] for g in pub["groups"]],
            "rule_dropped": [pub["clean"][g].get("rule", 0) for g in pub["groups"]],
            "unclustered_by_group": pub["unclustered_by_group"],
            "n_sample": pub["n_sample"],
        }
        proj = _load(pid)
        proj["rounds"].append({"n": n, "run": f"rounds/{name}", "preset": preset_file or "none",
                               "preset_sha": preset.get("_sha256"), "finished": _dt.datetime.now().isoformat(timespec="seconds"),
                               "summary": summary})
        _save(pid, proj)
        job["log"] = summary_text(rep)
        job["state"] = "done"
        job["stage"] = "done"
    except Exception as e:
        from whowasheard.embed import Stopped
        if isinstance(e, Stopped):
            job["state"] = "stopped"
            job["error"] = str(e)
        else:
            job["state"] = "error"
            job["error"] = f"{type(e).__name__}: {e}"
            job["log"] = traceback.format_exc()[-3000:]
    job["finished"] = time.time()


def job_status(jid):
    j = JOBS.get(jid)
    if not j:
        raise FileNotFoundError(jid)
    return dict(j, elapsed=round((j.get("finished") or time.time()) - j["started"]))


def current_job():
    run = [j for j in JOBS.values() if j["state"] == "running"]
    return job_status(run[0]["id"]) if run else None


# ── 판단 · review ──────────────────────────────────────────────────────

def _round(pid, n):
    proj = _load(pid)
    for r in proj["rounds"]:
        if int(r["n"]) == int(n):
            return proj, r
    raise FileNotFoundError(f"round {n}")


def review_data(pid, n):
    """판단 화면에 필요한 것 — 묶음(특징어·크기·흔들림·구성)과 내부 표본 원문. 이 PC 화면에만 쓴다."""
    proj, r = _round(pid, n)
    d = _pdir(pid)
    with open(os.path.join(d, r["run"] + "_public.json"), encoding="utf-8") as f:
        pub = json.load(f)
    with open(os.path.join(d, r["run"] + "_INTERNAL_do-not-share.json"), encoding="utf-8") as f:
        inter = json.load(f)
    nruns = len(pub.get("runs") or [])
    clusters = []
    for c in pub["clusters"]:
        cid = str(c["id"])
        samp = [x for x in inter.get("samples", {}).get(cid, []) if "text" in x]
        reps = inter.get("reps", {}).get(cid, [])
        clusters.append({"id": c["id"], "n": c["n"], "app": c["app"], "runs": nruns, "words": c["words"],
                         "comp": c["comp"], "label": c.get("label", ""),
                         "reps": [{"text": x["text"][:600], "speaker": x.get("speaker", "")} for x in reps],
                         "samples": [{"text": x["text"][:600], "speaker": x.get("speaker", "")} for x in samp],
                         "total_texts": len(inter.get("members", {}).get(cid, []))})
    reviews = {}
    for f in os.listdir(os.path.join(d, "reviews")):
        m = re.fullmatch(rf"r{int(n)}_(.+)\.json", f)
        if m:
            with open(os.path.join(d, "reviews", f), encoding="utf-8") as fh:
                reviews[m.group(1)] = json.load(fh)
    agr = None
    if reviews:
        from whowasheard.reviews import agreement
        revs = [dict(v, exclude=[int(x) for x in v.get("exclude", [])], labels={str(k): x for k, x in v.get("labels", {}).items()})
                for v in reviews.values()]
        agr = agreement(revs, [c["id"] for c in pub["clusters"]])
    return {"round": int(n), "groups": pub["groups"], "text_policy": pub.get("text_policy"),
            "clusters": clusters, "reviews": reviews, "agreement": agr, "preset": r.get("preset")}


def cluster_texts(pid, n, cid, offset=0, limit=20):
    """한 묶음의 글을 더 본다(맥락 확인용). 이 PC 화면에만 쓴다. 섞어서 보여 주되 늘 같은 순서."""
    import random
    proj, r = _round(pid, n)
    with open(os.path.join(_pdir(pid), r["run"] + "_INTERNAL_do-not-share.json"), encoding="utf-8") as f:
        mem = json.load(f).get("members", {}).get(str(int(cid)), [])
    order = list(range(len(mem)))
    random.Random(int(cid) * 7919 + 13).shuffle(order)
    sl = order[int(offset):int(offset) + int(limit)]
    return {"total": len(mem), "offset": int(offset), "texts": [mem[i][:1500] for i in sl]}


def save_review(pid, n, body):
    _round(pid, n)
    who = (body.get("reviewer") or "").strip()
    if not who or not re.fullmatch(r"[\w\-. ]{1,40}", who, flags=re.UNICODE):
        raise ValueError("채점자 이름을 적으세요(글자·숫자) · enter a reviewer name")
    rec = {"reviewer": who, "round": int(n),
           "exclude": sorted({int(x) for x in body.get("exclude", [])}),
           "labels": {str(k): str(v).strip() for k, v in (body.get("labels") or {}).items() if str(v).strip()},
           "notes": str(body.get("notes") or ""),
           "saved": _dt.datetime.now().isoformat(timespec="seconds")}
    path = os.path.join(_pdir(pid), "reviews", f"r{int(n)}_{who.replace(' ', '_')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return review_data(pid, n)


# ── 규칙 · rules ───────────────────────────────────────────────────────

def make_draft(pid, n, policy="majority"):
    """N차 판단들로 N+1차 규칙 초안을 쓴다. 앞 차수 규칙이 있으면 이어받는다."""
    from whowasheard import presets as P
    from whowasheard.report import load_report
    from whowasheard.reviews import agreement
    from whowasheard.rules import write_draft
    proj, r = _round(pid, n)
    d = _pdir(pid)
    rv = review_data(pid, n)
    if not rv["reviews"]:
        raise ValueError("먼저 판단을 저장하세요 · save at least one review first")
    revs = [dict(v, exclude=[int(x) for x in v.get("exclude", [])], labels={str(k): x for k, x in v.get("labels", {}).items()})
            for v in rv["reviews"].values()]
    agr = agreement(revs, [c["id"] for c in rv["clusters"]], policy)
    rep = load_report(os.path.join(d, r["run"] + "_public.json"), os.path.join(d, r["run"] + "_INTERNAL_do-not-share.json"))
    base = P.load(os.path.join(d, "rules", r["preset"])) if r.get("preset") and r["preset"] != "none" else None
    out = os.path.join(d, "rules", f"r{int(n) + 1}-draft.json")
    draft = write_draft(rep.public, rep.internal.get("members", {}), agr["excluded"],
                        f"{_slug(proj['name'])}-r{int(n) + 1}", out, agr, base)
    return {"file": os.path.basename(out), "rules": draft, "agreement": agr}


def get_rules(pid, fname):
    if not re.fullmatch(r"[\w\-.]+\.json", fname):
        raise ValueError("bad file")
    with open(os.path.join(_pdir(pid), "rules", fname), encoding="utf-8") as f:
        return json.load(f)


def save_rules(pid, fname, body):
    """사람이 고친 규칙을 저장한다. 패턴은 모두 정규식으로 컴파일해 본다."""
    if not re.fullmatch(r"r\d+\.json", fname):
        raise ValueError("규칙 파일 이름은 r<차수>.json · rules file must be named r<round>.json")
    pats = []
    for p in body.get("exclude_patterns", []):
        pat = p.get("pattern", "") if isinstance(p, dict) else str(p)
        if not pat.strip():
            continue
        try:
            re.compile(pat)
        except re.error as e:
            raise ValueError(f"패턴 오류 · bad pattern: {pat} ({e})")
        pats.append({"pattern": pat, "max_chars": int((p.get("max_chars") if isinstance(p, dict) else 0) or 0)})
    src = body.get("_from")
    base = get_rules(pid, src) if src else {}
    rec = dict(base)
    rec.update({"name": body.get("name") or base.get("name") or fname[:-5], "version": str(body.get("version") or "1"),
                "exclude_patterns": pats,
                "min_chars": int(body["min_chars"] if body.get("min_chars") is not None else base.get("min_chars", 5))})
    if "human_edits" in body:
        rec["human_edits"] = body["human_edits"]
    rec["saved"] = _dt.datetime.now().isoformat(timespec="seconds")
    with open(os.path.join(_pdir(pid), "rules", fname), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return {"file": fname, "rules": rec}


def apply_review_labels(pid, n):
    from whowasheard.report import apply_labels, load_report, write_reports
    from whowasheard.reviews import agreement
    proj, r = _round(pid, n)
    d = _pdir(pid)
    rv = review_data(pid, n)
    if not rv["reviews"]:
        raise ValueError("판단이 없습니다 · no reviews")
    revs = [dict(v, exclude=[int(x) for x in v.get("exclude", [])], labels={str(k): x for k, x in v.get("labels", {}).items()})
            for v in rv["reviews"].values()]
    agr = agreement(revs, [c["id"] for c in rv["clusters"]])
    if not agr["labels"]:
        raise ValueError("판단 파일에 주제 이름이 없습니다. ④에서 이름을 적고 저장한 뒤 누르세요. · No topic names in the reviews yet.")
    rep = load_report(os.path.join(d, r["run"] + "_public.json"), os.path.join(d, r["run"] + "_INTERNAL_do-not-share.json"))
    apply_labels(rep.public, agr["labels"], "채점자 " + ", ".join(agr["reviewers"]) + " — 엇갈린 이름은 「A / B」로 함께 적음")
    write_reports(rep, os.path.join(d, "rounds"), f"r{int(n)}")
    return {"labels": agr["labels"]}


def file_path(pid, rel):
    """보고서 파일을 브라우저로 보여 줄 때 — 프로젝트 폴더 밖은 못 나간다."""
    d = os.path.realpath(_pdir(pid))
    p = os.path.realpath(os.path.join(d, rel))
    if not p.startswith(d + os.sep) or not os.path.isfile(p):
        raise FileNotFoundError(rel)
    return p


def open_folder(pid):
    d = _pdir(pid)
    try:
        if sys.platform.startswith("win"):
            os.startfile(d)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", d])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", d], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return {"dir": d}


# ── 라우팅 · routing (http_hub가 부른다) ─────────────────────────────────

def _refresh_report_html(pid, p):
    """보고서 화면(템플릿)이 고쳐졌으면 예전 차수 보고서도 저장된 JSON으로 다시 그린다 — 숫자는 그대로, 화면만 새 판.
    If the report template changed since a round was written, re-render that round's HTML from its saved JSON."""
    import re
    m = re.search(r"(r\d+)_(public|INTERNAL_do-not-share)\.html$", p)
    if not m:
        return
    try:
        from whowasheard import report as R
        if os.path.getmtime(p) >= os.path.getmtime(R.TEMPLATE):
            return
        d = os.path.dirname(p)
        pj = os.path.join(d, m.group(1) + "_public.json")
        ij = os.path.join(d, m.group(1) + "_INTERNAL_do-not-share.json")
        if not os.path.exists(pj):
            return
        with _plock(pid):
            R.write_reports(R.load_report(pj, ij), d, m.group(1))
    except Exception:
        pass


def route(method, path, query, body, headers, token):
    """돌려주는 값: (상태 코드, 본문, content-type) — /api/... 와 /files/... 만 다룬다."""
    from urllib.parse import unquote
    path = unquote(path)
    if path.startswith("/files/"):
        if (query.get("t") or [""])[0] != token:
            return 403, {"error": "bad token"}, None
        parts = path[len("/files/"):].split("/", 1)
        if len(parts) != 2:
            return 404, {"error": "not found"}, None
        p = file_path(parts[0], parts[1])
        _refresh_report_html(parts[0], p)
        ctype = "text/html; charset=utf-8" if p.endswith(".html") else "application/json; charset=utf-8"
        with open(p, "rb") as f:
            return 200, f.read(), ctype
    if headers.get("X-WWH-Token") != token:
        return 403, {"error": "bad token"}, None
    seg = [s for s in path[len("/api/"):].split("/") if s]
    j = {}
    if body and method == "POST" and not (len(seg) == 3 and seg[2] in ("upload", "srcfile")):
        j = json.loads(body.decode("utf-8") or "{}")
    try:
        if seg == ["projects"]:
            return 200, (list_projects() if method == "GET" else create_project(j.get("name", ""))), None
        if seg == ["model"]:
            return 200, model_status(), None
        if seg[:1] == ["model"] and len(seg) == 2 and method != "POST":
            return 405, {"error": "POST only"}, None
        if seg == ["model", "dir"]:
            return 200, set_model_dir(j.get("path", "")), None
        if seg == ["model", "delete"]:
            return 200, delete_model(), None
        if seg == ["model", "download"]:
            return 200, start_model_download(), None
        if seg == ["job"]:
            return 200, {"job": current_job()}, None
        if len(seg) == 2 and seg[0] == "jobs":
            return 200, job_status(seg[1]), None
        if len(seg) == 3 and seg[0] == "jobs" and seg[2] == "stop":
            return 200, stop_job(seg[1]), None
        if seg and seg[0] == "p" and len(seg) >= 2:
            pid, rest = seg[1], seg[2:]
            if not rest:
                return 200, get_project(pid), None
            if rest == ["upload"] and method == "POST":
                if len(body) > MAX_UPLOAD:
                    return 413, {"error": "too large"}, None
                from urllib.parse import unquote
                return 200, set_input_upload(pid, unquote(headers.get("X-Filename") or "input.csv"), body), None
            if rest == ["srcfile"] and method == "POST":
                if len(body) > MAX_UPLOAD:
                    return 413, {"error": "too large"}, None
                from urllib.parse import unquote as _uq
                return 200, save_source_file(pid, _uq(headers.get("X-Filename") or "source.xlsx"), body), None
            if rest == ["fetch"]:
                return 200, start_fetch(pid, j.get("source"), j.get("params") or {}), None
            if rest == ["path"]:
                return 200, set_input_path(pid, j.get("path", "")), None
            if rest == ["setup"]:
                return 200, save_setup(pid, j), None
            if rest == ["run"]:
                return 200, start_round(pid, j.get("rules") or None), None
            if rest == ["open"]:
                return 200, open_folder(pid), None
            if rest and rest[0] in ("round", "rules"):
                with _plock(pid):
                    if len(rest) >= 2 and rest[0] == "round":
                        n = int(rest[1])
                        tail = rest[2:]
                        if tail == ["review"]:
                            return 200, (review_data(pid, n) if method == "GET" else save_review(pid, n, j)), None
                        if len(tail) == 2 and tail[0] == "cluster":
                            off = int((query.get("offset") or ["0"])[0])
                            return 200, cluster_texts(pid, n, int(tail[1]), off), None
                        if tail == ["draft"]:
                            return 200, make_draft(pid, n, j.get("policy") or "majority"), None
                        if tail == ["labels"]:
                            return 200, apply_review_labels(pid, n), None
                    if len(rest) == 2 and rest[0] == "rules":
                        return 200, (get_rules(pid, rest[1]) if method == "GET" else save_rules(pid, rest[1], j)), None
        return 404, {"error": "not found"}, None
    except FileNotFoundError as e:
        return 404, {"error": f"not found: {e}"}, None
    except (ValueError, RuntimeError) as e:
        return 400, {"error": str(e)}, None

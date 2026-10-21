"""설치판(파이썬 없이 도는 판)의 시작점.
Entry point of the Python-free build. Our code ships as plain files under app/;
the bundled interpreter runs start.py from there.

  who-was-heard                 안내 페이지와 세 서버를 켠다 (start.py와 같다)
  who-was-heard-cli --stdio X   MCP 서버 하나를 stdio로 (Claude 데스크톱용)
"""
import os
import sys

import deps  # noqa: F401  — 묶을 모듈 목록 · makes PyInstaller bundle our dependencies


def base():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "app")
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    root = base()
    sys.path[:0] = [root, os.path.join(root, "servers")]
    os.environ["WWH_FROZEN"] = "1"
    # numba(UMAP)가 함수를 캐시할 쓰기 가능한 곳 · a writable cache for numba
    os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".who-was-heard", "numba"))
    import runpy
    argv = sys.argv[1:]
    if argv[:1] == ["--stdio"] and len(argv) >= 2:
        sys.argv = [argv[1]] + argv[2:]
        runpy.run_path(os.path.join(root, "servers", argv[1], "server.py"), run_name="__main__")
        return
    sys.argv = [os.path.join(root, "start.py")] + argv
    runpy.run_path(sys.argv[0], run_name="__main__")


if __name__ == "__main__":
    main()

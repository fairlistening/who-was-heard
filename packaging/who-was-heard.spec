# -*- mode: python -*-
# 설치판(파이썬 없이 도는 판) 만들기 · build the Python-free app
#   pyinstaller packaging/who-was-heard.spec --noconfirm
# 결과 · output:  dist/who-was-heard/   (macOS: dist/who-was-heard.app)
#
# 우리 코드는 app/ 아래에 평범한 파일로 들어가고, 함께 든 파이썬이 그것을 돌린다.
# Our code ships as plain files under app/; the bundled interpreter runs it.
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(ROOT, "start.py"), "app"),
    (os.path.join(ROOT, "servers"), "app/servers"),
    (os.path.join(ROOT, "whowasheard"), "app/whowasheard"),
    (os.path.join(ROOT, "LICENSE"), "."),
    (os.path.join(ROOT, "LICENSE-docs"), "."),
    (os.path.join(ROOT, "NOTICE"), "."),
]
binaries = []
hiddenimports = []
for pkg in ("sentence_transformers", "transformers", "tokenizers", "huggingface_hub", "safetensors",
            "umap", "pynndescent", "hdbscan", "sklearn", "openpyxl"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("scipy.spatial") + collect_submodules("scipy.sparse")
# 시험 코드는 빼서 크기를 줄인다 · drop test modules to keep the build small
hiddenimports = [h for h in hiddenimports if ".tests" not in h and ".testing" not in h]

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "notebook", "pytest", "torchvision", "torchaudio",
              "tensorflow", "jax", "pandas.tests", "sklearn.tests", "cv2", "PIL.ImageQt",
              "torch.utils.tensorboard", "transformers.models.deprecated"],
    noarchive=False,
)
pyz = PYZ(a.pure)

ICON = None
app = EXE(pyz, a.scripts, [], exclude_binaries=True, name="who-was-heard",
          console=False, icon=ICON)       # 창 없이 · no console window
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="who-was-heard-cli",
          console=True, icon=ICON)        # 기록 보기·Claude 데스크톱(stdio)용 · logs and stdio
coll = COLLECT(app, cli, a.binaries, a.datas, name="who-was-heard")

if sys.platform == "darwin":
    BUNDLE(coll, name="who-was-heard.app", bundle_identifier="org.fairlistening.who-was-heard")

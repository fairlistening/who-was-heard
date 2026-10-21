"""설치판에 넣을 모듈 목록 — PyInstaller가 이 파일의 import를 보고 함께 묶는다.
Modules bundled into the installer. Our own code ships as plain files next to it
(app/), so PyInstaller cannot see what it imports; this list does that job.
Regenerate when the code imports something new:  python packaging/make_deps.py
"""
# 표준 라이브러리 · standard library
import argparse, collections, csv, ctypes, dataclasses, datetime, hashlib, html, html.parser  # noqa: E401,F401
import http.server, importlib.util, io, json, locale, math, os, random, re, secrets  # noqa: E401,F401
import shutil, subprocess, sys, threading, time, traceback, typing, uuid, webbrowser  # noqa: E401,F401
import urllib.error, urllib.parse, urllib.request, runpy, zipfile, tempfile, glob  # noqa: E401,F401
# 계산 · computation
import numpy  # noqa: F401
import scipy.spatial  # noqa: F401
import sklearn.metrics  # noqa: F401
import umap  # noqa: F401
import hdbscan  # noqa: F401
import sentence_transformers  # noqa: F401
import openpyxl  # noqa: F401

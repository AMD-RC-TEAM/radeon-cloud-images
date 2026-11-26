"""Start the Strata OpenAI server next to JupyterLab, and stop it when JupyterLab stops.

Radeon Cloud starts every notebook instance with its own command (`jupyter lab`), so an image cannot use CMD or an
entrypoint. jupyter_server loads this extension at start-up (enabled in {sys.prefix}/etc/jupyter/jupyter_server_config.d/
rc_strata.json). It starts /opt/b0/current/run.sh in its own process group if the model is mounted. It writes nothing
into the user's workspace: the template supplies the notebook (images carry only the environment). The server listens on 127.0.0.1:8080 and is reached through
jupyter-server-proxy at <notebook URL prefix>/proxy/8080/. On shutdown (SIGTERM to Jupyter) it SIGTERMs the server and
waits up to 25 s, inside the platform's 30 s grace. Set RC_STRATA_AUTOSTART=0 to keep it from starting.
Never raises: a problem here must not stop JupyterLab.
"""
import atexit, os, signal, subprocess

_proc = None


def _jupyter_server_extension_points():
    return [{"module": "rc_strata_autostart"}]


def _stop():
    global _proc
    p, _proc = _proc, None
    if p is None or p.poll() is not None:
        return
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=25)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass


def _load_jupyter_server_extension(app):
    global _proc
    log = app.log
    try:
        if os.environ.get("RC_STRATA_AUTOSTART", "1") == "0":
            log.info("rc_strata_autostart: disabled by RC_STRATA_AUTOSTART=0")
            return
        model = os.environ.get("B0_MODEL", "")
        logdir = os.environ.get("B0_LOG", "/tmp/b0-logs")
        os.makedirs(logdir, exist_ok=True)
        if not os.path.isdir(model):
            msg = f"model not mounted at {model!r}; the Strata server was not started"
            open(os.path.join(logdir, "autostart.log"), "a").write(msg + "\n")
            log.warning("rc_strata_autostart: " + msg)
            return
        out = open(os.path.join(logdir, "autostart.log"), "ab")
        _proc = subprocess.Popen(["bash", "-c", "ulimit -c 0; exec /opt/b0/current/run.sh"], stdout=out,
                                 stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        atexit.register(_stop)
        log.info(f"rc_strata_autostart: started the Strata server (pid {_proc.pid}); log {logdir}/autostart.log")
    except Exception as e:      # noqa: BLE001  (never break JupyterLab)
        log.warning(f"rc_strata_autostart: not started: {e!r}")


def _unload_jupyter_server_extension(app):
    _stop()

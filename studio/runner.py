"""Launch the unmodified command interface without a shell."""
import os
import subprocess
import threading


def engine_environment(keys):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    env.pop('NSCB_STUDIO_KEYS_FILE', None)
    if keys is not None:
        env['NSCB_STUDIO_KEYS_FILE'] = str(keys)
    return env


def execute(prefix, jobs, cwd, env, cancel, emit):
    for index, args in enumerate(jobs, 1):
        if cancel.is_set():
            return None
        emit(f'\n── Étape {index}/{len(jobs)} ──\n')
        with subprocess.Popen([*prefix, *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8',
                              errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as child:
            finished = threading.Event()

            def watch():
                while not finished.wait(0.1):
                    if cancel.is_set():
                        try:
                            child.kill()
                        except OSError:
                            pass
                        return

            watchdog = threading.Thread(target=watch, daemon=True)
            watchdog.start()
            try:
                for line in child.stdout:
                    emit(line)
                code = child.wait()
            finally:
                finished.set()
                watchdog.join()
        if cancel.is_set():
            return None
        if code:
            return code
    return 0

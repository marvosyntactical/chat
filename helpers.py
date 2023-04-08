# copy paste from SO: https://stackoverflow.com/questions/6796492/temporarily-redirect-stdout-stderr

import os
import sys
import time

def spinning_cursor():
    while True:
        for cursor in "|/-\\":
            yield cursor


class Logger(object):
    def __init__(self, logfile: str):
        self.terminal = sys.stdout
        self.log = open(logfile, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        # this handles the flush command by doing nothing.
        # you might want to specify some extra behavior here.
        pass

class RedirectStdStreams(object):
    def __init__(self, stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w")):
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush(); self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush(); self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

if __name__ == '__main__':

    devnull = open(os.devnull, 'w')
    print('Fubar')

    with RedirectStdStreams(stdout=devnull, stderr=devnull):
        print("You'll never see me")


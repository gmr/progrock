"""
The :py:class:`progrock.MultiProgress` class is used in conjunction with the
methods exposed at the module level such as :py:meth:`progrock.increment` to
create a full-screen experience allowing the user to track the progress of
individual processes as they perform their work.

This module is meant as a complement to :py:class:`multiprocessing.Process` and
provide an easy to use, yet opinionated view of child process progress bars.

"""
__version__ = '0.3.1'

import curses
import datetime
import locale
import math
import multiprocessing
import os
try:
    import Queue as queue
except ImportError:
    import queue
import sys
import threading
import time

_INCREMENT = 1
_STATUS = 2
_STEPS = 3
_VALUE = 4
_APP_INCREMENT = 5
_APP_STEPS = 6
_RESET_PROC_START = 7


class _Interval(threading.Thread):
    """The _Interval class is used to invoke the callback target every N
    seconds.

    :param int interval: The interval duration in seconds
    :param method target: The callback method to invoke.

    """
    def __init__(self, interval, target):
        super(_Interval, self).__init__()
        self.interval = interval
        self.callback = target
        self.daemon = True
        self.stopped = threading.Event()

    def run(self):
        while not self.stopped.wait(self.interval):
            self.callback()

    def stop(self):
        self.stopped.set()


class _Process(object):
    """The _Process object wraps all of the attributes of a process that are
    needed by the MultiProgress class for rendering status.

    :param multiprocessing.Process process: The process object
    :param curses.Window window: The window for the process progress
    :param float start: The epoch value for when the process started
    :param str status: The status text for the progress box
    :param int|float steps: The number of steps for the progress bar
    :param int|float value: The progress value for the progress bar

    """
    def __init__(self, process, window, status, steps, value):
        self.pid = process.pid
        self.process = process
        self.window = window
        self.start = time.time()
        self.status = status
        self.steps = float(steps)
        self.value = float(value)


def increment(ipc_queue, value=1):
    """Increment the progress value for the current process, passing in the
    queue exposed by ``MultiProgress.ipc_queue`` and automatically passed into
    the target function when creating the process with
    :py:class:`MultiProgress.new_process`.

    :param multiprocessing.Queue ipc_queue: The IPC command queue
    :param int value: The value to increment by. Default: ``1``

    """
    ipc_queue.put((_INCREMENT, os.getpid(), value))


def increment_app(ipc_queue, value=1):
    """Increment the progress value for the application, passing in the
    queue exposed by ``MultiProgress.ipc_queue``.

    :param multiprocessing.Queue ipc_queue: The IPC command queue
    :param int value: The value to increment by. Default: ``1``

    """
    ipc_queue.put((_APP_INCREMENT, 0, value))


def reset_start_time(ipc_queue):
    """Restart the start time of a process, passing in the queue
    exposed by ``MultiProgress.ipc_queue`` and automatically passed into
    the target function when creating the process with
    :py:class:`MultiProgress.new_process`.

    :param multiprocessing.Queue ipc_queue: The IPC command queue

    """
    ipc_queue.put((_RESET_PROC_START, os.getpid(), 0))


def reset_value(ipc_queue):
    """Reset the progress value for the current process, passing in the queue
    exposed by ``MultiProgress.ipc_queue`` and automatically passed into
    the target function when creating the process with
    :py:class:`MultiProgress.new_process`.

    :param multiprocessing.Queue ipc_queue: The IPC command queue

    """
    ipc_queue.put((_VALUE, os.getpid(), 0))


def set_app_step_count(ipc_queue, steps):
    """Set the number of steps for the application, passing in the queue
    exposed by ``MultiProgress.ipc_queue``.

    :param multiprocessing.Queue ipc_queue: The IPC command queue
    :param int steps: The number of steps for the application.

    """
    ipc_queue.put((_STEPS, 0, steps))


def set_status(ipc_queue, status):
    """Set the status of current process, passing in the queue
    exposed by ``MultiProgress.ipc_queue`` and automatically passed into
    the target function when creating the process with
    :py:class:`MultiProgress.new_process`.

    :param multiprocessing.Queue ipc_queue: The IPC command queue
    :param str status: The status text for the current process

    """
    ipc_queue.put((_STATUS, os.getpid(), status))


def set_step_count(ipc_queue, steps):
    """Set the number of steps for current process, passing in the queue
    exposed by ``MultiProgress.ipc_queue`` and automatically passed into
    the target function when creating the process with
    :py:class:`MultiProgress.new_process`.

    :param multiprocessing.Queue ipc_queue: The IPC command queue
    :param int steps: The number of steps for the current process

    """
    ipc_queue.put((_STEPS, os.getpid(), steps))


def set_value(ipc_queue, value):
    """Set the progress value for the current process, passing in the queue
    exposed by ``MultiProgress.ipc_queue`` and automatically passed into
    the target function when creating the process with
    :py:class:`MultiProgress.new_process`.

    :param multiprocessing.Queue ipc_queue: The IPC command queue
    :param int value: The value to set for the process

    """
    ipc_queue.put((_VALUE, os.getpid(), value))


class MultiProgress(object):
    """The MultiProgress class is responsible for rendering the progress screen
    using curses. In addition, it can wrap the creation of processes for you
    to automatically pass in the :py:class:`multiprocessing.Queue` object that
    is used to issue commands for updating the UI.

    If you do not pass in a ``title`` for the application, the Python file that
    is being run will be used as a title for the screen.

    If you pass in ``steps``, a progress bar will be centered in the footer to
    display the overall progress of an application. The bar can be incremented
    from the parent process using :py:meth:`MultiProgress.increment_app` or
    if you're incrementing from a child process, you can call
    :py:meth:`progrock.increment_app` passing in ``ipc_queue``.

    :param str title: The application title
    :param int steps: Overall steps for the application
    :param int value: Overall progress value for the application

    """
    BOX_HEIGHT = 4
    FOOTER_HEIGHT = 2
    HEADER_HEIGHT = 2

    TIME_FORMAT = '%Y-%m-%d %I:%M:%S'

    DEFAULT_STEPS = 100
    DEFAULT_STATUS = 'Initializing'

    def __init__(self, title=None, steps=None, value=0):
        locale.setlocale(locale.LC_ALL, '')
        self.ipc_queue = multiprocessing.Queue()
        self._canvas = None
        self._code = locale.getpreferredencoding()
        self._footer = None
        self._header = None
        self._canvas_offset = 0
        self._lock = threading.Lock()
        self._process = dict()
        self._screen = None
        self._start = None
        self._steps = steps
        self._stop = threading.Event()
        self._title = title or sys.argv[0]
        self._value = value
        self._update_interval = _Interval(1, self._on_screen_update_interval)
        self._update_thread = threading.Thread(target=self._watch_ipc_queue,
                                               args=(self.ipc_queue,
                                                     self._stop))
        self._update_thread.daemon = True

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()

    def initialize(self):
        """Initialize the :py:class:`MultiProgress` screen. Should only be
        invoked if not using the :py:class:`MultiProgress` instance as a
        context manager. If the instance :py:class:`MultiProgress` instance is
        used as a context manager, this is done automatically.

        """
        self._start = time.time()
        curses.wrapper(self._initialize_screen)
        self._keyboard_input = threading.Thread(target=self._keyboard_handler,
                                                args=(self._screen,
                                                      self._stop))
        self._keyboard_input.daemon = True
        self._keyboard_input.start()
        self._update_thread.start()
        self._update_interval.start()

    def shutdown(self):
        """Shutdown :py:class:`MultiProgress` screen. Must be called if the
        :py:class:`MultiProgress` instance is not being used as a context
        manager. If the instance :py:class:`MultiProgress` instance is used
        as a context manager, this is done automatically.

        """
        self._stop.set()
        self._update_interval.stop()
        curses.endwin()

    def add_process(self, process, status=DEFAULT_STATUS, steps=DEFAULT_STEPS,
                    value=0):
        """Add a process to the MultiProgress display. The process must
        already have been started proior to invoking this method.

        :param multiprocessing.Process: The process to add
        :param str status: The status text for the process box
        :param int|float steps: The number of steps for the progress bar
        :param int|float value: Current progress value for the process

        """
        start_y = int(math.floor(self._process_count / 2) * self.BOX_HEIGHT)
        start_x = (self._process_count % 2) * self._box_width
        self._maybe_resize_canvas(start_y)

        try:
            window = self._canvas.subwin(self.BOX_HEIGHT, self._box_width,
                                         start_y, start_x)
        except curses.error as error:
            raise ValueError('Error creating window for pid %s (%i,%i): %s' %
                             (process.pid, start_y, start_x, error))

        self._process[process.pid] = _Process(process, window, status,
                                              steps, value)
        self._draw_box(process.pid)
        self._draw_footer()

    def increment_app(self, value=1):
        """If using the application progress bar, increment the progress of
        the bar.

        :param int value: The value to increment by. Default: 1

        """
        with self._lock:
            self._value += float(value)
            if self._value > self._steps:
                self._value = self._steps
        if self._steps:
            self._update_footer_progress()

    def new_process(self, target, name=None, args=None, kwargs=None,
                    status=DEFAULT_STATUS, steps=DEFAULT_STEPS, value=0):
        """Create and start new :py:class:`multiprocessing.Process` instance,
        automatically appending the update queue to the positional arguments
        passed into the target when the process is started. Once the process
        is created, it is added to the stack of processes in
        :py:class:`MultiProgress`, bypassing the need to invoke
        :py:meth:`MutiProgress.add_process`.

        :param method target: The method to invoke when the process starts
        :param str name: Process name
        :param tuple args: Positional arguments to pass into the process
        :param dict kwargs: Keyword arguments to pass into the process
        :param str status: The status text for the process box
        :param int|float steps: The number of steps for the progress bar
        :param int|float value: Current progress value for the process
        :return: multiprocessing.Process

        """
        args = [] if not args else list(args)
        args.append(self.ipc_queue)
        process = multiprocessing.Process(target=target,
                                          name=name,
                                          args=tuple(args),
                                          kwargs=kwargs or dict())
        process.start()
        self.add_process(process, status, steps, value)
        return process

    # Internal Methods

    def _box_progress(self, process):
        if not process.steps:
            return self._progress_bar(0, self._progress_bar_width)
        return self._progress_bar((process.value / process.steps),
                                  self._progress_bar_width)

    def _box_status(self, process):
        duration = time.time() - process.start
        width = self._box_width - 25
        status = process.status[0:width]
        display = '<{0}>'.format(process.pid)
        return '{0: <8} {1: <{width}} {2: >10.1f}s'.format(display,
                                                           status,
                                                           duration,
                                                           width=width)

    def _current_display_time(self):
        return datetime.datetime.now().strftime(self.TIME_FORMAT)

    def _draw_box(self, pid):
        window = self._process[pid].window
        window.erase()
        window.border()
        window.addstr(1, 2, self._box_status(self._process[pid]))
        window.addstr(2, 2, self._box_progress(self._process[pid]))

    def _draw_footer(self):
        self._footer.erase()
        self._footer.hline(0, 0, curses.ACS_HLINE, curses.COLS)
        self._footer.addstr(1, 1, '{0} Processes'.format(self._process_count))
        self._update_footer_time()
        if self._steps:
            self._update_footer_progress()
        self._footer.redrawwin()

    def _draw_header(self):
        self._header.erase()
        self._header.addstr(0, 1, self._title)
        self._header.hline(1, 0, curses.ACS_HLINE, self._screen_width)
        self._header.refresh()
        self._update_header_time()

    def _increment_value(self, process, value):
        with self._lock:
            process.value += float(value)
            if process.value > process.steps:
                process.value = process.steps
        self._update_box_progress(process)

    def _initialize_screen(self, screen):
        curses.curs_set(0)
        self._screen = screen
        self._screen.erase()
        self._screen.keypad(1)
        self._screen.timeout(500)
        self._header = screen.subwin(self.HEADER_HEIGHT, self._screen_width,
                                     0, 0)
        self._header.overwrite(self._screen)
        self._draw_header()
        self._footer = screen.subwin(self.FOOTER_HEIGHT, self._screen_width,
                                     self._screen_height - 2, 0)
        self._draw_footer()
        self._canvas = curses.newpad(self._canvas_height, self._screen_width)
        self._screen.refresh()

    def _keyboard_handler(self, screen, stop):
        curses.cbreak()
        curses.noecho()
        while not stop.is_set():
            cmd = screen.getch()
            if cmd == 10 or cmd < 0:
                continue
            if cmd == 115:
                self._canvas_offset += 1
                max_offset = self._canvas_vheight - self._canvas_height
                if self._canvas_offset > max_offset:
                    self._canvas_offset = max_offset
                    curses.beep()
            elif cmd == 119:
                self._canvas_offset -= 1
                if self._canvas_offset <= 0:
                    self._canvas_offset = 0
                    curses.beep()
            else:
                continue
            self._refresh_canvas()

    def _maybe_resize_canvas(self, start_y):
        canvas_height, _width = self._canvas.getmaxyx()
        if (start_y + self.BOX_HEIGHT) > canvas_height:
            new_height = canvas_height + self.BOX_HEIGHT
            self._canvas.resize(new_height, self._screen_width)

    def _on_screen_update_interval(self):
        self._update_footer_time()
        if self._steps:
            self._update_footer_progress()
        self._update_header_time()
        self._update_box_timers()
        self._refresh_canvas()
        self._screen.refresh()

    def _process_update_command(self, cmd, pid, value):
        if cmd == _INCREMENT:
            self._increment_value(self._process[pid], value)
        elif cmd == _STATUS:
            self._set_status(self._process[pid], value)
        elif cmd == _STEPS:
            self._set_steps(self._process[pid], value)
        elif cmd == _VALUE:
            self._set_value(self._process[pid], value)
        elif cmd == _APP_INCREMENT:
            self.increment_app(value)
        elif cmd == _APP_STEPS:
            self._set_app_steps(value)
        elif cmd == _RESET_PROC_START:
            self._reset_process_start(self._process[pid])

    @staticmethod
    def _progress_bar(percentage, bar_width):
        fill = int(bar_width * percentage)
        empty = bar_width - fill
        if not empty:
            return '[{0:{fill}<{width}}] {1:7.2%}'.format('', percentage,
                                                          fill='#',
                                                          width=bar_width)
        return '[{0:{fill}<{width}}{1: <{empty}}] {2:7.2%}'.format('', '',
                                                                   percentage,
                                                                   fill='#',
                                                                   width=fill,
                                                                   empty=empty)

    def _refresh_canvas(self):
        try:
            self._canvas.refresh(self._canvas_offset, 0,
                                 self.HEADER_HEIGHT, 0,
                                 self._canvas_height,
                                 self._screen_width)
        except curses.error:
            pass

    def _reset_process_start(self, process):
        with self._lock:
            process.start = time.time()
        self._update_box_status(process)

    def _set_status(self, process, value):
        with self._lock:
            process.status = value
        self._update_box_status(process)

    def _set_app_steps(self, value):
        with self._lock:
            self._steps = value
        if self._steps is not None:
            self._update_footer_progress()

    def _set_steps(self, process, value):
        with self._lock:
            process.steps = float(value)
        self._update_box_progress(process)

    def _set_value(self, process, value):
        with self._lock:
            process.value = float(value)
        self._update_box_progress(process)

    def _update_box_progress(self, process):
        process.window.addstr(2, 2, self._box_progress(process))

    def _update_box_status(self, process):
        process.window.addstr(1, 2, self._box_status(process))

    def _update_box_timers(self):
        for pid in self._process:
            self._update_box_status(self._process[pid])

    def _update_footer_progress(self):
        if not self._steps:
            return
        proc_text_len = len('{0} Processes'.format(self._process_count))
        time_text_len = len('{0: >10.1f}s'.format(time.time() - self._start))
        # Screen width - process text - timer - bar structure - padding
        width = self._screen_width - proc_text_len - time_text_len - 11 - 14
        percentage = float(self._value) / float(self._steps)
        value = self._progress_bar(percentage, width)
        start_x = int(math.floor(self._screen_width / 2) - math.floor(width/2))
        self._footer.addstr(1, start_x, value)

    def _update_footer_time(self):
        value = '{0: >10.1f}s'.format(time.time() - self._start)
        self._footer.addstr(1, self._screen_width - len(value) - 1, value)
        self._footer.refresh()

    def _update_header_time(self):
        value = self._current_display_time()
        self._header.addstr(0, self._screen_width - len(value) - 1, value)
        self._header.refresh()

    def _watch_ipc_queue(self, ipc_queue, stop):
        while not stop.is_set():
            try:
                cmd, pid, value = ipc_queue.get(True, 1)
            except (queue.Empty, ValueError):
                continue
            self._process_update_command(cmd, pid, value)

    @property
    def _box_width(self):
        return int(self._screen_width / 2)

    @property
    def _canvas_height(self):
        return self._screen_height - self.HEADER_HEIGHT - self.FOOTER_HEIGHT

    @property
    def _canvas_vheight(self):
        height, _width = self._canvas.getmaxyx()
        return height

    @property
    def _process_count(self):
        return len(self._process)

    @property
    def _progress_bar_width(self):
        return self._box_width - 14

    @property
    def _screen_height(self):
        height, _width = self._screen.getmaxyx()
        return height or curses.LINES

    @property
    def _screen_width(self):
        _height, width = self._screen.getmaxyx()
        return width or curses.COLS


if __name__ == '__main__':
    import random

    def example_runner(ipc_queue):
        # Update the processes status in its progress box
        set_status(ipc_queue, 'Running')

        # Increment the progress bar, sleeping up to one second per iteration
        for iteration in range(0, 100):
            increment(ipc_queue)
            increment_app(ipc_queue)
            time.sleep(random.random())

    processes = []

    # Create the MultiProgress instance
    steps = multiprocessing.cpu_count() * 100
    with MultiProgress('Example', steps=steps) as progress:

        # Spawn a process per CPU and append it to the list of processes
        for proc_num in range(0, multiprocessing.cpu_count()):
            processes.append(progress.new_process(example_runner))

        # Wait for the processes to run
        while any([p.is_alive() for p in processes]):
            time.sleep(1)

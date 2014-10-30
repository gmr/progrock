"""

"""
import curses
import datetime
import locale
import multiprocessing
import os
import Queue
import threading
import time


class _Interval(threading.Thread):

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

    def __init__(self, pid, process, window, start, status, steps, value):
        self.pid = pid
        self.process = process
        self.window = window
        self.start = start
        self.status = status
        self.steps = float(steps)
        self.value = float(value)


def update_status(queue, process, status, steps, value):
    queue.put((process.pid, status, steps, value))


class MultiProgress(object):
    BOX_HEIGHT = 4
    FOOTER_HEIGHT = 2
    HEADER_HEIGHT = 2
    TIME_FORMAT = '%Y-%m-%d %I:%M:%S'

    def __init__(self, title):
        locale.setlocale(locale.LC_ALL, '')
        self.update_queue = multiprocessing.Queue()
        self._canvas = None
        self._code = locale.getpreferredencoding()
        self._footer = None
        self._header = None
        self._canvas_offset = 0
        self._stop = threading.Event()
        self._process = dict()
        self._screen = None
        self._start = None
        self._title = title
        self._update_interval = _Interval(1, self._on_screen_update_interval)
        self._update_thread = threading.Thread(target=self._watch_update_queue,
                                               args=(self.update_queue,
                                                     self._stop))
        self._update_thread.daemon = True

    def __enter__(self):
        self._start = time.time()
        curses.wrapper(self._initialize_screen)
        self._keyboard_input = threading.Thread(target=self._keyboard_handler,
                                                args=(self._screen,
                                                      self._stop))
        self._keyboard_input.daemon = True
        self._keyboard_input.start()
        self._update_thread.start()
        self._update_interval.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop.set()
        self._update_interval.stop()
        curses.endwin()

    def add_process(self, pid, status='Initializing', steps=100, value=0):
        """Temporarily have pid, this really should be multiprocessing.Process

        :param pid:
        :param status:
        :param steps:
        :param value:
        :return:
        """
        start_y = (self._process_count / 2) * self.BOX_HEIGHT
        start_x = (self._process_count % 2) * (self._screen_width / 2)
        self._maybe_resize_canvas(start_y)

        try:
            window = self._canvas.subwin(self.BOX_HEIGHT, self._box_width,
                                         start_y, start_x)
        except curses.error as error:
            raise ValueError('Error creating window for pid %s (%i,%i): %s' %
                             (pid, start_y, start_x, error))

        self._process[pid] = _Process(pid, None, window, time.time(), status,
                                      steps, value)
        self._draw_box(pid)
        self._draw_footer()

    def update_process(self, pid, status=None, steps=None, value=None):
        if status:
            self._process[pid].status = status
            self._update_box_status(self._process[pid])
        if steps is not None:
            self._process[pid].steps = float(steps)
        if value is not None:
            self._process[pid].value = float(value)
            progress_bar = self._box_progress(self._process[pid])
            self._process[pid].window.addstr(2, 2, progress_bar)
        self._draw_box(pid)

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

    def _box_progress(self, process):
        percentage = process.value / process.steps
        bar_width = self._progress_bar_width
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
        self._footer.redrawwin()

    def _draw_header(self):
        self._header.erase()
        self._header.addstr(0, 1, self._title)
        self._header.hline(1, 0, curses.ACS_HLINE, self._screen_width)
        self._header.refresh()
        self._update_header_time()

    def _maybe_resize_canvas(self, start_y):
        canvas_height, _width = self._canvas.getmaxyx()
        if (start_y + self.BOX_HEIGHT) > canvas_height:
            new_height = canvas_height + self.BOX_HEIGHT
            self._canvas.resize(new_height, self._screen_width)

    def _on_screen_update_interval(self):
        self._update_footer_time()
        self._update_header_time()
        self._screen.refresh()
        self._refresh_canvas()

    def _refresh_canvas(self):
        try:
            self._canvas.refresh(self._canvas_offset, 0, self.HEADER_HEIGHT, 0,
                                 self._canvas_height,
                                 self._screen_width)
        except curses.error:
            pass

    def _update_box_status(self, process):
        process.window.addstr(1, 2, self._box_status(process))

    def _update_box_timers(self):
        for pid in self._process:
            self._update_box_status(self._process[pid])

    def _update_footer_time(self):
        value = '{0: >10.1f}s'.format(time.time() - self._start)
        self._footer.addstr(1, self._screen_width - len(value) - 1, value)
        self._footer.refresh()

    def _update_header_time(self):
        value = self._current_display_time()
        self._header.addstr(0, self._screen_width - len(value) - 1, value)
        self._header.refresh()

    def _watch_update_queue(self, update_queue, stop):
        while not stop.is_set():
            try:
                update = update_queue.get(True, 1)
            except Queue.Empty:
                continue
            self.update_process(*update)

    @property
    def _box_width(self):
        return self._screen_width / 2

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
        return height

    @property
    def _screen_width(self):
        _height, width = self._screen.getmaxyx()
        return width


if __name__ == '__main__':

    def example_runner(update_queue):
        import random
        random.seed()
        for iteration in range(0, 1001):
            time.sleep(random.random())
            update_queue.put((os.getpid(), 'Iteration #%i' % iteration, None,
                              iteration))

    processes = []
    with MultiProgress('Test Application') as ui:
        for proc_num in range(0, multiprocessing.cpu_count()):
            proc = multiprocessing.Process(target=example_runner,
                                           args=(ui.update_queue,))
            proc.start()
            ui.add_process(proc.pid, 'Starting', 1000, 0)
            processes.append(proc)

        # Wait for the processes to run
        while any([p.is_alive() for p in processes]):
            time.sleep(1)
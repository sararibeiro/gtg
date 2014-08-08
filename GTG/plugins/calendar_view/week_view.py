from gi.repository import Gtk, Gdk
import datetime

from GTG.plugins.calendar_view.week import WeekSpan
from GTG.plugins.calendar_view.drawtask import DrawTask, TASK_HEIGHT
from GTG.plugins.calendar_view.grid import Grid
from GTG.plugins.calendar_view.utils import date_to_col_coord, \
    convert_coordinates_to_col
from GTG.plugins.calendar_view.view import ViewBase


class WeekView(ViewBase):

    def __init__(self, parent, requester, numdays=7):
        super(WeekView, self).__init__(parent, requester, numdays)

        self.min_day_width = 60
        self.grid = Grid(1, self.numdays)
        numweeks = int(self.numdays/7)
        self.week = WeekSpan(numweeks)

        # Scrolled Window options
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.vadjustment = self.scroll.get_vadjustment()
        self.vadjustment.connect('changed', self.on_vadjustment_changed)

    def first_day(self):
        """ Returns the first day of the view being displayed """
        return self.week.start_date

    def last_day(self):
        """ Returns the last day of the view being displayed """
        return self.week.end_date

    def show_today(self):
        """
        Shows the range of dates in the current view with the date
        corresponding to today among it.
        """
        self.week.week_containing_day(datetime.date.today())
        self.refresh()

    def on_vadjustment_changed(self, a):
        """ Verify if the scrollbar is needed, and notifies header of that """
        if (self.vadjustment.get_page_size() == self.vadjustment.get_upper()):
            self.header.set_sidebar_size(0)
        else:
            self.header.set_sidebar_size(15)

    def compute_size(self):
        """ Computes and requests the size needed to draw everything. """
        width = self.min_day_width * self.numdays
        height = TASK_HEIGHT * self.grid.num_rows
        self.all_day_tasks.set_size_request(width, height)

    def set_week_from(self, start):
        """
        Sets the week to be shown, starting on @start.

        @param start: must be a datetime object, first day to be shown.
        """
        self.week.set_week_starting_on(start)

    def update_header(self, format="%a %m/%d"):
        """
        Updates the header label of the days to be drawn given a specific
        strftime @format, and then redraws the header. If more than one line is
        wanted to display each labels, the format must separate the content
        inteded for each line by a space.

        @param format: string, must follow the strftime convention.
         Default: "%a %m/%d" - abbrev weekday in first line,
         month/day_of_month as decimal numbers in second line.
        """
        days = self.week.label(format)
        days = [d.split() for d in days]
        self.header.set_labels(days)
        self.header.queue_draw()
        self.emit('dates-changed')

    def set_task_drawing_position(self, dtask):
        """
        Calculates and sets the position of a @dtask.

        @param dtask: a DrawingTask object.
        """
        task = self.req.get_task(dtask.get_id())

        start = max(task.get_start_date().date(), self.first_day())
        end = min(task.get_due_date().date(), self.last_day())
        duration = (end - start).days + 1

        x = date_to_col_coord(start, self.first_day())
        w = duration
        x, y, w, h = self.grid.add_to_grid(x, w, id=dtask.get_id())

        dtask.set_position(x, y, w, h)
        dtask.set_overflowing_L(self.first_day())
        dtask.set_overflowing_R(self.last_day())

    def date_range_to_string(self):
        """
        Returns the string correspoding to the days being displayed in this
        view.
        """
        start = self.first_day()
        end = self.last_day()
        start_format = "%b %d"
        end_format = "%d, %Y"
        if start.month != end.month:
            end_format = "%b " + end_format
            if start.year != end.year:
                start_format += ", %Y"
        return "%s - %s" % (start.strftime(start_format),
                            end.strftime(end_format))

    def update_drawtasks(self, tasks=None):
        """
        Updates the drawtasks and calculates the position of where each one of
        them should be drawn.

        @param tasks: a Task list, containing the tasks to be drawn.
         If none is given, the tasks will be retrieved from the requester.
        """
        def duration(task):
            return (task.get_due_date() - task.get_start_date()).days

        if not tasks:
            tasks = [self.req.get_task(t) for t in
                     self.tasktree.get_all_nodes()]
        self.tasks = [DrawTask(t) for t in tasks if t is not None and
                      self.is_in_days_range(t)]
        self.tasks.sort(key=lambda t: duration(t.task), reverse=True)

        self.grid.clear_rows()
        for t in self.tasks:
            self.set_task_drawing_position(t)
        self.all_day_tasks.set_tasks_to_draw(self.tasks)

        # clears selected_task if it is not being showed
        if self.selected_task:
            if self.req.has_task(self.selected_task):
                task = self.req.get_task(self.selected_task)
                if not self.is_in_days_range(task):
                    self.unselect_task()
            else:
                self.unselect_task()

    def highlight_today_cell(self):
        """ Highlights the cell equivalent to today."""
        row = 0
        col = date_to_col_coord(datetime.date.today(), self.first_day())
        self.all_day_tasks.set_today_cell(row, col)
        self.header.set_highlight_cell(0, col)

    def refresh(self, widget=None, dummy=None):
        """
        Updates the header, the content to be drawn (tasks), recalculates the
        size needed and then redraws everything.
        """
        self.update_drawtasks()
        self.compute_size()
        self.highlight_today_cell()
        self.update_header()
        self.all_day_tasks.queue_draw()

    def next(self, days=None):
        """
        Advances the dates being displayed by a given number of @days.
        If none is given, the default self.numdays will be used. In this case,
        if the actual first_day being shown is not at the beginning of a
        week, it will advance to the beginning of the next one instead
        of advancing @numdays.

        @param days: integer, the number of days to advance.
         If none is given, the default self.numdays will be used.
        """
        if not days:
            days = self.numdays - self.first_day().weekday()
        self.week.adjust(days)
        self.refresh()

    def previous(self, days=None):
        """
        Regresses the dates being displayed by a given number of @days.
        If none is given, the default self.numdays will be used. In this case,
        if the actual first_day being shown is not at the beginning of a
        week, it will go back to the beginning of it instead
        of going back @numdays.

        @param days: integer, the number of days to go back.
         If none is given, the default self.numdays will be used.
        """
        if not days:
            days = self.first_day().weekday() or self.numdays
        self.week.adjust(-days)
        self.refresh()

    def track_cells_to_create_new_task(self, event):
        """
        Keeps track of the range of cells between the start of the dragging
        (mouse click) and where the mouse is at the moment, in order to create
        a new task when the mouse button is released. In the meantime, the
        cells will be highlighted to show where the task will be created.

        @param event: GdkEvent object, contains the pointer coordinates.
        """
        day_width = self.get_day_width()
        curr_col = convert_coordinates_to_col(event.x, day_width)
        start_col = convert_coordinates_to_col(self.drag_offset, day_width)

        # invert cols in case user started dragging from the end date
        if curr_col < start_col:
            temp = curr_col
            curr_col = start_col
            start_col = temp
        cells = []
        for i in range(curr_col - start_col + 1):
            row = 0
            col = start_col + i
            cells.append((row, col))
        self.all_day_tasks.cells = cells
        self.all_day_tasks.queue_draw()

    def dnd_start(self, widget, event):
        """ User clicked the mouse button, starting drag and drop """
        # find which task was clicked, if any
        task_id, self.drag_action, cursor = \
            self.all_day_tasks.identify_pointed_object(event, clicked=True)
        self.set_selected_task(task_id)
        self.all_day_tasks.queue_draw()

        if self.selected_task:
            # double-click opens task to edit
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.ask_edit_task(self.selected_task)
                self.is_dragging = False
                self.drag_offset = None
                return
            task = self.req.get_task(self.selected_task)
            start = (task.get_start_date().date() - self.first_day()).days
            end = (task.get_due_date().date() - self.first_day()).days + 1
            duration = end - start

            day_width = self.get_day_width()
            offset = (start * day_width) - event.x
            # offset_y = pos * TASK_HEIGHT - event.y
            if self.drag_action == "expand_right":
                offset += duration * day_width
            self.drag_offset = offset

        # if no task is selected, save mouse location in case the user wants
        # to create a new task using DnD
        else:
            self.drag_offset = event.x

        widget.get_window().set_cursor(cursor)

    def motion_notify(self, widget, event):
        """ User moved mouse over widget """
        # dragging with no task selected: new task will be created
        if not self.selected_task and self.drag_offset:
            self.is_dragging = True
            self.track_cells_to_create_new_task(event)
            return

        if self.selected_task and self.drag_offset:  # a task was clicked
            self.is_dragging = True
            task = self.req.get_task(self.selected_task)
            start_date = task.get_start_date().date()
            end_date = task.get_due_date().date()
            duration = (end_date - start_date).days

            event_x = event.x + self.drag_offset
            # event_y = event.y

            day_width = self.get_day_width()
            col = convert_coordinates_to_col(event_x, day_width)
            day = self.first_day() + datetime.timedelta(col)

            if self.drag_action == "expand_left":
                new_start_day = day
                if new_start_day <= end_date:
                    task.set_start_date(new_start_day)

            elif self.drag_action == "expand_right":
                new_due_day = day
                if new_due_day >= start_date:
                    task.set_due_date(new_due_day)

            else:
                new_start_day = day
                new_due_day = new_start_day + datetime.timedelta(days=duration)
                task.set_start_date(new_start_day)
                task.set_due_date(new_due_day)

        else:  # mouse hover
            t_id, self.drag_action, cursor = \
                self.all_day_tasks.identify_pointed_object(event)
            widget.get_window().set_cursor(cursor)

    def dnd_stop(self, widget, event):
        """ User released a button, stopping drag and drop. """
        # dragging with no task selected: new task will be created
        if not self.selected_task and self.is_dragging:
            day_width = self.get_day_width()
            start = convert_coordinates_to_col(self.drag_offset, day_width)
            end = convert_coordinates_to_col(event.x, day_width)

            # invert cols in case user started dragging from the end date
            if start > end:
                temp = start
                start = end
                end = temp

            start_date = self.first_day() + datetime.timedelta(days=start)
            due_date = self.first_day() + datetime.timedelta(days=end)

            self.ask_add_new_task(start_date, due_date)
            self.all_day_tasks.cells = []

        # user didn't click on a task or just finished dragging task
        # in both cases, redraw to 'unselect' task
        elif not self.selected_task or self.is_dragging:
            self.unselect_task()
            self.all_day_tasks.queue_draw()

        widget.get_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.ARROW))
        self.drag_offset = None
        self.is_dragging = False
        self.drag_action = None

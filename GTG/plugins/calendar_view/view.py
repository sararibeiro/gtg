# -*- coding: utf-8 -*-
# Copyright (c) 2014 - Sara Ribeiro <sara.rmgr@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gdk, GObject
import abc
import datetime

from GTG.plugins.calendar_view.header import Header
from GTG.plugins.calendar_view.all_day_tasks import AllDayTasks


class ViewConfig:
    """
    This class contains design related configurations, such as text, lines and
    background colors, task and header sizes, font faces, etc.
    """
    font = "Courier"
    font_size = 12
    font_color = (0.35, 0.31, 0.24)
    task_font_color = (1, 1, 1)  # white

    line_color = (0.35, 0.31, 0.24, 0.15)
    line_width = 0.8
    vgrid = True
    hgrid = True

    bg_color = None
    faded_cells_color = (0.8, 0.8, 0.8, 0.6)  # light gray
    highlight_cells_color = (0.8, 0.8, 0, 0.1)  # light yellow
    today_cell_color = (1, 1, 1, 0.7)  # white
    selected_task_color = (0.8, 0.8, 0)  # yellow

    link_color = (0, 0, 255, 0.5)  # default blue link color
    label_height = 15

    header_height = 35
    min_day_width = 60
    min_week_height = 80
    task_height = 20
    padding = 1.5


class ViewBase(Gtk.VBox):
    """
    The class is an abstract class to represent a calendar view and is where
    the core work of what is being showed on the screen happens.
    This class is responsible for managing the drawing of everything inside it.
    It calculates the days and tasks to be shown, the appropriate position of
    each task, what is the selected task, etc. Multiple Views can exist at the
    same time.
    Since View is an abstract class, it can not be instantiated. Rather than
    instantiating it, a subclass needs to be created and implement all the
    abstract functions of the this base class.
    """
    __metaclass__ = abc.ABCMeta  # marks methods of this class as abstract
    __string_signal__ = (GObject.SignalFlags.RUN_FIRST, None, (str, ))
    __none_signal__ = (GObject.SignalFlags.RUN_FIRST, None, tuple())
    __gsignals__ = {'selection-changed': __string_signal__,
                    'dates-changed': __none_signal__,
                    }

    def __init__(self, parent, requester, numdays):
        super(Gtk.VBox, self).__init__()
        self.par = parent
        self.req = requester

        self.header = None

        self.numdays = numdays
        self.selected_task = None

        self.config = ViewConfig()

        self.tasktree = self.req.get_tasks_tree(
            name='calendar_view', refresh=False)
        self.req.apply_global_filter(self.tasktree, 'calendar_view')

        # Header
        self.header = Header(self.numdays)
        self.header.set_size_request(-1, self.config.header_height)
        self.pack_start(self.header, False, False, 0)

        # Scrolled Window
        self.scroll = Gtk.ScrolledWindow(None, None)
        self.scroll.add_events(Gdk.EventMask.SCROLL_MASK)
        self.scroll.connect("scroll-event", self.on_scroll)
        self.pack_start(self.scroll, True, True, 0)

        self.connect("size-allocate", self.on_size_allocate)

        # AllDayTasks widget
        self.all_day_tasks = AllDayTasks(self, cols=self.numdays)
        self.scroll.add_with_viewport(self.all_day_tasks)

        # drag-and-drop support
        self.drag_offset = None
        self.drag_action = None
        self.is_dragging = False

        # handle the AllDayTasks DnD events
        self.all_day_tasks.connect("button-press-event", self.dnd_start)
        self.all_day_tasks.connect("motion-notify-event", self.motion_notify)
        self.all_day_tasks.connect("button-release-event", self.dnd_stop)

        # callbacks to set
        self.edit_task = None
        self.add_new_task = None
        self.delete_task = None

    def on_size_allocate(self, widget=None, event=None):
        """ Handles window resizing event. """
        pass

    def update_config(self):
        """ Updates general design configurations. """
        self.all_day_tasks.add_configurations(self.config)
        self.header.add_configurations(self.config)

    def get_allocation(self):
        """ Returns drawable area allocation. Overrides default method. """
        return self.all_day_tasks.get_allocation()

    def fit_event_in_boundaries(self, event):
        """
        Checks if event coordinates are inside the delimited area and if not,
        modify them to the maximum allowed value in order to fit the area.

        @param event: GdkEvent object, contains the pointer coordinates.
        @return event: GdkEvent object, containing the new x and y coordinates.
        """
        alloc = self.get_allocation()
        event.x = min(event.x, alloc.width - 1)
        event.x = max(event.x, 0)

        event.y = min(event.y, alloc.height - 1)
        event.y = max(event.y, 0)
        return event

    def get_selected_task(self):
        """ Returns which task is being selected. """
        return self.selected_task

    def set_selected_task(self, tid):
        """
        Sets task with id @tid as the selected_task.

        @param tid: str, the id of a Task to be edited.
        """
        self.selected_task = tid
        self.all_day_tasks.selected_task = tid
        self.emit('selection-changed', tid)

    def unselect_task(self):
        """ Unselects the task that was selected before. """
        self.selected_task = None
        self.all_day_tasks.selected_task = None
        self.emit('selection-changed', None)

    def on_scroll(self, widget, event):
        """
        Callback function to deal with scrolling the drawing area window.
        If scroll right or left, change the days displayed in the calendar
        view. If scroll up or down, propagates the signal to scroll window
        normally.
        """
        # scroll right
        if event.get_scroll_deltas()[1] > 0:
            self.next(1)
        # scroll left
        elif event.get_scroll_deltas()[1] < 0:
            self.previous(1)
        # scroll up or down
        else:
            return False  # propagates signal to scroll window normally

    def get_day_width(self):
        """ Returns the day/column width in pixels """
        return self.all_day_tasks.get_day_width()

    def update_tasks(self):
        """ Updates and redraws everything related to the tasks """
        self.update_drawtasks()
        self.compute_size()
        self.all_day_tasks.queue_draw()

    @abc.abstractmethod
    def first_day(self):
        """ Returns the first day of the view being displayed """
        return

    @abc.abstractmethod
    def last_day(self):
        """ Returns the last day of the view being displayed """
        return

    @abc.abstractmethod
    def refresh(self):
        """ Refreshes all the content whenever a change is required. """
        return

    @abc.abstractmethod
    def next(self, days=None):
        """
        Advances the dates being displayed by a given number of @days.

        @param days: integer, the number of days to advance.
         If none is given, the default self.numdays will be used.
        """
        return

    @abc.abstractmethod
    def previous(self, days=None):
        """
        Regresses the dates being displayed by a given number of @days.

        @param days: integer, the number of days to go back.
         If none is given, the default self.numdays will be used.
        """
        return

    @abc.abstractmethod
    def show_today(self):
        """
        Shows the range of dates in the current view with the date
        corresponding to today among it.
        """
        return

    @abc.abstractmethod
    def date_range_to_string(self):
        """
        Returns the string correspoding to the days being displayed in this
        view.
        """
        return

    def is_in_days_range(self, task):
        """
        Returns true if the given @task have either the start or due days
        between the current first and last day being displayed.
        Useful to know if @task should be drawn in the current screen.

        @param task: a Task object
        """
        return (task.get_due_date().date() >= self.first_day()) and \
               (task.get_start_date().date() <= self.last_day())

    def is_today_being_shown(self):
        """
        Returns true if the date for today is being
        shown in the current view
        """
        today = datetime.date.today()
        return today >= self.first_day() and today <= self.last_day()

    @abc.abstractmethod
    def dnd_start(self, widget, event):
        """ User clicked the mouse button, starting drag and drop """
        return

    @abc.abstractmethod
    def motion_notify(self, widget, event):
        """ User moved mouse over widget """
        return

    @abc.abstractmethod
    def dnd_stop(self, widget, event):
        """ User released a button, stopping drag and drop. """
        return

    def edit_task_callback(self, func):
        """
        Callback function to edit a task

        @param func: the function to be called in order to edit the task
        """
        self.edit_task = func

    def new_task_callback(self, func):
        """
        Callback function to add a new task

        @param func: the function to be called in order to add the new task
        """
        self.add_new_task = func

    def delete_task_callback(self, func):
        """
        Callback function to delete a task

        @param func: the function to be called to perform the deletion
        """
        self.delete_task = func

    def ask_add_new_task(self, start_date, due_date):
        """
        Adds a new task with @start_date and @due_date, and refreshes the View.

        @param start_date: datetime object, the start date of the new Task
        @param due_date: datetime object, the due date of the new Task
        """
        new_task = self.req.new_task()
        new_task.set_start_date(start_date)
        new_task.set_due_date(due_date)
        self.add_new_task(new_task.get_id(), thisisnew=True)
        self.set_selected_task(new_task.get_id())
        self.refresh()

    def ask_edit_task(self, task_id):
        """
        Edits a task given by @task_id and refreshes the View.

        @param task_id: str, the id of a Task to be edited
        """
        self.edit_task(task_id)
        self.refresh()

    def ask_delete_task(self, task_id):
        """
        Deletes a task given by @task_id and refreshes the View.

        @param task_id: str, the id of a Task to be deleted
        """
        self.delete_task(task_id=task_id)
        self.unselect_task()
        self.refresh()

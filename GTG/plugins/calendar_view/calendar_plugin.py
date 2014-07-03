#!/usr/bin/python3
from gi.repository import Gtk, GObject
import datetime
import random
import os

from GTG.gtk.editor.editor import TaskEditor
from GTG.tools.dates import Date

from GTG.plugins.calendar_view.utils import random_color
from GTG.plugins.calendar_view.week_view import WeekView
# from GTG.plugin.calendar_view.controller import Controller
from GTG.plugins.calendar_view.taskview import TaskView

tests = True


class CalendarPlugin(GObject.GObject):
    """
    This class is a plugin to display tasks into a dedicated view, where tasks
    can be selected, edited, moved around by dragging and dropping, etc.
    """
    __string_signal__ = (GObject.SignalFlags.RUN_FIRST, None, (str, ))
    __gsignals__ = {'on_delete_task': __string_signal__,
                    }

    def __init__(self, requester):
        super(CalendarPlugin, self).__init__()

        self.req = requester
        self.first_day = self.last_day = self.numdays = None

        self.plugin_path = os.path.dirname(os.path.abspath(__file__))
        self.glade_file = os.path.join(self.plugin_path, "calendar_view.ui")

        builder = Gtk.Builder()
        builder.add_from_file(self.glade_file)
        handlers = {
            "on_window_destroy": self.close_window,
            "on_today_clicked": self.on_today_clicked,
            "on_combobox_changed": self.on_combobox_changed,
            "on_add_clicked": self.on_add_clicked,
            "on_edit_clicked": self.on_edit_clicked,
            "on_remove_clicked": self.on_remove_clicked,
            "on_next_clicked": self.on_next_clicked,
            "on_previous_clicked": self.on_previous_clicked,
            "on_statusbar_text_pushed": self.on_statusbar_text_pushed
        }
        builder.connect_signals(handlers)

        self.window = builder.get_object("window")
        self.window.__init__()
        self.window.set_title("GTG - Calendar View")
        self.window.connect("destroy", Gtk.main_quit)

        self.today_button = builder.get_object("today")
        self.header = builder.get_object("header")

        # FIXME: controller drawing content is not working
        # self.controller = Controller(self, self.req)
        # using weekview object instead for now:
        self.controller = WeekView(self, self.req)
        #self.controller.connect("on_edit_task", self.on_edit_clicked)
        #self.controller.connect("on_add_task", self.on_add_clicked)
        self.controller.connect("dates-changed", self.on_dates_changed)
        self.controller.show_today()

        vbox = builder.get_object("vbox")
        vbox.add(self.controller)
        vbox.reorder_child(self.controller, 1)

        self.combobox = builder.get_object("combobox")
        self.combobox.set_active(0)

        self.statusbar = builder.get_object("statusbar")
        self.label = builder.get_object("label")

        self.window.show_all()

    def close_window(self, arg):
        # FIXME: not working, still closes GTG main window
        self.window.hide()
        return True  # do not destroy window

    def on_statusbar_text_pushed(self, text):
        """ Adds the @text to the statusbar """
        self.label.set_text(text)
        # self.statusbar.push(0, text)

    def on_add_clicked(self, button=None, start_date=None, due_date=None):
        """
        Adds a new task, with the help of a pop-up dialog
        for entering the task title, start and due dates.
        Redraw the calendar view after the changes.
        """
        # only to make testing easier
        if tests and not start_date and not due_date:
            today = datetime.date.today()
            start = random.choice(range(today.day, 31))
            end = random.choice(range(start, 31))
            start_date = (str(today.year) + "-" + str(today.month)
                          + "-" + str(start))
            due_date = (str(today.year) + "-" + str(today.month)
                        + "-" + str(end))
        ####
        dialog = TaskView(self.window, new=True)
        dialog.set_task_title("My New Task")
        if start_date:
            dialog.set_start_date(start_date)
        if due_date:
            dialog.set_due_date(due_date)

        response = dialog.run()
        dialog.hide()
        if response == Gtk.ResponseType.OK:
            title = dialog.get_title()
            start_date = Date(dialog.get_start_date())
            due_date = Date(dialog.get_due_date())
            color = random_color()
            self.controller.add_new_task(title, start_date, due_date, color)
            self.on_statusbar_text_pushed("Added task: %s" % title)
        else:
            self.on_statusbar_text_pushed("...")

    def on_edit_clicked(self, button=None, task_id=None):
        """
        Edits the selected task, with the help of a pop-up dialog
        for modifying the task title, start and due dates.
        Redraw the calendar view after the changes.
        """
        if not task_id:
            task_id = self.controller.get_selected_task()
        task = self.req.get_task(task_id)
        if task:
            dialog = TaskView(self.window, task)
            response = dialog.run()
            dialog.hide()
            if response == Gtk.ResponseType.OK:
                title = dialog.get_title()
                start_date = dialog.get_start_date()
                due_date = dialog.get_due_date()
                is_done = dialog.get_active()
                self.controller.edit_task(task.get_id(), title,
                                          start_date, due_date, is_done)
                self.on_statusbar_text_pushed("Edited task: %s" % title)
            else:
                self.on_statusbar_text_pushed("...")

    def on_remove_clicked(self, button=None):
        """
        Removes the selected task from the datastore and redraw the
        calendar view.
        """
        task = self.req.get_task(self.controller.get_selected_task())
        if task:
            GObject.idle_add(self.emit, 'on_delete_task',
                                 task.get_id())
            self.on_statusbar_text_pushed("Deleted task: %s" %
                                          task.get_title())
        else:
            self.on_statusbar_text_pushed("...")

    def on_next_clicked(self, button, days=None):
        """ Advances the dates being displayed by a given number of @days """
        self.controller.next(days)
        self.content_update()
        self.controller.update()

    def on_previous_clicked(self, button, days=None):
        """ Regresses the dates being displayed by a given number of @days """
        self.controller.previous(days)
        self.content_update()
        self.controller.update()

    def on_today_clicked(self, button):
        """ Show the day corresponding to today """
        self.controller.show_today()
        self.content_update()

    def on_combobox_changed(self, combo):
        """
        User chose a combobox entry: change the view_type according to it
        """
        view_type = combo.get_active_text()
        # FIXME: view switch is not working, even thought objects exist
        # try Gtk.Stack for this -> needs Gnome 3.10
        # self.controller.on_view_changed(view_type)
        print("Ignoring view change for now")
        self.content_update()

    def on_dates_changed(self, widget=None):
        """ Callback to update date-related objects in main window """
        self.header.set_text(self.controller.get_current_year())
        self.today_button.set_sensitive(
            not self.controller.is_today_being_shown())

    def content_update(self):
        """ Performs all that is needed to update the content displayed """
        self.on_dates_changed()
        self.controller.update()

# If we want to test only the Plugin (outside GTG):
# from GTG.core.datastore import DataStore
# ds = DataStore()
# ds.populate()  # hard-coded tasks
# CalendarPlugin(ds.get_requester())
# Gtk.main()

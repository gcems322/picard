# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
# Copyright (C) 2006 Lukáš Lalinský
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

from PyQt4 import QtCore, QtGui
from picard import config
from picard.const import PICARD_URLS
from picard.script import ScriptParser
from picard.ui.options import OptionsPage, OptionsCheckError, register_options_page
from picard.ui.ui_options_script import Ui_ScriptingOptionsPage


DEFAULT_NUMBERED_SCRIPT_NAME = N_("My script %d")
DEFAULT_SCRIPT_NAME = N_("My script")


class TaggerScriptSyntaxHighlighter(QtGui.QSyntaxHighlighter):

    def __init__(self, document):
        QtGui.QSyntaxHighlighter.__init__(self, document)
        self.func_re = QtCore.QRegExp(r"\$(?!noop)[a-zA-Z][_a-zA-Z0-9]*\(")
        self.func_fmt = QtGui.QTextCharFormat()
        self.func_fmt.setFontWeight(QtGui.QFont.Bold)
        self.func_fmt.setForeground(QtCore.Qt.blue)
        self.var_re = QtCore.QRegExp(r"%[_a-zA-Z0-9:]*%")
        self.var_fmt = QtGui.QTextCharFormat()
        self.var_fmt.setForeground(QtCore.Qt.darkCyan)
        self.escape_re = QtCore.QRegExp(r"\\.")
        self.escape_fmt = QtGui.QTextCharFormat()
        self.escape_fmt.setForeground(QtCore.Qt.darkRed)
        self.special_re = QtCore.QRegExp(r"[^\\][(),]")
        self.special_fmt = QtGui.QTextCharFormat()
        self.special_fmt.setForeground(QtCore.Qt.blue)
        self.bracket_re = QtCore.QRegExp(r"[()]")
        self.noop_re = QtCore.QRegExp(r"\$noop\(")
        self.noop_fmt = QtGui.QTextCharFormat()
        self.noop_fmt.setFontWeight(QtGui.QFont.Bold)
        self.noop_fmt.setFontItalic(True)
        self.noop_fmt.setForeground(QtCore.Qt.darkGray)
        self.rules = [
            (self.func_re, self.func_fmt, 0, -1),
            (self.var_re, self.var_fmt, 0, 0),
            (self.escape_re, self.escape_fmt, 0, 0),
            (self.special_re, self.special_fmt, 1, -1),
        ]

    def highlightBlock(self, text):
        self.setCurrentBlockState(0)

        for expr, fmt, a, b in self.rules:
            index = expr.indexIn(text)
            while index >= 0:
                length = expr.matchedLength()
                self.setFormat(index + a, length + b, fmt)
                index = expr.indexIn(text, index + length + b)

        # Ignore everything if we're already in a noop function
        index = self.noop_re.indexIn(text) if self.previousBlockState() <= 0 else 0
        open_brackets = self.previousBlockState() if self.previousBlockState() > 0 else 0
        while index >= 0:
            next_index = self.bracket_re.indexIn(text, index)

            # Skip escaped brackets
            if (next_index > 0) and text[next_index - 1] == '\\':
                next_index += 1

            if (next_index > -1) and text[next_index] == '(':
                open_brackets += 1
            elif (next_index > -1) and text[next_index] == ')':
                open_brackets -= 1

            if (next_index > -1):
                self.setFormat(index, next_index - index + 1, self.noop_fmt)
            elif (next_index == -1) and (open_brackets > 0):
                self.setFormat(index, len(text) - index, self.noop_fmt)

            # Check for next noop operation, necessary for multiple noops in one line
            if open_brackets == 0:
                next_index = self.noop_re.indexIn(text, next_index)

            index = next_index + 1 if (next_index > -1) and (next_index < len(text)) else -1

        self.setCurrentBlockState(open_brackets)


class AdvancedScriptItem(QtGui.QWidget):
    """Custom widget for script list items"""

    _CHECKBOX_POS = 0
    _NAME_POS = 1
    _BUTTON_UP = 2
    _BUTTON_DOWN = 3
    _BUTTON_OTHER = 4

    def __init__(self, name=None, state=True, parent=None):
        super(AdvancedScriptItem, self).__init__(parent)
        layout = QtGui.QGridLayout()
        layout.setHorizontalSpacing(5)
        layout.setVerticalSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        checkbox = QtGui.QCheckBox()
        checkbox.setChecked(state)
        checkbox.setMaximumSize(QtCore.QSize(22, 22))
        layout.addWidget(checkbox, 0, self._CHECKBOX_POS)

        layout.addWidget(QtGui.QLabel(name), 0, self._NAME_POS)

        up_button = QtGui.QToolButton()
        up_button.setArrowType(QtCore.Qt.UpArrow)
        up_button.setMaximumSize(QtCore.QSize(16, 16))
        up_button.setToolTip(_("Move script up"))
        down_button = QtGui.QToolButton()
        down_button.setArrowType(QtCore.Qt.DownArrow)
        down_button.setMaximumSize(QtCore.QSize(16, 16))
        down_button.setToolTip(_("Move script down"))
        layout.addWidget(up_button, 0, self._BUTTON_UP)
        layout.addWidget(down_button, 0, self._BUTTON_DOWN)

        other_button = QtGui.QToolButton()
        other_button.setText("...")
        other_button.setAutoRaise(True)
        other_button.setMaximumSize(QtCore.QSize(16, 16))
        other_button.setToolTip(_("Other options"))
        menu = QtGui.QMenu()
        menu.addAction(_("Rename script"))
        menu.addAction(_("Remove script"))
        self.menu = menu
        other_button.setMenu(menu)
        # remove menu indicator
        other_button.setStyleSheet('QToolButton::menu-indicator { image: none; }')
        other_button.clicked.connect(other_button.showMenu)

        layout.addWidget(other_button, 0, self._BUTTON_OTHER)

    def set_up_connection(self, move_up):
        layout = self.layout()
        up = layout.itemAtPosition(0, self._BUTTON_UP).widget()
        up.clicked.connect(move_up)

    def set_down_connection(self, move_down):
        layout = self.layout()
        down = layout.itemAtPosition(0, self._BUTTON_DOWN).widget()
        down.clicked.connect(move_down)

    def set_remove_connection(self, remove):
        menu_options = self.menu.actions()
        menu_options[1].triggered.connect(remove)

    def set_rename_connection(self, rename):
        menu_options = self.menu.actions()
        menu_options[0].triggered.connect(rename)

    def set_checkbox_connection(self, check_state):
        layout = self.layout()
        checkbox = layout.itemAtPosition(0, self._CHECKBOX_POS).widget()
        checkbox.stateChanged.connect(check_state)

    def update_name(self, name):
        layout = self.layout()
        name_label = layout.itemAtPosition(0, self._NAME_POS).widget()
        name_label.setText(name)

    def checkbox_state(self):
        layout = self.layout()
        checkbox = layout.itemAtPosition(0, self._CHECKBOX_POS).widget()
        return checkbox.isChecked()


class ScriptItem:
    """Holds a script's list and text widget properties and improves readability"""
    def __init__(self, pos, name=None, enabled=True, text=""):
        self.pos = pos
        if name is None:
            self.name = _(DEFAULT_SCRIPT_NAME)
        else:
            self.name = name
        self.enabled = enabled
        self.text = text

    def get_all(self):
        # tuples used to get pickle dump of settings to work
        return (self.pos, self.name, self.enabled, self.text)


class ScriptingOptionsPage(OptionsPage):

    NAME = "scripting"
    TITLE = N_("Scripting")
    PARENT = "advanced"
    SORT_ORDER = 30
    ACTIVE = True

    options = [
        config.BoolOption("setting", "enable_tagger_scripts", False),
        config.ListOption("setting", "list_of_scripts", []),
        config.IntOption("persist", "last_selected_script_pos", 0),
    ]

    def __init__(self, parent=None):
        super(ScriptingOptionsPage, self).__init__(parent)
        self.ui = Ui_ScriptingOptionsPage()
        self.ui.setupUi(self)
        self.highlighter = TaggerScriptSyntaxHighlighter(self.ui.tagger_script.document())
        self.ui.tagger_script.textChanged.connect(self.live_update_and_check)
        self.ui.script_name.textChanged.connect(self.script_name_changed)
        self.ui.add_script.clicked.connect(self.add_to_list_of_scripts)
        self.ui.script_list.itemSelectionChanged.connect(self.script_selected)
        self.ui.tagger_script.setEnabled(False)
        self.ui.script_name.setEnabled(False)
        self.listitem_to_scriptitem = {}
        self.list_of_scripts = []
        self.last_selected_script_pos = 0

    def script_name_changed(self):
        items = self.ui.script_list.selectedItems()
        if items:
            script = self.listitem_to_scriptitem[items[0]]
            script.name = self.ui.script_name.text()
            list_widget = self.ui.script_list.itemWidget(items[0])
            list_widget.update_name(script.name)
            self.list_of_scripts[script.pos] = script.get_all()

    def script_selected(self):
        items = self.ui.script_list.selectedItems()
        if items:
            self.ui.tagger_script.setEnabled(True)
            self.ui.script_name.setEnabled(True)
            script = self.listitem_to_scriptitem[items[0]]
            self.ui.tagger_script.setText(script.text)
            self.ui.script_name.setText(script.name)
            self.last_selected_script_pos = script.pos

    def setSignals(self, list_widget, item):
        list_widget.set_up_connection(lambda: self.move_script(self.ui.script_list.row(item), 1))
        list_widget.set_down_connection(lambda: self.move_script(self.ui.script_list.row(item), -1))
        list_widget.set_remove_connection(lambda: self.remove_from_list_of_scripts(self.ui.script_list.row(item)))
        list_widget.set_checkbox_connection(lambda: self.update_check_state(item, list_widget.checkbox_state()))
        list_widget.set_rename_connection(lambda: self.rename_script(item))

    def rename_script(self, item):
        self.ui.script_list.setItemSelected(item, True)
        self.ui.script_name.setFocus()
        self.ui.script_name.selectAll()

    def update_check_state(self, item, checkbox_state):
        script = self.listitem_to_scriptitem[item]
        script.enabled = checkbox_state
        self.list_of_scripts[script.pos] = script.get_all()

    def add_to_list_of_scripts(self):
        count = self.ui.script_list.count()
        numbered_name = _(DEFAULT_NUMBERED_SCRIPT_NAME) % (count + 1)
        script = ScriptItem(pos=count, name=numbered_name)

        list_item = QtGui.QListWidgetItem()
        list_widget = AdvancedScriptItem(numbered_name)
        self.setSignals(list_widget, list_item)
        self.ui.script_list.addItem(list_item)
        self.ui.script_list.setItemWidget(list_item, list_widget)
        self.listitem_to_scriptitem[list_item] = script
        self.list_of_scripts.append(script.get_all())
        self.ui.script_list.setItemSelected(list_item, True)

    def update_script_positions(self):
        for i, script in enumerate(self.list_of_scripts):
            self.list_of_scripts[i] = (i, script[1], script[2], script[3])
            item = self.ui.script_list.item(i)
            self.listitem_to_scriptitem[item].pos = i

    def remove_from_list_of_scripts(self, row):
        item = self.ui.script_list.item(row)
        confirm_remove = QtGui.QMessageBox()
        msg = _("Are you sure you want to remove this script?")
        reply = confirm_remove.question(confirm_remove, _('Confirm Remove'), msg, QtGui.QMessageBox.Yes,
                                        QtGui.QMessageBox.No)
        if item and reply == QtGui.QMessageBox.Yes:
            item = self.ui.script_list.takeItem(row)
            script = self.listitem_to_scriptitem[item]
            del self.listitem_to_scriptitem[item]
            del self.list_of_scripts[script.pos]
            del script
            item = None
            # update positions of other items
            self.update_script_positions()
            if not self.ui.script_list:
                self.ui.tagger_script.setText("")
                self.ui.tagger_script.setEnabled(False)
                self.ui.script_name.setText("")
                self.ui.script_name.setEnabled(False)

            # update position of last_selected_script
            if row == self.last_selected_script_pos:
                self.last_selected_script_pos = 0
                # workaround to remove residue on UI
                if not self.ui.script_list.selectedItems():
                    current_item = self.ui.script_list.currentItem()
                    if current_item:
                        self.ui.script_list.setItemSelected(current_item, True)
                    else:
                        item = self.ui.script_list.item(0)
                        self.ui.script_list.setItemSelected(item, True)
            elif row < self.last_selected_script_pos:
                self.last_selected_script_pos -= 1

    def move_script(self, row, step):
        item1 = self.ui.script_list.item(row)
        item2 = self.ui.script_list.item(row - step)
        if item1 and item2:
            # make changes in the ui

            list_item = self.ui.script_list.takeItem(row)
            script = self.listitem_to_scriptitem[list_item]
            # list_widget has to be set again
            list_widget = AdvancedScriptItem(name=script.name, state=script.enabled)
            self.setSignals(list_widget, list_item)
            self.ui.script_list.insertItem(row - step, list_item)
            self.ui.script_list.setItemWidget(list_item, list_widget)

            # make changes in the picklable list

            script1 = self.listitem_to_scriptitem[item1]
            script2 = self.listitem_to_scriptitem[item2]
            # workaround since tuples are immutable
            indices = script1.pos, script2.pos
            self.list_of_scripts = [i for j, i in enumerate(self.list_of_scripts) if j not in indices]
            new_script1 = (script1.pos - step, script1.name, script1.enabled, script1.text)
            new_script2 = (script2.pos + step, script2.name, script2.enabled, script2.text)
            self.list_of_scripts.append(new_script1)
            self.list_of_scripts.append(new_script2)
            self.list_of_scripts = sorted(self.list_of_scripts, key=lambda x: x[0])
            # corresponding mapping support also has to be updated
            self.listitem_to_scriptitem[item1] = ScriptItem(script1.pos - step, script1.name, script1.enabled,
                                                            script1.text)
            self.listitem_to_scriptitem[item2] = ScriptItem(script2.pos + step, script2.name, script2.enabled,
                                                            script2.text)

    def live_update_and_check(self):
        items = self.ui.script_list.selectedItems()
        if items:
            script = self.listitem_to_scriptitem[items[0]]
            script.text = self.ui.tagger_script.toPlainText()
            self.list_of_scripts[script.pos] = script.get_all()
        self.ui.script_error.setStyleSheet("")
        self.ui.script_error.setText("")
        try:
            self.check()
        except OptionsCheckError as e:
            self.ui.script_error.setStyleSheet(self.STYLESHEET_ERROR)
            self.ui.script_error.setText(e.info)
            return

    def check(self):
        parser = ScriptParser()
        try:
            parser.eval(unicode(self.ui.tagger_script.toPlainText()))
        except Exception as e:
            raise OptionsCheckError(_("Script Error"), str(e))

    def load(self):
        self.ui.enable_tagger_scripts.setChecked(config.setting["enable_tagger_scripts"])
        self.list_of_scripts = config.setting["list_of_scripts"]
        for s_pos, s_name, s_enabled, s_text in self.list_of_scripts:
            script = ScriptItem(s_pos, s_name, s_enabled, s_text)
            list_item = QtGui.QListWidgetItem()
            list_widget = AdvancedScriptItem(name=s_name, state=s_enabled)
            self.setSignals(list_widget, list_item)
            self.ui.script_list.addItem(list_item)
            self.ui.script_list.setItemWidget(list_item, list_widget)
            self.listitem_to_scriptitem[list_item] = script

        # Select the last selected script item
        self.last_selected_script_pos = config.persist["last_selected_script_pos"]
        last_selected_script = self.ui.script_list.item(self.last_selected_script_pos)
        if last_selected_script:
            self.ui.script_list.setItemSelected(last_selected_script, True)

        args = {
            "picard-doc-scripting-url": PICARD_URLS['doc_scripting'],
        }
        text = _(u'<a href="%(picard-doc-scripting-url)s">Open Scripting'
                 ' Documentation in your browser</a>') % args
        self.ui.scripting_doc_link.setText(text)

    def save(self):
        config.setting["enable_tagger_scripts"] = self.ui.enable_tagger_scripts.isChecked()
        config.setting["list_of_scripts"] = self.list_of_scripts
        config.persist["last_selected_script_pos"] = self.last_selected_script_pos

    def display_error(self, error):
        pass


register_options_page(ScriptingOptionsPage)

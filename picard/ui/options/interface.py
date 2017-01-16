# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
# Copyright (C) 2007 Lukáš Lalinský
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

import os.path
from functools import partial
from PyQt4 import QtCore, QtGui
from picard import config
from picard.ui.options import OptionsPage, register_options_page
from picard.ui.ui_options_interface import Ui_InterfaceOptionsPage
from picard.ui.util import enabledSlot
from picard.const import UI_LANGUAGES
import operator
import locale


class InterfaceOptionsPage(OptionsPage):

    NAME = "interface"
    TITLE = N_("User Interface")
    PARENT = "advanced"
    SORT_ORDER = 40
    ACTIVE = True
    SEPERATOR = u'-'*10
    TOOLBAR_BUTTONS = {'add_directory': N_(u'Add Folder'),
                       'add_files': N_(u'Add Files'),
                       'cluster': N_(u'Cluster'),
                       'autotag': N_(u'Lookup'),
                       'analyze': N_(u'Scan'),
                       'browser_lookup': N_(u'Lookup in Browser'),
                       'save': N_(u'Save'),
                       'view_info': N_(u'Info'),
                       'remove': N_(u'Remove'),
                       'submit': N_(u'Submit AcoustIDs'),
                       'play_file': N_(u'Open in Player'),
                       'cd_lookup': N_(u'Lookup CD...')
                       }
    options = [
        config.BoolOption("setting", "toolbar_show_labels", True),
        config.BoolOption("setting", "toolbar_multiselect", False),
        config.BoolOption("setting", "builtin_search", False),
        config.BoolOption("setting", "use_adv_search_syntax", False),
        config.BoolOption("setting", "quit_confirmation", True),
        config.TextOption("setting", "ui_language", u""),
        config.BoolOption("setting", "starting_directory", False),
        config.TextOption("setting", "starting_directory_path", ""),
        config.ListOption("setting", "toolbar_layout", [
            'add_directory', 'add_files', 'seperator', 'cluster', 'seperator',
            'autotag', 'analyze', 'browser_lookup', 'seperator',
            'save', 'view_info', 'remove', 'seperator',
            'submit', 'seperator', 'play_file', 'seperator', 'cd_lookup']),
    ]

    def __init__(self, parent=None):
        super(InterfaceOptionsPage, self).__init__(parent)
        self.ui = Ui_InterfaceOptionsPage()
        self.ui.setupUi(self)
        self.ui.ui_language.addItem(_('System default'), '')
        language_list = [(l[0], l[1], _(l[2])) for l in UI_LANGUAGES]
        for lang_code, native, translation in sorted(language_list, key=operator.itemgetter(2),
                                                     cmp=locale.strcoll):
            if native and native != translation:
                name = u'%s (%s)' % (translation, native)
            else:
                name = translation
            self.ui.ui_language.addItem(name, lang_code)
        self.ui.starting_directory.stateChanged.connect(
            partial(
                enabledSlot,
                self.ui.starting_directory_path.setEnabled
            )
        )
        self.ui.starting_directory.stateChanged.connect(
            partial(
                enabledSlot,
                self.ui.starting_directory_browse.setEnabled
            )
        )
        self.ui.starting_directory_browse.clicked.connect(self.starting_directory_browse)
        self.ui.add_button.clicked.connect(self.add_to_toolbar)


    def load(self):
        self.ui.toolbar_show_labels.setChecked(config.setting["toolbar_show_labels"])
        self.ui.toolbar_multiselect.setChecked(config.setting["toolbar_multiselect"])
        self.ui.builtin_search.setChecked(config.setting["builtin_search"])
        self.ui.use_adv_search_syntax.setChecked(config.setting["use_adv_search_syntax"])
        self.ui.quit_confirmation.setChecked(config.setting["quit_confirmation"])
        current_ui_language = config.setting["ui_language"]
        self.ui.ui_language.setCurrentIndex(self.ui.ui_language.findData(current_ui_language))
        self.ui.starting_directory.setChecked(config.setting["starting_directory"])
        self.ui.starting_directory_path.setText(config.setting["starting_directory_path"])
        self.populate_action_list()

    def save(self):
        config.setting["toolbar_show_labels"] = self.ui.toolbar_show_labels.isChecked()
        config.setting["toolbar_multiselect"] = self.ui.toolbar_multiselect.isChecked()
        config.setting["builtin_search"] = self.ui.builtin_search.isChecked()
        config.setting["use_adv_search_syntax"] = self.ui.use_adv_search_syntax.isChecked()
        config.setting["quit_confirmation"] = self.ui.quit_confirmation.isChecked()
        self.tagger.window.update_toolbar_style()
        new_language = self.ui.ui_language.itemData(self.ui.ui_language.currentIndex())
        if new_language != config.setting["ui_language"]:
            config.setting["ui_language"] = self.ui.ui_language.itemData(self.ui.ui_language.currentIndex())
            dialog = QtGui.QMessageBox(
                QtGui.QMessageBox.Information,
                _('Language changed'),
                _('You have changed the interface language. You have to restart Picard in order for the change to take effect.'),
                QtGui.QMessageBox.Ok,
                self)
            dialog.exec_()
        config.setting["starting_directory"] = self.ui.starting_directory.isChecked()
        config.setting["starting_directory_path"] = os.path.normpath(unicode(self.ui.starting_directory_path.text()))

    def starting_directory_browse(self):
        item = self.ui.starting_directory_path
        path = QtGui.QFileDialog.getExistingDirectory(self, "", item.text())
        if path:
            path = os.path.normpath(unicode(path))
            item.setText(path)

    def populate_action_list(self):
        self.ui.toolbar_layout_list.setDragDropMode(QtGui.QAbstractItemView.DragDrop)
        self.ui.toolbar_layout_list.setDefaultDropAction(QtCore.Qt.MoveAction)
        for name in config.setting['toolbar_layout']:
            if name in self.TOOLBAR_BUTTONS.keys():
                self._insert_item(self.TOOLBAR_BUTTONS[name])
            else:
                self._insert_item(self.SEPERATOR)

    def _insert_item(self, action, index=None):
        list_item = QtGui.QListWidgetItem(action)
        list_item.setToolTip(_(u'Drag and Drop to re-order'))
        if index:
            self.ui.toolbar_layout_list.insertItem(index, list_item)
        else:
            self.ui.toolbar_layout_list.addItem(list_item)
        return list_item

    def add_to_toolbar(self):
        added_items = self._added_actions()
        display_list = list(set.difference(self.ACTION_NAMES, added_items))
        action, ok = QtGui.QInputDialog.getItem(self, "Add Action", "Select an Action:", display_list)
        if ok:
            list_item = self._insert_item(action)
            self.ui.toolbar_layout_list.setCurrentItem(list_item)


register_options_page(InterfaceOptionsPage)

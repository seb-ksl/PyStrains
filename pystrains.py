#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  pystrains.py
#  
#  Copyright 2013-2014 seb-ksl <seb@gelis.ch>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, see <http://www.gnu.org/licenses/>.
#  
#

# FixMe: Import : réguler erreur (XLRDError) si fichier pas format Excel (xlrd plante)
# ToDo: gestion des utilisateurs avec des droits
# ToDo: fusion Create de FirstRun et DB ?
# ToDo: when a strain is copied, add as a note "strain copied from strain #"

# ToDo: créer une classe pour instancier des objets récurrents : les boutons "send" et "reset"
# ToDo: cacher dossier bak
# ToDo: Import : au moment du clic sur OK, créer 2 threads : un progress et un qui importe réellement. Celui qui importe fait appel au thread progress
# ToDo: log des actions sur la DB, auquel seul admin a accès
# ToDo: Auto-complétion dans NewEditEntry avec source = treeview
# ToDo: tooltip header mode
# ToDo: export CSV
# ToDo: en import header mode, ignorer l'ordre des colonnes, se servir du header (lire le header, déterminer l'ordre des colonnes, et ensuite retrier chaque row selon cet ordre)
# ToDo: couleurs en fonction de l'espèce (réglable dans futures versions ?)
# FixMe: après erreur, le filechooserdialog ne fonctionne plus. Réguler avec try ?

import sys                                          # Various system related methods
# Add the PyStrains lib directory to the system path,
# so the next imports will look for modules in this directory as well.
sys.path.append('/usr/lib/pystrains')
from gi.repository import Gtk                       # User interface
from hashlib import sha256
from xlrd import open_workbook, xldate_as_tuple     # Read data in Excel format
import os                                           # Various system related methods
import datetime                                     # Used here to get today's date
import sqlite3                                      # SQLite interface
import shutil                                       # High-level file management


class Glob(object):
    
    headers = [('Index', 'i'),('Experimentator','s'),('Box','i'),('Tube','i'),('Strain','s'),('Genome','s'),('Plasmid','s'),('Antibiotics','s'),('Date','s'),('Notes','s'),('Sequenced','i')]
    dbfile = ""
    bakpath = ""
    bakname = str(datetime.date.today())
    write_permission = 0
    number_of_tables = 3        # Used when db validity is checked. Current 2 tables are "strains" and "who_is_where".
    isadmin = False

    @staticmethod
    def set_var(var, var_value):
        if var == "dbfile": Glob.dbfile = var_value
        if var == "bakpath": Glob.bakpath = var_value
        if var == "bakname": Glob.bakname = var_value
        print("DB File=",Glob.dbfile)
        f = open(".pystrains.conf","w")
        f.write(Glob.dbfile)
        f.close()

    @staticmethod
    def locate_db():
        f = open('.pystrains.conf')
        line = f.readline()
        f.close()
        dbfile = line.split("\n")       # Because line ends with a \n we do not want.
        Glob.dbfile = dbfile[0]         # dbfile[0] = actual DB file, and dbfile[1] = ""
        Glob.bakpath = os.path.join(os.path.dirname(dbfile[0]),"bak")

    @staticmethod
    def encrypt(plain):
        return sha256(plain).hexdigest()


class DB(object):
    def __init__(self):
        try:
            f = open(Glob.dbfile)
        except:
            self.error = True
            Error(None, "Database file could not be found.")
        else:
            self.connect()
            if self.db_is_valid():
                self.error = False
            else:
                self.error = True
                self.cur.close()
                self.conn.close()
                Error(None, "Database file is not valid.")

    def connect(self):
        self.conn = sqlite3.connect(Glob.dbfile)
        self.cur = self.conn.cursor()

    def db_is_valid(self):
        try:
            self.cur.execute("SELECT * FROM SQLITE_MASTER")     # SQLITE_MASTER is a master table that lists all tables and their characteristics
        except:
            return False
        else:
            db_tables = list(self.cur)
            if len(db_tables) == Glob.number_of_tables:
                if db_tables[0][1] == "strains":
                    return True
                else:
                    return False
            else:
                return False

    @staticmethod
    def test_write():
        try:
            f = open(Glob.dbfile,"a")    # Try to open the DB in "append" mode (DO NOT TRY WRITE MODE: that would clear DB file, of course).
        except:
            Glob.write_permission = 0
            Error(None,"Database could not be opened in write-mode\nPlease make sure that you are allowed to write in file\n"+Glob.dbfile+".")
        else:
            Glob.write_permission = 1
            
    def create(self,newdbfile):
        print("Creating new DB at:",newdbfile + ".")
        Glob.dbfile = newdbfile
        self.connect()
        request = "CREATE TABLE strains (StrainNumber INTEGER, Experimentator TEXT, Box INTEGER, Tube INTEGER, STRAIN TEXT, Genome TEXT, Plasmid TEXT, Antibiotics TEXT, Date TEXT, Notes TEXT, Sequenced INTEGER)"
        self.cur.execute(request)
        request = "CREATE TABLE who_is_where (Who TEXT, IsWhere TEXT)"
        self.cur.execute(request)
        request = "CREATE TABLE users (user TEXT, pwd TEXT)"
        self.cur.execute(request)
        
    def read(self):
        self.cur.execute("SELECT * FROM strains")
        return list(self.cur)

    def read_users(self):
        self.cur.execute("SELECT * FROM users")
        return list(self.cur)
        
    def read_who_where(self):
        self.cur.execute("SELECT * FROM who_is_where")
        return list(self.cur)
        
    def read_max(self):
        max_ = list(self.cur.execute("SELECT MAX(StrainNumber) from strains"))
        if max_[0][0] is None:
            return 0
        else:
            return max_[0][0]

    def read_min(self):
        min_ = list(self.cur.execute("SELECT MIN(StrainNumber) from strains"))
        if min_[0][0] is None:
            return 0
        else:
            return min_[0][0]
        
    def insert(self,strainnumber,data):
        if data[0] != "" and data[1] != "" and data[2] != "":    # Keep this check for imported data, checks that there is at least "experimentator", "box", "tube".
            try:
                request = 'INSERT INTO strains VALUES({0},"{1[0]}",{1[1]},{1[2]},"{1[3]}","{1[4]}","{1[5]}","{1[6]}","{1[7]}","{1[8]}","{1[9]}")'
                self.cur.execute(request.format(strainnumber,data))        # Format the request inserting 1)an index superior to last item and 2)all the data entered in the creation form
                self.conn.commit()
            except:
                print("Insertion error:\nThis row could not be inserted:\n",data)
        else:
            print("Insertion error:\nThis row could not be inserted because mandatory fields were not filled up:\n",data)
    
    def insert_whowhere(self,who,where):
        try:
            request = 'INSERT INTO who_is_where VALUES("{0}","{1}")'
            self.cur.execute(request.format(who,where))
            self.conn.commit()
        except:
            print('Insertion error:\nThis row could not be inserted:',who,";",where)
    
    def edit(self,rowtoedit,data):
        request = 'UPDATE strains SET Experimentator="{0[0]}", Box="{0[1]}", Tube="{0[2]}", Strain="{0[3]}", Genome="{0[4]}", Plasmid="{0[5]}",Antibiotics="{0[6]}", Date="{0[7]}", Notes="{0[8]}", Sequenced={0[9]} WHERE StrainNumber={1}'
        self.cur.execute(request.format(data,rowtoedit))
        self.conn.commit()
        
    def del_(self,data):
        request = "DELETE FROM strains WHERE StrainNumber={}"
        self.cur.execute(request.format(data))
        self.conn.commit()
    
    def del_whowhere(self,data):
        request = 'DELETE FROM who_is_where WHERE IsWhere="{}"'
        self.cur.execute(request.format(data))
        self.conn.commit()

    def quick_filter(self, data):

        if len(data) > 0:

            for word in data:
                i = data.index(word)

                if i == 0 :
                    request = "SELECT * FROM strains WHERE (LOWER(Experimentator) LIKE LOWER('%{0[0]}%') OR LOWER(Box) LIKE LOWER('%{0[0]}%') OR LOWER(Tube) LIKE LOWER('%{0[0]}%') OR LOWER(Strain) LIKE LOWER('%{0[0]}%') OR LOWER(Genome) LIKE LOWER('%{0[0]}%') OR LOWER(Plasmid) LIKE LOWER('%{0[0]}%') OR LOWER(Antibiotics) LIKE LOWER('%{0[0]}%') OR LOWER(Date) LIKE LOWER('%{0[0]}%') OR LOWER(Notes) LIKE LOWER('%{0[0]}%') OR LOWER(Sequenced) LIKE LOWER('%{0[0]}%'))"
                else:
                    requestadd = "AND (LOWER(Experimentator) LIKE LOWER('%{0}%') OR LOWER(Box) LIKE LOWER('%{0}%') OR LOWER(Tube) LIKE LOWER('%{0}%') OR LOWER(Strain) LIKE LOWER('%{0}%') OR LOWER(Genome) LIKE LOWER('%{0}%') OR LOWER(Plasmid) LIKE LOWER('%{0}%') OR LOWER(Antibiotics) LIKE LOWER('%{0}%') OR LOWER(Date) LIKE LOWER('%{0}%') OR LOWER(Notes) LIKE LOWER('%{0}%') OR LOWER(Sequenced) LIKE LOWER('%{0}%'))"
                    requestadd = requestadd.format("{0[" + str(i) + "]}")
                    request += requestadd

            request += ";"
            request = request.format(data)
            self.cur.execute(request)
            return list(self.cur)

        else:

            return []
        
    def filter(self,data):
        request = "SELECT * FROM strains WHERE "
        for key in data.keys():
            request = request + "LOWER(" + str(key) + ")" + " LIKE " + "LOWER('%" + str(data[key]) + "%') AND "
        request = request[:-5]
        self.cur.execute(request)
        return list(self.cur)


class AskAdmin(Gtk.Window):
    def __init__(self, parent):
        Gtk.Window.__init__(self, title="Admin rights required")
        self.parent = parent
        self.connect("key-press-event",self.on_key_press)
        self.set_resizable(False)
        self.set_default_size(200, 200)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        self.add(grid)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.entry_pwd = Gtk.Entry(visibility=False)

        button_ok = Gtk.Button(self,stock='gtk-ok')
        button_ok.connect('clicked',self.ok)
        button_cancel = Gtk.Button(self,stock='gtk-cancel')
        button_cancel.connect('clicked',self.quit)

        grid.add(self.entry_pwd)
        grid.attach_next_to(button_ok, self.entry_pwd, Gtk.PositionType.BOTTOM, 1, 1)
        grid.attach_next_to(button_cancel, button_ok, Gtk.PositionType.RIGHT, 1, 1)

    def ok(self, *args):
        if True:
            Glob.isadmin = True
        self.quit()

    def on_key_press(self,widget,event):
        if event.keyval == 65293 or event.keyval == 65421:
            self.ok()
        if event.keyval == 65307:
            self.quit(self)

    def quit(self, *args):
        self.hide()


class StrainBook(Gtk.Window):
    """Main class that handles the main window and dispatches requests to daughter windows"""
    def __init__(self):
        Gtk.Window.__init__(self, title="PyStrains")
        self.set_resizable(True)
        self.set_has_resize_grip(False)
        
        self.grid = Gtk.Grid()
        self.add(self.grid)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.spinner = Gtk.Spinner()
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_width(700)
        scroll.set_min_content_height(400)
        
        self.make_menu()
        self.grid.add(self.menu)
        
        self.init_db()

        self.liststore = Gtk.ListStore(int, str, int, int, str, str, str, str, str, str, str)
            
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.set_hexpand(True)
        self.treeview.set_vexpand(True)
        self.treeview.set_rules_hint(True)    # To alternate background colors
        
        self.renderer_text = Gtk.CellRendererText()
        
        scroll.add(self.treeview)
        
        self.treeview.connect("button-press-event",self.on_treeview_click)
        
        self.grid.attach_next_to(scroll,self.menu,Gtk.PositionType.BOTTOM,1,1)
        self.grid.attach_next_to(self.spinner,self.menu,Gtk.PositionType.RIGHT,1,1)

        if not self.db.error:
            self.init_treeview()
            self.refresh()
            self.backup()

    def init_treeview(self):
        self.liststore.clear()
        i = 0
        while i < len(Glob.headers):
            columntitle = Gtk.TreeViewColumn(Glob.headers[i][0], self.renderer_text, text=i)
            columntitle.set_alignment(0.5)    # 0 = left, 0.5 = center, 1 = right
            self.treeview.append_column(columntitle)
            i=i+1
    
    def backup(self):
        
        if not os.path.isdir(Glob.bakpath):
            try:
                os.mkdir(Glob.bakpath)
            except:
                Error(self, "Could not create backup folder on server.\nPlease check that you are allowed to write in\n" + Glob.bakpath + ".")
        
        ### If there is more than 20 backups, remove the oldest one before backing up
        ls = os.listdir(Glob.bakpath)
        ls.sort()
        if len(ls) > 20:
            try:
                os.remove(os.path.join(Glob.bakpath,ls[0]))
            except:
                print("Could not remove old database file.\nPlease check that you are allowed to write in\n"+Glob.bakpath+".")
        
        try:
            shutil.copy2(Glob.dbfile,os.path.join(Glob.bakpath,Glob.bakname))
        except:
            Error(self,"Could not backup database.\nPlease check that you are allowed to write in\n"+Glob.bakpath+".")
        else:
            return 1
    
    def restore(self,menu):
        dialog_open = Gtk.FileChooserDialog("Please choose a database file",self,Gtk.FileChooserAction.OPEN,(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog_open.set_current_folder(Glob.bakpath)
        
        choice = dialog_open.run()
        if choice == Gtk.ResponseType.OK:
            dialog_sure = Gtk.MessageDialog(self,Gtk.DialogFlags.DESTROY_WITH_PARENT,Gtk.MessageType.QUESTION,Gtk.ButtonsType.YES_NO,"Are you sure you want to restore database from backup?\nBackup date is: " + dialog_open.get_filename().split("/")[-1])
            choice_sure = dialog_sure.run()
            if choice_sure == Gtk.ResponseType.YES:
                shutil.copy2(dialog_open.get_filename(),Glob.dbfile)
                os.execl(sys.executable, sys.executable, * sys.argv)
                dialog_sure.destroy()
            elif choice_sure == Gtk.ResponseType.NO:
                dialog_sure.destroy()
        elif choice == Gtk.ResponseType.CANCEL:
            dialog_open.destroy()
            
        dialog_open.destroy()
        
    def init_db(self):
        self.db = DB()
        if not self.db.error:
            self.db.test_write()
        
    def refresh(self,filter=None,data=None):
        self.liststore.clear()
        if not self.db.error:
            if filter == "complex" and len(data) != 0:
                for row in self.db.filter(data):
                    # Transform tuple into list to make it editable
                    row = list(row)
                    # Format sequencing results and add the row
                    if row[10] == 0: row[10] = ""
                    if row[10] == 1: row[10] = "Passed"
                    if row[10] == -1: row[10] = "Failed"
                    self.liststore.append(row)
            elif filter == "quick":
                for row in self.db.quick_filter(data):
                    # Transform tuple into list to make it editable
                    row = list(row)
                    # Format sequencing results and add the row
                    if row[10] == 0: row[10] = ""
                    if row[10] == 1: row[10] = "Passed"
                    if row[10] == -1: row[10] = "Failed"
                    self.liststore.append(row)
            else:
                for row in self.db.read():
                    # Transform tuple into list to make it editable
                    row = list(row)
                    # Format sequencing results and add the row
                    if row[10] == 0: row[10] = ""
                    if row[10] == 1: row[10] = "Passed"
                    if row[10] == -1: row[10] = "Failed"
                    self.liststore.append(row)
            
    def make_menu(self):
        self.menu = Gtk.MenuBar()
        
        # Acceleration groups required for Ctrl+? shortcuts
        agr = Gtk.AccelGroup()
        self.add_accel_group(agr)
        
        ### Main menus ###
        menu_button_file = Gtk.MenuItem(use_underline=True,label='_File')
        menu_file = Gtk.Menu()
        menu_button_file.set_submenu(menu_file)
        
        menu_button_edit = Gtk.MenuItem(use_underline=True,label='_Edit')
        menu_edit = Gtk.Menu()
        menu_button_edit.set_submenu(menu_edit)
        
        menu_button_view = Gtk.MenuItem(use_underline=True,label='_View')
        menu_view = Gtk.Menu()
        menu_button_view.set_submenu(menu_view)
        
        menu_button_question = Gtk.MenuItem(use_underline=True,label='_?')
        menu_question = Gtk.Menu()
        menu_button_question.set_submenu(menu_question)
        
        ### Menu Items ###
        # File #
        menu_newdb = Gtk.MenuItem('Create new database')
        menu_newdb.connect('activate', self.new_db)
        menu_file.append(menu_newdb)
        
        menu_restore = Gtk.MenuItem('Restore backup')
        menu_restore.connect('activate', self.restore)
        menu_file.append(menu_restore)
        
        menu_file.append(Gtk.SeparatorMenuItem())
        
        menu_import = Gtk.MenuItem('Import strains from Excel')
        menu_import.connect('activate', self.show_import)
        menu_file.append(menu_import)
                
        menu_file.append(Gtk.SeparatorMenuItem())
        
        menu_exit = Gtk.ImageMenuItem.new_from_stock('gtk-quit',agr)
        menu_exit.connect('activate', self.quit)
        menu_file.append(menu_exit)
        
        # Edit #
        menu_createentry = Gtk.MenuItem('Create entry')
        menu_createentry.connect('activate', self.show_newentry)
        key, mod = Gtk.accelerator_parse("<Control>N")
        menu_createentry.add_accelerator("activate",agr,key,mod,Gtk.AccelFlags.VISIBLE)
        menu_edit.append(menu_createentry)
        
        menu_copyentry = Gtk.MenuItem('Copy entry')
        menu_copyentry.connect('activate',self.copy_entry)
        key, mod = Gtk.accelerator_parse("<Control>C")
        menu_copyentry.add_accelerator("activate",agr,key,mod,Gtk.AccelFlags.VISIBLE)
        menu_edit.append(menu_copyentry)

        menu_editentry = Gtk.MenuItem('Edit entry')
        menu_editentry.connect('activate',self.show_editentry)
        key, mod = Gtk.accelerator_parse("<Control>E")
        menu_editentry.add_accelerator("activate",agr,key,mod,Gtk.AccelFlags.VISIBLE)
        menu_edit.append(menu_editentry)
        
        menu_delentry = Gtk.MenuItem('Delete entry')
        menu_delentry.connect('activate',self.del_entry)
        key, mod = Gtk.accelerator_parse("<Control>D")
        menu_delentry.add_accelerator("activate",agr,key,mod,Gtk.AccelFlags.VISIBLE)
        menu_edit.append(menu_delentry)
        
        menu_delbatch = Gtk.MenuItem('Delete multiple entries')
        menu_delbatch.connect('activate',self.show_delbatch)
        menu_edit.append(menu_delbatch)
        
        menu_edit.append(Gtk.SeparatorMenuItem())

        menu_settings = Gtk.MenuItem('Users')
        menu_settings.connect('activate',self.show_users)
        menu_edit.append(menu_settings)

        menu_settings = Gtk.ImageMenuItem.new_from_stock('gtk-preferences',agr)
        menu_settings.connect('activate',self.show_settings)
        menu_edit.append(menu_settings)
        
        # View #
        menu_quickfilterentry = Gtk.MenuItem('Quick Filter')
        menu_quickfilterentry.connect('activate',self.show_quickfilter)
        key, mod = Gtk.accelerator_parse("<Control>F")
        menu_quickfilterentry.add_accelerator("activate",agr,key,mod,Gtk.AccelFlags.VISIBLE)
        menu_view.append(menu_quickfilterentry)

        menu_filterentry = Gtk.MenuItem('Filter')
        menu_filterentry.connect('activate',self.show_filter)
        key, mod = Gtk.accelerator_parse("<Control>G")
        menu_filterentry.add_accelerator("activate",agr,key,mod,Gtk.AccelFlags.VISIBLE)
        menu_view.append(menu_filterentry)
        
        menu_showall = Gtk.MenuItem('Show All')
        menu_showall.connect('activate',self.refresh)
        key, mod = Gtk.accelerator_parse("<Control>R")
        menu_showall.add_accelerator("activate",agr,key,mod,Gtk.AccelFlags.VISIBLE)
        menu_view.append(menu_showall)
        
        menu_whoiswhere = Gtk.MenuItem('Who is where?')
        menu_whoiswhere.connect('activate',self.show_whoiswhere)
        menu_view.append(menu_whoiswhere)
        
        menu_view.append(Gtk.SeparatorMenuItem())
        
        menu_fullscreen = Gtk.CheckMenuItem("Fullscreen")
        menu_fullscreen.connect("activate",self.on_fullscreen_checkmenu)
        key, mod = Gtk.accelerator_parse("F11")
        menu_fullscreen.add_accelerator("activate",agr,key,mod,Gtk.AccelFlags.VISIBLE)
        menu_view.append(menu_fullscreen)
        
        # ? #
        menu_about = Gtk.ImageMenuItem.new_from_stock('gtk-help',agr)
        menu_about.connect('activate',self.show_help)
        menu_question.append(menu_about)
        
        menu_about = Gtk.ImageMenuItem.new_from_stock('gtk-about',agr)
        menu_about.connect('activate',self.show_about)
        menu_question.append(menu_about)
        
        ### Connect menus ###
        self.menu.append(menu_button_file)
        self.menu.append(menu_button_edit)
        self.menu.append(menu_button_view)
        self.menu.append(menu_button_question)
        
        ### Popup menu ###
        self.popmenu = Gtk.Menu()
        popmenu_copyentry = Gtk.MenuItem('Copy entry')
        popmenu_copyentry.connect('activate',self.copy_entry)
        popmenu_editentry = Gtk.MenuItem('Edit entry')
        popmenu_editentry.connect('activate',self.show_editentry)
        popmenu_delentry = Gtk.MenuItem('Delete entry')
        popmenu_delentry.connect('activate',self.del_entry)
        self.popmenu.append(popmenu_copyentry)
        self.popmenu.append(popmenu_editentry)
        self.popmenu.append(popmenu_delentry)
        self.popmenu.show_all()
    
    def on_treeview_click(self,widget=None,event=None):
        if event.button == 3:
            path = self.treeview.get_path_at_pos(event.x,event.y)    # Determines what row is under the cursor. path[0] is the row number, path[1] is the column, path[3] is cell(x) and path[4] is cell(y)
            if path is not None:
                self.treeview.grab_focus()    # Sets keyboard focus to treeview
                self.treeview.set_cursor(path[0],path[1],0)    # Sets keyboard focus to the right row and column
                self.popmenu.popup(None,None,None,None,event.button,event.time)
                model,row = self.treeview.get_selection().get_selected()
    
    def on_fullscreen_checkmenu(self,widget):
        if widget.get_active():
            self.fullscreen()
        else:
            self.unfullscreen()
        
    def new_db(self,parent):
        dialog_save = Gtk.FileChooserDialog("Create new database", self,Gtk.FileChooserAction.SAVE,(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,Gtk.STOCK_SAVE, Gtk.ResponseType.OK),do_overwrite_confirmation=True)
        dialog_save.set_create_folders(True)
        choice = dialog_save.run()
        if choice == Gtk.ResponseType.OK:
            newdbfile = dialog_save.get_filename()
            if newdbfile[-3:] != 'sq3': newdbfile = newdbfile + '.sq3'
            try:
                self.db.create(newdbfile)
            except:
                Error(self,"Could not create new database file. Check that you are allowed to write in\n"+os.path.dirname(newdbfile)+".")
            else:
                dialog_save.destroy()
                self.refresh()
                Glob.set_var('dbfile',newdbfile)
        elif choice == Gtk.ResponseType.CANCEL:
            dialog_save.destroy()
    
    def show_whoiswhere(self,parent):
        whoiswhere = WhoIsWhere(self)
        whoiswhere.show_all()
        whoiswhere.connect("delete-event",whoiswhere.quit)
        
    def show_newentry(self,parent):
        if Glob.write_permission == 1:
            newentry = NewEditEntry(self,'new')
            newentry.show_all()
            newentry.connect('delete-event',newentry.quit)
        else:
            Error(self,"Cannot create new strain in read-only mode.")
        
    def show_editentry(self,parent):
        if Glob.write_permission == 1:
            model, row = self.treeview.get_selection().get_selected()
            if row is not None:
                editentry = NewEditEntry(self,'edit',model,row)
                editentry.show_all()
                editentry.connect('delete-event',editentry.quit)
            else:
                Error(self,'Please select an entry to edit.')
        else:
            Error(self,"Cannot edit strains in read-only mode.")
    
    def copy_entry(self,parent):
        if Glob.write_permission == 1:
            self.spinner.start()
            model,row = self.treeview.get_selection().get_selected()
            data = []
            for cell in model[row]:
                data.append(cell)
            del data[0]
            self.create(data)
            self.spinner.stop()
        else:
            Error(self,"Cannot copy strains in read-only mode.")
        
    def edit_entry(self,rowtoedit,data):
        self.spinner.start()
        self.db.edit(rowtoedit,data)
        self.refresh()
        self.spinner.stop()

    def create(self,data):
        self.spinner.start()
        strainnumber = self.db.read_max() + 1
        self.db.insert(strainnumber,data)
        self.refresh()
        self.spinner.stop()
        
    def create_whowhere(self,who,where):
        if Glob.write_permission == 1:
            self.spinner.start()
            self.db.insert_whowhere(who,where)
            self.spinner.stop()
        else:
            Error(self,"Cannot create new entry in read-only mode.")
    
    def export(self,menu):
        print("Export")
        
    def import_(self,importlist):
        for row in importlist:
            strainnumber = self.db.read_max() + 1
            self.db.insert(strainnumber,row)
        self.refresh()
        
    def del_entry(self,parent):
        if Glob.write_permission == 1:
            self.spinner.start()
            model,row = self.treeview.get_selection().get_selected()
            if row is not None:
                dialog_sure = Gtk.MessageDialog(self,Gtk.DialogFlags.DESTROY_WITH_PARENT,Gtk.MessageType.QUESTION,Gtk.ButtonsType.YES_NO,"Are you sure you want to delete entry n°"+str(model[row][0])+"?")
                choice_sure = dialog_sure.run()
                if choice_sure == Gtk.ResponseType.YES:
                    self.db.del_(model[row][0])
                    self.refresh()
                    dialog_sure.destroy()
                elif choice_sure == Gtk.ResponseType.NO:
                    dialog_sure.destroy()    
            else:
                Error(self,"Please select an entry to delete")
            self.spinner.stop()
        else:
            Error(self,"Cannot delete strains in read-only mode")
        
    def del_batch(self,dellist):
        for delitem in dellist:
            self.db.del_(delitem)
    
    def show_delbatch(self,parent):
        if Glob.write_permission == 1:
            delbatchwin = DelBatch(self)
            delbatchwin.show_all()
        else:
            Error(self,"Cannot delete strains in read-only mode")
        
    def show_import(self,parent):
        if Glob.write_permission == 1:
            importwin = Import(self)
            importwin.show_all()
        else:
            Error(self,"Cannot import strains in read-only mode")

    def show_filter(self,parent):
        filterentry = Filter(self)
        filterentry.show_all()
        
    def show_settings(self,parent):
        setwin = Settings(self)
        setwin.show_all()
        
    def show_help(self,parent):
        pass

    @staticmethod
    def show_about(*args):
        about = Gtk.AboutDialog()
        about.set_program_name('PyStrains')
        about.set_version('1.0')
        about.set_authors(['Sébastien GÉLIS'])
        about.set_copyright('(c)2013-2014 Sébastien GÉLIS')
        about.set_license('This program is free software: you can redistribute it and/or modify\nit under the terms of the GNU General Public License as published by\nthe Free Software Foundation, either version 3 of the License, or\n(at your option) any later version.\n\nThis program is distributed in the hope that it will be useful,\nbut WITHOUT ANY WARRANTY; without even the implied warranty of\nMERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\nGNU General Public License for more details.\n\nYou should have received a copy of the GNU General Public License\nalong with this program. If not, see http://www.gnu.org/licenses/.')
        about.set_comments('PyStrains is a simple lightweight strains library\nmanager for research labs.')
        about.set_website("http://www.gelis.ch/pystrains")
        #~ about.set_logo(gtk.gdk.pixbuf_new_from_file("battery.png"))
        about.run()
        about.destroy()

    def show_quickfilter(self,parent):
        quickfilter = QuickFilter(self)
        quickfilter.show_all()

    def show_users(self, parent):
        userswin = UsersList(self)
        userswin.show_all()
        
    def filter(self,parent,data):
        self.spinner.start()
        self.refresh(filter="complex",data=data)
        self.spinner.stop()
    
    def quit(self, *args):
        if not self.db.error:
            try:
                self.db.cur.close()
                self.db.conn.close()
            except:
                pass
            finally:
                Gtk.main_quit()
        else:
            Gtk.main_quit()


class UsersList(Gtk.Window):
    def __init__(self,parent):
        Gtk.Window.__init__(self, title="Users")
        self.parent = parent
        self.connect("key-press-event",self.on_key_press)
        self.set_resizable(False)
        self.set_default_size(200, 200)

        grid = Gtk.Grid()
        self.add(grid)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.liststore = Gtk.ListStore(str,str,str)

        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("button-press-event",self.on_treeview_click)

        self.renderer_text = Gtk.CellRendererText()

        columntitle = Gtk.TreeViewColumn("User", self.renderer_text, text=0)
        columntitle.set_alignment(0.5)
        columntitle.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        columntitle.set_fixed_width(160)
        self.treeview.append_column(columntitle)
        columntitle = Gtk.TreeViewColumn("Rights", self.renderer_text, text=1)
        columntitle.set_alignment(0.5)
        columntitle.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        columntitle.set_fixed_width(440)
        self.treeview.append_column(columntitle)

        button_add = Gtk.Button("Create a new user")
        button_add.connect('clicked', self.on_create_click)

        grid.add(self.treeview)
        grid.attach_next_to(button_add, self.treeview, Gtk.PositionType.RIGHT, 1, 1)

        self.fill_list()

    def fill_list(self):
        self.liststore.clear()
        if not self.parent.db.error:
            for row in self.parent.db.read_users():
                self.liststore.append(row)

    def on_create_click(self, *args):
        askadmin = AskAdmin(self)
        askadmin.show_all()
        print(Glob.isadmin)

    def on_treeview_click(self, widget=None, event=None):
        pass

    def on_key_press(self,widget,event):
        if event.keyval == 65307:self.quit(self)

    def quit(self, *args):
        self.hide()


class WhoIsWhere(Gtk.Window):
    def __init__(self,parent):
        Gtk.Window.__init__(self, title="Who is where?")
        self.parent = parent
        self.connect("key-press-event",self.on_key_press)
        self.set_resizable(False)
        self.set_default_size(200, 200)
        
        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        self.add(grid)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        ### Popup menu
        self.popmenu = Gtk.Menu()
        popmenu_delentry = Gtk.MenuItem('Delete entry')
        popmenu_delentry.connect('activate',self.del_entry)
        self.popmenu.append(popmenu_delentry)
        self.popmenu.show_all()
        
        self.liststore = Gtk.ListStore(str,str)
            
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("button-press-event",self.on_treeview_click)
        
        self.renderer_text = Gtk.CellRendererText()
        
        columntitle = Gtk.TreeViewColumn("Who", self.renderer_text, text=0)
        columntitle.set_alignment(0.5)
        columntitle.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        columntitle.set_fixed_width(160)
        self.treeview.append_column(columntitle)
        columntitle = Gtk.TreeViewColumn("Where", self.renderer_text, text=1)
        columntitle.set_alignment(0.5)
        columntitle.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        columntitle.set_fixed_width(440)
        self.treeview.append_column(columntitle)
        
        self.refresh()
        
        self.entry_who = Gtk.Entry()
        self.entry_who.set_max_length(12)
        self.entry_who.connect("key-press-event",self.on_validate)
        self.entry_iswhere = Gtk.Entry()
        self.entry_iswhere.set_max_length(40)
        self.entry_iswhere.connect("key-press-event",self.on_validate)
        
        grid.attach(self.entry_who,0,0,1,1)
        grid.attach_next_to(self.entry_iswhere,self.entry_who,Gtk.PositionType.RIGHT,3,1)
        grid.attach_next_to(self.treeview,self.entry_who,Gtk.PositionType.TOP,4,1)
        
    def on_validate(self,widget,event):
        if event.keyval == 65293 or event.keyval == 65421:
            if self.entry_who.get_text() != "" and self.entry_iswhere.get_text() != "":
                self.parent.create_whowhere(self.entry_who.get_text(),self.entry_iswhere.get_text())
                self.liststore.append([self.entry_who.get_text(),self.entry_iswhere.get_text()])
                self.entry_who.set_text("")
                self.entry_iswhere.set_text("")
            else:
                Error(self,"Please fill in both fields")
    
    def on_treeview_click(self,widget=None,event=None):
        if event.button == 3:
            path = self.treeview.get_path_at_pos(event.x,event.y)    # Determines what row is under the cursor. path[0] is the row number, path[1] is the column, path[3] is cell(x) and path[4] is cell(y)
            if path is not None:
                self.treeview.grab_focus()    # Sets keyboard focus to treeview
                self.treeview.set_cursor(path[0],path[1],0)    # Sets keyboard focus to the right row and column
                self.popmenu.popup(None,None,None,None,event.button,event.time)
                model,row = self.treeview.get_selection().get_selected()

    def del_entry(self,parent):
        model,row = self.treeview.get_selection().get_selected()
        if row is not None:
            dialog_sure = Gtk.MessageDialog(self,Gtk.DialogFlags.DESTROY_WITH_PARENT,Gtk.MessageType.QUESTION,Gtk.ButtonsType.YES_NO,"Are you sure you want to delete the entry "+'"'+str(model[row][0])+'"'+"?")
            choice_sure = dialog_sure.run()
            if choice_sure == Gtk.ResponseType.YES:
                self.parent.db.del_whowhere(model[row][1])
                self.refresh()
                dialog_sure.destroy()
            elif choice_sure == Gtk.ResponseType.NO:
                dialog_sure.destroy()    
        else:
            Error(self,"Please select an entry to delete")
    
    def refresh(self):
        self.liststore.clear()
        if not self.parent.db.error:
            for row in self.parent.db.read_who_where(): self.liststore.append(row)
    
    def on_key_press(self,widget,event):
        if event.keyval == 65307:self.quit(self)

    def quit(self, *args):
        self.hide()


class NewEditEntry(Gtk.Window):
    def __init__(self,parent,windowtype,model=None,row=None):
        if windowtype == 'new': Gtk.Window.__init__(self, title="New strain")
        if windowtype == 'edit': Gtk.Window.__init__(self, title="Edit strain")
        self.parent=parent
        self.set_default_size(200, 200)
        grid = Gtk.Grid()
        self.add(grid)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.connect("key-press-event",self.on_key_press)        
        
        self.entry_who = Gtk.Entry()
        self.entry_who.set_max_length(12)
        self.entry_who.set_placeholder_text("Experimentator")
        self.entry_box = Gtk.Entry()
        self.entry_box.set_max_length(3)
        self.entry_box.set_placeholder_text("Box")
        self.entry_tube = Gtk.Entry()
        self.entry_tube.set_max_length(3)
        self.entry_tube.set_placeholder_text("Tube")
        self.entry_strain = Gtk.Entry()
        self.entry_strain.set_max_length(30)
        self.entry_strain.set_placeholder_text("Strain")
        self.entry_genome = Gtk.Entry()
        self.entry_genome.set_max_length(50)
        self.entry_genome.set_placeholder_text("Genome")
        self.entry_plasmid = Gtk.Entry()
        self.entry_plasmid.set_max_length(50)
        self.entry_plasmid.set_placeholder_text("Plasmid")
        self.entry_ab = Gtk.Entry()
        self.entry_ab.set_max_length(20)
        self.entry_ab.set_placeholder_text("Antibiotics")
        self.entry_date = Gtk.Entry()
        self.entry_date.set_max_length(10)
        self.entry_date.set_placeholder_text("Date")
        self.entry_notes = Gtk.Entry()
        self.entry_notes.set_max_length(100)
        self.entry_notes.set_placeholder_text("Notes")
        self.seq_label = Gtk.Label("Sequencing:")
        self.seq_na = Gtk.RadioButton.new_with_label_from_widget(None,"None")
        self.seq_ok = Gtk.RadioButton.new_with_label_from_widget(self.seq_na,"Passed")
        self.seq_fail = Gtk.RadioButton.new_with_label_from_widget(self.seq_na,"Failed")
        
        self.entry_who.connect("focus-in-event",self.on_focus)
        self.entry_who.connect("button-press-event",self.on_focus)
        self.entry_box.connect("focus-in-event",self.on_focus)
        self.entry_box.connect("button-press-event",self.on_focus)
        self.entry_tube.connect("focus-in-event",self.on_focus)
        self.entry_tube.connect("button-press-event",self.on_focus)
        self.entry_strain.connect("focus-in-event",self.on_focus)
        self.entry_strain.connect("button-press-event",self.on_focus)
        self.entry_genome.connect("focus-in-event",self.on_focus)
        self.entry_genome.connect("button-press-event",self.on_focus)
        self.entry_plasmid.connect("focus-in-event",self.on_focus)
        self.entry_plasmid.connect("button-press-event",self.on_focus)
        self.entry_ab.connect("focus-in-event",self.on_focus)
        self.entry_ab.connect("button-press-event",self.on_focus)
        self.entry_date.connect("focus-in-event",self.on_focus)
        self.entry_date.connect("button-press-event",self.on_focus)
        self.entry_notes.connect("focus-in-event",self.on_focus)
        self.entry_notes.connect("button-press-event",self.on_focus)
        
        button_delta = Gtk.Button(chr(916))        # Delta
        button_delta.connect("clicked",lambda x:self.insert_char("delta"))
        button_omega = Gtk.Button(chr(937))        # Omega
        button_omega.connect("clicked",lambda x:self.insert_char("omega"))
        button_alpha = Gtk.Button(chr(945))        # Alpha
        button_alpha.connect("clicked",lambda x:self.insert_char("alpha"))
        button_lambda = Gtk.Button(chr(955))    # Lambda
        button_lambda.connect("clicked",lambda x:self.insert_char("lambda"))
        
        button_send = Gtk.Button(self,stock='gtk-ok')
        if windowtype == 'new': button_send.connect('clicked',self.sendto_create)
        if windowtype == 'edit': button_send.connect('clicked',self.sendto_edit)
        button_cancel = Gtk.Button(self,stock='gtk-cancel')
        button_cancel.connect('clicked',self.quit)
        
        grid.attach(self.entry_who,0,0,4,1)
        grid.attach_next_to(self.entry_box,self.entry_who,Gtk.PositionType.BOTTOM,4,1)
        grid.attach_next_to(self.entry_tube,self.entry_box,Gtk.PositionType.BOTTOM,4,1)
        grid.attach_next_to(self.entry_strain,self.entry_tube,Gtk.PositionType.BOTTOM,4,1)
        grid.attach_next_to(self.entry_genome,self.entry_strain,Gtk.PositionType.BOTTOM,4,1)
        grid.attach_next_to(self.entry_plasmid,self.entry_genome,Gtk.PositionType.BOTTOM,4,1)
        grid.attach_next_to(self.entry_ab,self.entry_plasmid,Gtk.PositionType.BOTTOM,4,1)
        grid.attach_next_to(self.entry_date,self.entry_ab,Gtk.PositionType.BOTTOM,4,1)
        grid.attach_next_to(self.entry_notes,self.entry_date,Gtk.PositionType.BOTTOM,4,1)
        
        grid.attach_next_to(self.seq_label,self.entry_notes,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.seq_na,self.seq_label,Gtk.PositionType.RIGHT,2,1)
        grid.attach_next_to(self.seq_ok,self.seq_na,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.seq_fail,self.seq_ok,Gtk.PositionType.BOTTOM,2,1)
        
        grid.attach(button_delta,0,12,1,1)
        grid.attach_next_to(button_omega,button_delta,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(button_alpha,button_omega,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(button_lambda,button_alpha,Gtk.PositionType.RIGHT,1,1)
        
        grid.attach_next_to(button_cancel,button_delta,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(button_send,button_alpha,Gtk.PositionType.BOTTOM,2,1)
        
        if windowtype == 'edit':
            self.rowtoedit = model[row][0]
            self.entry_who.set_text(str(model[row][1]))
            self.entry_box.set_text(str(model[row][2]))
            self.entry_tube.set_text(str(model[row][3]))
            self.entry_strain.set_text(str(model[row][4]))
            self.entry_genome.set_text(str(model[row][5]))
            self.entry_plasmid.set_text(str(model[row][6]))
            self.entry_ab.set_text(str(model[row][7]))
            self.entry_date.set_text(str(model[row][8]))
            self.entry_notes.set_text(str(model[row][9]))
            ### Read sequencing status and check the right radio button
            if model[row][10] == "": self.seq_na.set_active(True)
            if model[row][10] == "Passed": self.seq_ok.set_active(True)
            if model[row][10] == "Failed": self.seq_fail.set_active(True)
        
        button_cancel.grab_focus()    # Otherwise self.entry_who gets the focus when window opens, and the placeholder text disappears
        self.active_entry = self.entry_who    # Initializes the variable to first entry
    
    def on_focus(self,widget,signal):
        self.active_entry = widget
            
    def insert_char(self,specchar):
        if specchar == "delta": self.active_entry.set_text(self.active_entry.get_text()+chr(916))
        if specchar == "omega": self.active_entry.set_text(self.active_entry.get_text()+chr(937))
        if specchar == "alpha": self.active_entry.set_text(self.active_entry.get_text()+chr(945))
        if specchar == "lambda": self.active_entry.set_text(self.active_entry.get_text()+chr(955))
        self.active_entry.grab_focus()
    
    def sendto_create(self,parent):
        
        try:
            tmp = int(self.entry_box.get_text())
            tmp = int(self.entry_tube.get_text())
        except:
            Error(self,"Please enter numerical values for box and tube fields")
        else:
        
            if '%' not in self.entry_who.get_text() and '%' not in self.entry_date.get_text() and '%' not in self.entry_box.get_text() and '%' not in self.entry_tube.get_text() and '%' not in self.entry_strain.get_text() and '%' not in self.entry_genome.get_text() and '%' not in self.entry_plasmid.get_text() and '%' not in self.entry_ab.get_text() and '%' not in self.entry_notes.get_text():
                if '_' not in self.entry_who.get_text() and '_' not in self.entry_date.get_text() and '_' not in self.entry_box.get_text() and '_' not in self.entry_tube.get_text() and '_' not in self.entry_strain.get_text() and '_' not in self.entry_genome.get_text() and '_' not in self.entry_plasmid.get_text() and '_' not in self.entry_ab.get_text() and '_' not in self.entry_notes.get_text():
                    if self.entry_who.get_text() != '' and self.entry_box.get_text() != '' and self.entry_tube.get_text() != '':
                        ### Get sequencing status and store it in seq
                        if self.seq_na.get_active(): seq = 0
                        if self.seq_ok.get_active(): seq = 1
                        if self.seq_fail.get_active(): seq = -1
                        ### Build data tuple and send it to create
                        data = (self.entry_who.get_text(),int(self.entry_box.get_text()),int(self.entry_tube.get_text()),self.entry_strain.get_text(),self.entry_genome.get_text(),self.entry_plasmid.get_text(),self.entry_ab.get_text(),self.entry_date.get_text(),self.entry_notes.get_text(), seq)
                        self.parent.create(data)
                        self.quit()
                    else:
                        Error(self, 'Please fill in minimum fields')
                else:
                    Error(self, 'Character _ not allowed')
            else:
                Error(self, 'Character % not allowed')
    
    def sendto_edit(self, parent):
                
        try:
            tmp = int(self.entry_box.get_text())
            tmp = int(self.entry_tube.get_text())
        except:
            Error(self, "Please enter numerical values for box and tube fields")
        else:
        
            if '%' not in self.entry_who.get_text() and '%' not in self.entry_date.get_text() and '%' not in self.entry_box.get_text() and '%' not in self.entry_tube.get_text() and '%' not in self.entry_strain.get_text() and '%' not in self.entry_genome.get_text() and '%' not in self.entry_plasmid.get_text() and '%' not in self.entry_ab.get_text() and '%' not in self.entry_notes.get_text():
                if '_' not in self.entry_who.get_text() and '_' not in self.entry_date.get_text() and '_' not in self.entry_box.get_text() and '_' not in self.entry_tube.get_text() and '_' not in self.entry_strain.get_text() and '_' not in self.entry_genome.get_text() and '_' not in self.entry_plasmid.get_text() and '_' not in self.entry_ab.get_text() and '_' not in self.entry_notes.get_text():
                    ### Get sequencing status and store it in seq
                    if self.seq_na.get_active(): seq = 0
                    if self.seq_ok.get_active(): seq = 1
                    if self.seq_fail.get_active(): seq = -1
                    ### Build data tuple and send it to edit
                    data = (self.entry_who.get_text(),int(self.entry_box.get_text()),int(self.entry_tube.get_text()),self.entry_strain.get_text(),self.entry_genome.get_text(),self.entry_plasmid.get_text(),self.entry_ab.get_text(),self.entry_date.get_text(),self.entry_notes.get_text(),seq)
                    self.parent.edit_entry(self.rowtoedit,data)
                    self.quit()
                else:
                    Error(self, 'Character _ not allowed')
            else:
                Error(self, 'Character % not allowed')
    
    def on_key_press(self,widget,event):
        if event.keyval == 65307:
            self.quit()
        
    def quit(self, *args):
        self.hide()


class QuickFilter(Gtk.Window):
    def __init__(self,parent):
        Gtk.Window.__init__(self, title="Search")
        self.parent = parent
        self.set_default_size(200, 200)
        grid = Gtk.Grid()
        self.add(grid)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.connect("key-press-event",self.on_key_press)

        self.entry_query = Gtk.Entry()

        button_send = Gtk.Button(self,stock='gtk-find',use_underline=True)
        button_send.label = button_send.get_children()[0]
        button_send.label=button_send.label.get_children()[0].get_children()[1]
        button_send.label=button_send.label.set_label('Filter')
        button_send.connect('clicked',self.sendto_quickfilter)

        button_reset = Gtk.Button(self,stock='gtk-cancel',use_underline=True)
        button_reset.label = button_reset.get_children()[0]
        button_reset.label=button_reset.label.get_children()[0].get_children()[1]
        button_reset.label=button_reset.label.set_label('_Reset')
        button_reset.connect('clicked',self.reset)

        grid.add(self.entry_query)
        grid.attach_next_to(button_send, self.entry_query, Gtk.PositionType.BOTTOM, 1, 1)
        grid.attach_next_to(button_reset, button_send, Gtk.PositionType.RIGHT, 1, 1)

    def on_key_press(self,widget,event):
        if event.keyval == 65293 or event.keyval == 65421:
            self.sendto_quickfilter()
        if event.keyval == 65307: self.quit()

    def sendto_quickfilter(self, widget=None):
        data = self.entry_query.get_text().split()
        self.parent.refresh(filter="quick",data=data)

    def reset(self, widget=None):
        self.parent.refresh()
        self.quit()

    def quit(self, *args):
        self.hide()
        

class Filter(Gtk.Window):
    def __init__(self,parent):
        Gtk.Window.__init__(self, title="Search")
        self.parent=parent
        self.set_default_size(200, 200)
        grid = Gtk.Grid()
        self.add(grid)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.connect("key-press-event",self.on_key_press)

        label_hint = Gtk.Label('Hint: use _ as a single character joker\nand % as a multiple characters joker')
        
        self.entry_who = Gtk.Entry()
        self.entry_who.id = 'Experimentator'
        self.entry_who.set_placeholder_text("Experimentator")
        self.entry_who.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_who.connect('icon-press',self.sendto_filter_single)
        
        self.entry_box = Gtk.Entry()
        self.entry_box.id = 'Box'
        self.entry_box.set_placeholder_text("Box")
        self.entry_box.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_box.connect('icon-press',self.sendto_filter_single)
        
        self.entry_tube = Gtk.Entry()
        self.entry_tube.id = 'Tube'
        self.entry_tube.set_placeholder_text("Tube")
        self.entry_tube.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_tube.connect('icon-press',self.sendto_filter_single)
        
        self.entry_strain = Gtk.Entry()
        self.entry_strain.id = 'Strain'
        self.entry_strain.set_placeholder_text("Strain")
        self.entry_strain.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_strain.connect('icon-press',self.sendto_filter_single)
        
        self.entry_genome = Gtk.Entry()
        self.entry_genome.id = 'Genome'
        self.entry_genome.set_placeholder_text("Genome")
        self.entry_genome.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_genome.connect('icon-press',self.sendto_filter_single)
        
        self.entry_plasmid = Gtk.Entry()
        self.entry_plasmid.id = 'Plasmid'
        self.entry_plasmid.set_placeholder_text("Plasmid")
        self.entry_plasmid.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_plasmid.connect('icon-press',self.sendto_filter_single)
        
        self.entry_ab = Gtk.Entry()
        self.entry_ab.id = 'Antibiotics'
        self.entry_ab.set_placeholder_text("Antibiotics")
        self.entry_ab.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_ab.connect('icon-press',self.sendto_filter_single)
        
        self.entry_date = Gtk.Entry()
        self.entry_date.id = 'Date'
        self.entry_date.set_placeholder_text("Date")
        self.entry_date.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_date.connect('icon-press',self.sendto_filter_single)
        
        self.entry_notes = Gtk.Entry()
        self.entry_notes.id = 'Notes'
        self.entry_notes.set_placeholder_text("Notes")
        self.entry_notes.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,Gtk.STOCK_FIND)
        self.entry_notes.connect('icon-press',self.sendto_filter_single)
        
        button_reset = Gtk.Button(self,stock='gtk-cancel',use_underline=True)
        button_reset.label = button_reset.get_children()[0]                                # These three lines
        button_reset.label=button_reset.label.get_children()[0].get_children()[1]        # are a dumb trick to make a stock button
        button_reset.label=button_reset.label.set_label('_Reset')                        # with a custom label
        button_reset.connect('clicked',self.reset)
        
        button_send = Gtk.Button(self,stock='gtk-find',use_underline=True)
        button_send.label = button_send.get_children()[0]
        button_send.label=button_send.label.get_children()[0].get_children()[1]
        button_send.label=button_send.label.set_label('Multi-criteria _search')
        button_send.connect('clicked',self.sendto_filter_multiple)
        
        grid.attach(self.entry_who,0,0,2,1)
        grid.attach_next_to(self.entry_box,self.entry_who,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.entry_tube,self.entry_box,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.entry_strain,self.entry_tube,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.entry_genome,self.entry_strain,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.entry_plasmid,self.entry_genome,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.entry_ab,self.entry_plasmid,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.entry_date,self.entry_ab,Gtk.PositionType.BOTTOM,2,1)
        grid.attach_next_to(self.entry_notes,self.entry_date,Gtk.PositionType.BOTTOM,2,1)        
        
        grid.attach_next_to(button_reset,self.entry_notes,Gtk.PositionType.BOTTOM,1,1)
        grid.attach_next_to(button_send,button_reset,Gtk.PositionType.RIGHT,1,1)
        
        grid.attach_next_to(label_hint,button_reset,Gtk.PositionType.BOTTOM,2,2)
        
        button_reset.grab_focus()    # Otherwise self.entry_who gets the focus when window opens, and the placeholder text disappears
        
    def on_key_press(self,widget,event):
        if event.keyval == 65293 or event.keyval == 65421:
            self.sendto_filter_multiple()
        if event.keyval == 65307:self.quit()
        
    def sendto_filter_single(self,widget,icon,*args):
        data = {}
        data[widget.id] = widget.get_text()
        self.parent.filter(self.parent,data)
        
    def sendto_filter_multiple(self,widget=None):
        data = {}
        if self.entry_who.get_text() != '': data['Experimentator'] = self.entry_who.get_text()
        if self.entry_box.get_text() != '': data['Box'] = self.entry_box.get_text()
        if self.entry_tube.get_text() != '': data['Tube'] = self.entry_tube.get_text()
        if self.entry_strain.get_text() != '': data['Strain'] = self.entry_strain.get_text()
        if self.entry_genome.get_text() != '': data['Genome'] = self.entry_genome.get_text()
        if self.entry_plasmid.get_text() != '': data['Plasmid'] = self.entry_plasmid.get_text()
        if self.entry_ab.get_text() != '': data['Antibiotics'] = self.entry_ab.get_text()
        if self.entry_date.get_text() != '': data['Date'] = self.entry_date.get_text()
        if self.entry_notes.get_text() != '': data['Notes'] = self.entry_notes.get_text()
        
        ### Replace spaces by SQL joker % in search requests.
        ### % acts as a multiple character joker like * in bash.
        ### Request "x y" will therefore search for "x*y" instead of purely "xSPACEy".
        for k in data.keys():
            data[k] = data[k].replace(" ","%")
        
        self.parent.filter(self,data)
        
    def reset(self,parent):
        data = {}
        self.entry_who.set_text('')
        self.entry_box.set_text('')
        self.entry_tube.set_text('')
        self.entry_strain.set_text('')
        self.entry_genome.set_text('')
        self.entry_plasmid.set_text('')
        self.entry_ab.set_text('')
        self.entry_notes.set_text('')
        self.parent.filter(self.parent,data)
    
    def quit(self, *args):
        self.hide()


class Import(Gtk.Window):
    def __init__(self,parent):
        self.parent = parent
        Gtk.Window.__init__(self, title='Import')
        grid = Gtk.Grid()
        self.add(grid)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.connect("key-press-event",self.on_key_press)
        
        xlfile_label = Gtk.Label('Excel file:',justify=Gtk.Justification.RIGHT)
        self.xlfile_entry = Gtk.Entry(text="testreal.xls")
        
        self.header = Gtk.CheckButton("Header mode")
        self.header.set_has_tooltip(True)
        self.header.set_tooltip_text("Test")
        self.header.connect('toggled',self.set_header_mode)
        self.headermode = False
        
        button_ok = Gtk.Button(self,stock='gtk-ok')
        button_ok.connect('clicked',self.ok)
        button_cancel = Gtk.Button(self,stock='gtk-cancel')
        button_cancel.connect('clicked',self.quit)
        button_open = Gtk.Button(self,stock='gtk-open')
        button_open.connect('clicked',self.show_open)
        
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        emptylabel = Gtk.Label("")
        emptylabel2 = Gtk.Label("")
        
        label_format = Gtk.Label("\nPlease note that your Excel file should be formatted as follows:\n")
        label_format2 = Gtk.Label("\nBetween stars: minimal required fields\nSequencing results: 0 if none, 1 if passed, -1 if failed")
        label_format.set_alignment(0,1)
        label_format2.set_alignment(0,1)
        liststore = Gtk.ListStore(str, str, str, str, str, str, str, str, str, str)
        treeview = Gtk.TreeView(model=liststore)
        treeview.set_enable_search(False)
        renderer_text = Gtk.CellRendererText()
        
        headers = ["Experimentator","Box","Tube","Strain","Genome","Plasmid","Antibiotics","Date","Notes","Sequencing"]
        i = 0
        while i < len(headers):
            columntitle = Gtk.TreeViewColumn(headers[i],renderer_text,text=i)
            columntitle.set_alignment(0.5)
            treeview.append_column(columntitle)
            i += 1
        liststore.append(["*Me*","*5*","*17*","E. coli TG1","ΔompF","pUC18","Amp100","2013-09-08","Clone #3","*-1*"])

        grid.add(xlfile_label)
        grid.attach_next_to(emptylabel,xlfile_label,Gtk.PositionType.BOTTOM,5,1)
        grid.attach_next_to(self.xlfile_entry,xlfile_label,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(button_open,self.xlfile_entry,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(button_ok,button_open,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(button_cancel,button_ok,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(self.header,button_open,Gtk.PositionType.BOTTOM,1,1)
        grid.attach_next_to(sep,emptylabel,Gtk.PositionType.BOTTOM,5,1)
        grid.attach_next_to(label_format,sep,Gtk.PositionType.BOTTOM,5,1)
        grid.attach_next_to(treeview,label_format,Gtk.PositionType.BOTTOM,5,1)
        grid.attach_next_to(label_format2,treeview,Gtk.PositionType.BOTTOM,5,1)
        grid.attach_next_to(emptylabel2,label_format2,Gtk.PositionType.BOTTOM,5,1)
    
    def set_header_mode(self,widget):
        if self.header.get_active():
            self.headermode = True
        else:
            self.headermode = False
        
    def show_open(self,widget=None):
        dialog_open = Gtk.FileChooserDialog("Please choose an Excel file", self,Gtk.FileChooserAction.OPEN,(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        choice = dialog_open.run()
        if choice == Gtk.ResponseType.OK:
            self.xlfile_entry.set_text(dialog_open.get_filename())
        elif choice == Gtk.ResponseType.CANCEL:
            dialog_open.destroy()
        dialog_open.destroy()
        
    def ok(self,event=None):
        if self.xlfile_entry.get_text() != '':
            xlfile = self.xlfile_entry.get_text()
            importlist = []
            
            with open_workbook(xlfile) as f:
            
                for sheet in f.sheets():
                    
                    for row in range(sheet.nrows):
                        listrow = []
                        if self.headermode and row==0:continue        # If user specified there is a header in the table, do not consider first row
                        
                        for col in range(sheet.ncols):
                            cell = sheet.cell(row,col).value
                            if type(cell) == float: cell = int(cell)    # If cell contains a number, it will be imported as a float. This line converts it to int.
                            if sheet.cell_type(row,col) == 3:            # If cell type is "date"
                                date_tuple = xldate_as_tuple(cell,f.datemode)[:3]    # Read the cell as a date and return a tuple containing (year,month,day,hour,minute,second)
                                cell = str(date_tuple[0])+"-"+str(date_tuple[1])+"-"+str(date_tuple[2])
                            listrow.append(str(cell))
                        importlist.append(listrow)
                self.parent.import_(importlist)
            
        else:
            Error(self,'Please choose a file')
        self.quit()
        
    def on_key_press(self,widget,event):
        if event.keyval == 65307:self.quit()
        
    def quit(self, *args):
        self.hide()


class Settings(Gtk.Window):
    def __init__(self,parent):
        self.parent = parent
        Gtk.Window.__init__(self, title='Settings')
        grid = Gtk.Grid()
        self.add(grid)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.connect("key-press-event",self.on_key_press)
        
        dbfile_label = Gtk.Label('Database:',justify=Gtk.Justification.RIGHT)
        self.dbfile_entry = Gtk.Entry()
        self.dbfile_entry.set_text(Glob.dbfile)
        button_ok = Gtk.Button(self,stock='gtk-ok')
        button_ok.connect('clicked',self.ok)
        button_cancel = Gtk.Button(self,stock='gtk-cancel')
        button_cancel.connect('clicked',self.quit)
        button_open = Gtk.Button(self,stock='gtk-open')
        button_open.connect('clicked',self.show_open)
        
        grid.add(dbfile_label)
        grid.attach_next_to(self.dbfile_entry,dbfile_label,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(button_open,self.dbfile_entry,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(button_cancel,self.dbfile_entry,Gtk.PositionType.BOTTOM,1,1)
        grid.attach_next_to(button_ok,button_open,Gtk.PositionType.BOTTOM,1,1)
        
    def show_open(self,widget=None):
        dialog_open = Gtk.FileChooserDialog("Please choose a database file",self,Gtk.FileChooserAction.OPEN,(Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN,Gtk.ResponseType.OK))

        filter_sq3 = Gtk.FileFilter()
        filter_sq3.set_name("SQLite 3 databases")
        filter_sq3.add_pattern("*.sq3")
        dialog_open.add_filter(filter_sq3)
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")
        dialog_open.add_filter(filter_all)

        choice = dialog_open.run()
        if choice == Gtk.ResponseType.OK:
            self.dbfile_entry.set_text(dialog_open.get_filename())
        elif choice == Gtk.ResponseType.CANCEL:
            dialog_open.destroy()
        dialog_open.destroy()
        
    def ok(self,event=None):
        if self.dbfile_entry.get_text() != '':
            Glob.set_var('dbfile',self.dbfile_entry.get_text())
            self.parent.init_db()
            self.parent.init_treeview()
            self.parent.refresh()
        else:
            Error(self,'Please enter a valid database address')
        self.quit()
    
    def on_key_press(self,widget,event):
        if event.keyval == 65307:self.quit()
        
    def quit(self, *args):
        self.hide()


class DelBatch(Gtk.Window):
    def __init__(self,parent):
        self.parent = parent
        Gtk.Window.__init__(self, title='Delete multiple entries')
        grid = Gtk.Grid()
        self.add(grid)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.connect("key-press-event",self.on_key_press)

        self.max = self.parent.db.read_max()
        self.min = self.parent.db.read_min()
        
        self.entry_from = Gtk.Entry()
        self.entry_from.set_placeholder_text("min=" + str(self.min))
        self.entry_to = Gtk.Entry()
        self.entry_to.set_placeholder_text("max=" + str(self.max))
        label = Gtk.Label('-')
        button_ok = Gtk.Button(self,stock='gtk-ok')
        button_ok.connect('clicked',self.ok)
        button_cancel = Gtk.Button(self,stock='gtk-cancel')
        button_cancel.connect('clicked',self.quit)
        
        grid.add(self.entry_from)
        grid.attach_next_to(label,self.entry_from,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(self.entry_to,label,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(button_ok,self.entry_to,Gtk.PositionType.BOTTOM,1,1)
        grid.attach_next_to(button_cancel,self.entry_from,Gtk.PositionType.BOTTOM,1,1)

        button_cancel.grab_focus()      # Otherwise entry_from gets focus and hides placeholder
        
    def ok(self,event=None):
        try:
            delfrom = int(self.entry_from.get_text())
            delto = int(self.entry_to.get_text())
        except:
            Error(self,'Please enter valid numbers')
        else:
            if 0 < delfrom <= delto and delfrom >= self.min and delto <= self.max:
                dialog_sure = Gtk.MessageDialog(self,Gtk.DialogFlags.DESTROY_WITH_PARENT,Gtk.MessageType.QUESTION,Gtk.ButtonsType.YES_NO,"Are you sure you want to delete entries n°" + str(delfrom) + " to " + str(delto) + "?")
                choice_sure = dialog_sure.run()
                if choice_sure == Gtk.ResponseType.YES:
                    self.parent.del_batch(list(range(delfrom,delto + 1)))
                    self.parent.refresh()
                    self.quit()
                    dialog_sure.destroy()
                elif choice_sure == Gtk.ResponseType.NO:
                    dialog_sure.destroy()
            else:
                Error(self,'Please enter valid values')
    
    def on_key_press(self,widget,event):
        if event.keyval == 65307:self.quit()
        
    def quit(self, *args):
        self.hide()


class Error(Gtk.MessageDialog):
    def __init__(self,parent,text):
        Gtk.MessageDialog.__init__(self,parent,Gtk.DialogFlags.DESTROY_WITH_PARENT,Gtk.MessageType.WARNING,Gtk.ButtonsType.CLOSE,text)
        self.run()
        self.destroy()


class FirstRun(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title='First run')
        grid = Gtk.Grid()
        self.add(grid)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("key-press-event",self.on_key_press)
        
        label = Gtk.Label("\nNo database could be found.\n")
        button_create = Gtk.Button("Create new database")
        button_create.connect("clicked",self.create)
        button_set = Gtk.Button("Set existing database")
        button_set.connect("clicked",self.set)
        
        grid.add(button_create)
        grid.attach_next_to(button_set,button_create,Gtk.PositionType.RIGHT,1,1)
        grid.attach_next_to(label,button_create,Gtk.PositionType.TOP,2,1)
        
    def create(self,widget):
        dialog_save = Gtk.FileChooserDialog("Create new database", self,Gtk.FileChooserAction.SAVE,(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,Gtk.STOCK_SAVE, Gtk.ResponseType.OK),do_overwrite_confirmation=True)
        dialog_save.set_create_folders(True)
        choice = dialog_save.run()
        if choice == Gtk.ResponseType.OK:
            newdbfile = dialog_save.get_filename()
            if newdbfile[-3:] != 'sq3': newdbfile += '.sq3'

            dialog_save.destroy()

            Glob.set_var('dbfile',newdbfile)
            
            conn = sqlite3.connect(newdbfile)
            cur = conn.cursor()
            
            request = 'CREATE TABLE strains (StrainNumber INTEGER, Experimentator TEXT, Box INTEGER, Tube INTEGER, STRAIN TEXT, Genome TEXT, Plasmid TEXT, Antibiotics TEXT, Date TEXT, Notes TEXT, Sequenced INTEGER)'
            cur.execute(request)
            request = 'CREATE TABLE who_is_where (Who TEXT, IsWhere TEXT)'
            cur.execute(request)
            request = 'CREATE TABLE users (user TEXT, rights TEXT, pwd TEXT)'
            cur.execute(request)

            cur.close()
            conn.close()
            self.restart()
        elif choice == Gtk.ResponseType.CANCEL:
            dialog_save.destroy()

    def set(self,widget):
        dialog_open = Gtk.FileChooserDialog("Please choose a database file", self,Gtk.FileChooserAction.OPEN,(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        filter_sq3 = Gtk.FileFilter()
        filter_sq3.set_name("SQLite 3 databases")
        filter_sq3.add_pattern("*.sq3")
        dialog_open.add_filter(filter_sq3)
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")
        dialog_open.add_filter(filter_all)

        choice = dialog_open.run()
        if choice == Gtk.ResponseType.OK:
            Glob.set_var('dbfile',dialog_open.get_filename())
        elif choice == Gtk.ResponseType.CANCEL:
            dialog_open.destroy()
            
        dialog_open.destroy()
        self.restart()

    @staticmethod
    def restart(*args):
        os.execl(sys.executable, sys.executable, * sys.argv)
    
    def on_key_press(self,widget,event):
        if event.keyval == 65307:self.quit()

    @staticmethod
    def quit(*args):
        Gtk.main_quit()    


def main():
    try:
        f = open('.pystrains.conf')
        line = f.readline()
        f.close()
        dbfile = line.split()        # Because line ends with a \n we do not want
        Glob.dbfile = dbfile[0]
        f = open(Glob.dbfile)
    except FileNotFoundError:
        firstrun = FirstRun()
        firstrun.connect('delete-event',firstrun.quit)
        firstrun.show_all()
        Gtk.main()
    except error:
        print("Error: ", error)
    else:
        Glob.locate_db()
        mainwin = StrainBook()
        mainwin.connect("delete-event", mainwin.quit)
        mainwin.show_all()
        Gtk.main()
    finally:
        return 0
    # Glob.LocateDB()
    # win = StrainBook()
    # win.connect("delete-event", win.Quit)
    # win.show_all()
    # Gtk.main()
    # return 0

if __name__ == '__main__':
    main()

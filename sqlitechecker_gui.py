#!/usr/bin/env python
# -*- coding:utf-8 -*-

# @file: sqlitechecker_gui.py
# @purpose: an assist tool to help validate sqlite files and output result to a webpage.
# It can validate below items: label, locale, sync status(local server and GCS), watermark,
# it also can generate report for a set of sqlites for a round.
# @author: Reed Xia <python012@qq.com>

__doc__ = """ Sqlitechecker is the tool to help validate sqlites from many aspects. To compile the source file to .exe in windows,
it requires wxpython, pywin32(need for pyinstaller), pyh, pysmb, mysqldb, google-api-python-client.
"""
__author__ = "Reed Xia <python012@qq.com>"
__version__ = '$Revision: 16 $'
__date__ = '$Date: 2014-04-15 $'


import wx
import wx.lib.filebrowsebutton as filebrowse
from pyh import *
import sqlite3 as lite
import time 
from time import strftime
import os
import webbrowser
from smb.SMBConnection import SMBConnection
from smb.smb_structs import OperationFailure
import urllib2
from smb.SMBHandler import SMBHandler
import MySQLdb
# Begin: work for cloud sync check.
import httplib2
from apiclient.discovery import build as discovery_build
import json
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage as CredentialStorage
from oauth2client.tools import run as run_oauth2
# End: work for cloud sync check.
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

# Gloable values
TARGET_DIR = ''
TARGET_LABEL = ''
TARGET_BUILD = ''
TARGET_LOCALE_LIST = []
SELECTIONS = []
SQLITE_COUNT = None
FINISHED_DB_COUNT = 0
WATERMARKE_STATUS = None
EN_SCREEN_NUMBER = 0
error_number = 0
mysql_IP = "10.194.77.221"

DIRECTOR = urllib2.build_opener(SMBHandler)
screen_conn = None

starttime = None
con = None
cur = None
config = None
FILELIST_IN_TARGET_DIR = []

result_page = None

# Screen Server config
SS_USER = 'scrserver'
SS_PW = 'motorola123'
SS_IP = '10.194.77.221'
SS_PORT = 139

# The values as bgcolor of the name row in the forms
rowname_bgcolor_value = 'Silver'
index_color = 'Silver'
en_color = 'YellowGreen'
RESULT_TAB_STYLE = 'font-size:14px;'
OVERALL_TAB_STYLE = 'font-size:13px;color:Gray;'
SCRIPT_DB_TAB_STYLE = 'font-size:14px;'
temp_index = 0

# Cloud Sync check
CLIENT_SECRETS_FILE = 'client_secret.json'
CREDENTIALS_FILE = 'credentials.json'
RO_SCOPE = 'https://www.googleapis.com/auth/devstorage.read_only'
MISSING_CLIENT_SECRETS_MESSAGE = "The secret file is missing"
bucket_name = "mmavikscreenshot01"
cloud_service = None
bad_screen_list = [] # The list of screens not sync to Cloud Server.


class SqChekFrame(wx.Frame):
    def __init__(self, parent, id):
        wx.Frame.__init__(self, parent, id,
                          title = 'Sqlitechecker v1.6 (Apr. 14, 2014)',
                          style = (wx.SYSTEM_MENU |
                          wx.MINIMIZE_BOX |
                          wx.CAPTION |
                          wx.CLOSE_BOX |
                          wx.CLIP_CHILDREN),
                          size = (690, 580))

        panel = MainPanel(self)
        panel.msgLabel.AppendText(panel.getTimestamp() + ' Sqlitechecker is ready.\n')
        panel.msgLabel.AppendText(panel.getTimestamp() + ' Screen Server IP: %s. \n' % SS_IP )
        panel.msgLabel.AppendText(panel.getTimestamp() + ' GCS bucket: %s. \n' % bucket_name )


class MainPanel(wx.Panel):
    def __init__(self, parent, id=-1):
        wx.Panel.__init__(self, parent, id)

        self.dirLabel = wx.StaticText(self, -1, "DB folder")
        self.dirBrowser = wx.DirPickerCtrl(self, -1)
        self.Bind(wx.EVT_DIRPICKER_CHANGED, self.OnDirButton, self.dirBrowser)

        self.labelLabel = wx.StaticText(self, -1, "Expected label")
        self.labelTxtBox = wx.TextCtrl(self, -1, "", size=(290, -1))
        #~ self.Bind(wx.EVT_TEXT, self.OnLabelTextChange, self.labelTxtBox)

        self.localeLabel = wx.StaticText(self, -1, "Expected locale")
        self.localeButton = wx.Button(self, -1, "Click here to open locales list", (50,-1))
        self.Bind(wx.EVT_BUTTON, self.OnLocaleButton, self.localeButton)
        
        self.targetBuildLabel = wx.StaticText(self, -1, "Target build")
        self.buildTxtBox = wx.TextCtrl(self, -1, "", size=(290, -1))

        self.checkSyncLabel = wx.StaticText(self, -1, "Local sync")
        self.checkSyncBox = wx.CheckBox(self, -1, "")
        
        self.checkCloudSyncLabel = wx.StaticText(self, -1, "Cloud sync")
        self.checkCloudSyncBox = wx.CheckBox(self, -1, "")

        self.checkDupLabel = wx.StaticText(self, -1, "Check dup screen*")
        self.checkDupBox = wx.CheckBox(self, -1, "")
        
        self.countScreenSumLabel = wx.StaticText(self, -1, "Count screens sum*")
        self.countScreenSumBox = wx.CheckBox(self, -1, "")

        self.DBanalysisLabel = wx.StaticText(self, -1, "DB analysis*")
        self.DBanalysisBox = wx.CheckBox(self, -1, "")

        self.msgName = wx.StaticText(self, -1, "Message")
        self.msgLabel = wx.TextCtrl(self, -1, "", style = wx.TE_MULTILINE|wx.TE_READONLY, size=(520, 240))

        self.runButton = wx.Button(self, -1, 'Go', size = (80, -1))
        self.Bind(wx.EVT_BUTTON, self.OnClickRun, self.runButton)
        
        self.cleanButton = wx.Button(self, -1, 'Reset', size = (80, -1))
        self.Bind(wx.EVT_BUTTON, self.OnCleanValue, self.cleanButton)
        
        #~ self.newButton = wx.Button(self, -1, 'New', size = (80, -1))

        mySizer = wx.FlexGridSizer(cols=2, hgap=6, vgap=6)
        mySizer.AddMany([self.dirLabel, self.dirBrowser,
                         self.labelLabel, self.labelTxtBox,
                         self.targetBuildLabel, self.buildTxtBox,
                         self.localeLabel, self.localeButton,
                         self.checkSyncLabel, self.checkSyncBox,
                         self.checkCloudSyncLabel, self.checkCloudSyncBox,
                         self.checkDupLabel, self.checkDupBox,
                         self.countScreenSumLabel, self.countScreenSumBox,
                         self.DBanalysisLabel, self.DBanalysisBox,
                         (0,0), (0,0),
                         self.msgName, self.msgLabel,
                         self.runButton, self.cleanButton
                        ])
        
        border = wx.BoxSizer(wx.VERTICAL)
        border.Add(mySizer, 0, wx.ALL, 25)
        self.SetSizer(border)
        self.SetAutoLayout(True)
    
    def OnCleanValue(self, event):
        self.dirBrowser.SetPath('')
        self.labelTxtBox.Clear()
        self.msgLabel.Clear()
        self.buildTxtBox.Clear()
    
    def OnDirButton(self, event):
        self.msgLabel.AppendText(self.getTimestamp() + ' Folder: ' + self.dirBrowser.GetPath() + '\n')
    
    def OnLocaleButton(self, event):
        full_locales = "en,en-GB,fr,it,de,es,es-US,pt-BR,pt-PT,nl,pl,el-GR,zh-CN,zh-TW,ja-JP,ko-KR,in-ID,fi,nb-NO,da-DK,sv-SE,tr,iw-IL,ar-EG,hu,ro,sk,cs-CZ,hr,ca-ES,sl-SL,sr-RS,bg,uk-UA,ru,lt-LT,lv,hi-IN,ms-MY,th,tl-PH,vi-VN".split(",")
        self.locale_dlg = wx.MultiChoiceDialog(self, 'Select the expected locale', 'Locale list', choices = full_locales)
        global SELECTIONS
        self.locale_dlg.SetSelections(SELECTIONS)
        if (wx.ID_OK == self.locale_dlg.ShowModal()):
                selections = self.locale_dlg.GetSelections()
                SELECTIONS = selections
                global TARGET_LOCALE_LIST
                TARGET_LOCALE_LIST = [full_locales[x] for x in selections]
                selected_locale_str = self.getTimestamp() + ' [' + str(len(TARGET_LOCALE_LIST)) + ' locale(s)] ' + (', ').join(TARGET_LOCALE_LIST)    + '\n'
                self.msgLabel.AppendText(selected_locale_str)
                self.locale_dlg.Destroy()
    
    def printLog(self, message):
        self.msgLabel.AppendText(self.getTimestamp() + ' ' + str(message) + '\n')
    
    def getValueFromJsonStr(self, json_str, option = 0):
        # option:
        # 0, default value, return scriptor name, like "Nancy Huang", "Allen Xu"
        # 1, return scriptor name + email, like "Amy Liu(nhb468@motorola.com)"
        # 2, check if the screen was replaced, return 1 if yes, return 0 if no.

        if '' == json_str or None == json_str:
            if 2 == option:
                return 0
            else:
                return ''

        json_dict = eval(json_str)

        if 0 == option:
            if "executor" in json_dict:
                return json_dict["executor"][:json_dict["executor"].index("(")]
            else:
                return ''
        elif 1 == option:
            if "executor" in json_dict:
                return json_dict["executor"]
            else:
                return ''
        elif 2 == option:
            if "replaced" not in json_dict:
                return 0
            else:
                return 1
        else:
            return '' # There should be an error here.

    def checkDupScreen(self, DB_file_list):
        self.printLog("Start to check dup screen...")
        temp_en_screenlib_DB = "temp_en_screenlib.sqlite"
        if os.path.isfile(temp_en_screenlib_DB):
            try:
                os.remove(temp_en_screenlib_DB)
            except WindowsError, e:
                self.printLog(e)
                self.printLog("Fail to delete old en-US screen lib file, pls check whether the file is already opened by other process and try again.")
                return False
            finally:
                pass
        conn = lite.connect(temp_en_screenlib_DB)
        cur = conn.cursor()
        cur.execute("create table screenlib (screenname text, scriptname text, tags text, path text)")
        conn.commit()
        conn.close()
        
        self.printLog("Building en-US screen lib...")
        for i in range(1, len(DB_file_list) + 1):
            conn_db_file = lite.connect(DB_file_list[i-1])
            cur_db_file = conn_db_file.cursor()
            cur_db_file.execute("select distinct screenname, scriptname, tags from screens where locale = " + '\'' + 'en' + '\'')
            for f in cur_db_file.fetchall():
                conn_en_db = lite.connect(temp_en_screenlib_DB)
                cur_en_db = conn_en_db.cursor()
                cur_en_db.execute("insert into screenlib values (" + '\'' + f[0] + '\', \'' + f[1] + '\', \'' + f[2] + '\', \'' + DB_file_list[i-1] + '\')')
                conn_en_db.commit()
                conn_en_db.close()
            conn_db_file.close()
            self.printLog(str(i) + " / " + str(len(DB_file_list)) + "...")
        self.printLog("en-US screen lib is ready...")
        
        self.printLog("Checking dup screen...")
        conn_en_db = lite.connect(temp_en_screenlib_DB)
        cur_en_db = conn_en_db.cursor()
        cur_en_db.execute("select * from screenlib where screenname in (select screenname from screenlib group by screenname having count(screenname) > 1)")
        dup_list = cur_en_db.fetchall()
        dup_list.sort()
        len_of_dup_list = len(dup_list)
        if 0 == len_of_dup_list:
            self.printLog("Great! No duplicate screen found!")
        else:
            self.printLog("")
            self.printLog("***** Attention!!! Duplicate screen found!!! ****")
            self.printLog("")
            dup_screen_webpage = PyH('Duplicate Screen List')
            dup_screen_webpage << h1('Duplicate Screen List')
            
            dup_screen_tab = dup_screen_webpage << table(border = "1")
            dup_tab_row1 = dup_screen_tab  << tr(bgcolor=rowname_bgcolor_value)
            dup_tab_row1 << td('Index', bgcolor='DarkSlateGray',
                                        style='color:white;') + td('Screen name',
                                        bgcolor='DarkSlateGray', style='color:white;') + td('Script name',
                                        bgcolor='DarkSlateGray', style='color:white;') + td('Scriptor',
                                        bgcolor='DarkSlateGray', style='color:white;') + td('In which DB file',
                                        bgcolor='DarkSlateGray', style='color:white;')

            for x in range(0, len_of_dup_list):
                dup_tab_row2 = dup_screen_tab << tr()
                
                if (x % 2 == 0):
                    row2_bgcolor = 'White'
                else:
                    row2_bgcolor = 'LightGrey'
                
                dup_tab_row2 << td(str(x + 1), align="center",
                                        bgcolor=row2_bgcolor) + td(dup_list[x][0],
                                        bgcolor=row2_bgcolor) + td(dup_list[x][1],
                                        bgcolor=row2_bgcolor) + td(self.getValueFromJsonStr(dup_list[x][2]),
                                        bgcolor=row2_bgcolor) + td(dup_list[x][3].replace('\\\\', '\\'),
                                        bgcolor=row2_bgcolor)
            
            dup_list_url = strftime("Dup_screen_list_%Y%m%d_%H%M%S.html", time.localtime())
            dup_screen_webpage.printOut(dup_list_url)
            webbrowser.open(dup_list_url)

        return True

    def countScreenSum(self, DB_file_list):
        self.printLog("Start to count screen sum, it may take some time...")
        total_screen_sum = 0
        en_screen_sum = 0
        counter = 0
        DB_list_len = len(DB_file_list)
        
        for i in DB_file_list:
            temp_conn = lite.connect(i)
            temp_cur = temp_conn.cursor()

            temp_cur.execute("select count(screenname) from screens")
            total_screen_sum = temp_cur.fetchone()[0] + total_screen_sum
            
            temp_cur.execute("select count(screenname) as en_screen from screens where locale = 'en'")
            en_screen_sum = temp_cur.fetchone()[0] + en_screen_sum

            counter = counter +1
            
            self.printLog(str(counter) + " / " + str(DB_list_len) + "...")
        
        temp_conn.close()
        self.printLog("Total en-US screen sum: " + str(en_screen_sum))
        self.printLog("Total screen sum: " + str(total_screen_sum))
        
        return True


    def DBanalysis(self, DB_file_list):
        self.printLog("Start to analyse, it may take some time...")


        try:
            lib_table_name = ''
            if '' == TARGET_BUILD or 'AVIK' != TARGET_BUILD:
                lib_table_name = strftime("tmp%Y%m%d_%H%M%S", time.localtime())
            else:
                if '' == TARGET_LABEL:
                    self.printLog("Please specify the label.")
                    return False
                else:
                    lib_table_name = TARGET_LABEL
            
            
            mysql_conn=MySQLdb.connect(host=mysql_IP, user='reed', passwd='123456', db='screenlib', port=3306)

            mysql_cur=mysql_conn.cursor()
            mysql_cur.execute("create table %s (screenname varchar(127), scriptname varchar(127), locale varchar(31), scriptor varchar(31), replaced int, sqlitename varchar(31), folder varchar(63), sdate varchar(31), stime varchar(31))" % lib_table_name) 

            #~ mysql_cur.execute("truncate lib") # clear the lib table firstly
 
            self.printLog("Building lib file...")
            DB_list_len = len(DB_file_list)

            for i in range(1, DB_list_len + 1):
                conn_db_file = lite.connect(DB_file_list[i-1])
                cur_db_file = conn_db_file.cursor()
                cur_db_file.execute("select screenname, scriptname, locale, tags, modtime from screens")
                for f in cur_db_file.fetchall():
                    scriptor_name = self.getValueFromJsonStr(f[3])
                    replaced_value = self.getValueFromJsonStr(f[3], 2)
                    sqlitename_value = DB_file_list[i-1][DB_file_list[i-1].rfind("\\"):][1:]
                    #~ print DB_file_list[i-1]
                    folder_value = DB_file_list[i-1][:((len(sqlitename_value) +1) * -1 )][DB_file_list[i-1][:((len(sqlitename_value) +1) * -1 )].rfind("\\")+1:]
                    #~ print folder_value
                    date_value = f[4][:10]
                    time_value = f[4][-8:]

                    mysql_cur.execute("insert into %s values ('%s', '%s', '%s', '%s', %s, '%s', '%s', '%s', '%s')" % (lib_table_name, f[0], f[1], f[2], scriptor_name, str(replaced_value), sqlitename_value, folder_value, date_value, time_value))
                    mysql_conn.commit()

                cur_db_file.close()
                conn_db_file.close()
                self.printLog(str(i) + " / " + str(DB_list_len) + "...")
                
            self.printLog("lib is ready...")
            self.buildReport(DB_list_len, lib_table_name)
            #~ if '' == TARGET_BUILD or 'AVIK' != TARGET_BUILD:
                #~ mysql_cur.execute("drop table %s" % lib_table_name)
            return True
            
        except MySQLdb.Error, e:
            self.printLog("Mysql Error %d: %s" % (e.args[0], e.args[1]))


        finally:
            if mysql_cur:
                mysql_cur.close()
            if mysql_conn:
                mysql_conn.close()


    def buildReport(self, DB_number, lib_table_name):
        self.printLog("Building report...")
        
        mysql_conn=MySQLdb.connect(host=mysql_IP,user='reed',passwd='123456',db='screenlib',port=3306)
        mysql_cur=mysql_conn.cursor()
        
        bgcl = "LightGrey"
        DB_report_webpage = PyH('AViK DB Analysis Report')
        DB_report_webpage << h1('AViK DB Analysis Report', align="center")
        
        DB_report_webpage << h6('')
        DB_report_webpage << h3('Overall')
        
        
        # DB folder: C:\Users\xkqj34\Desktop\_1_work\1\Migrate11_Rd1_20130902
        # DB number: 20
        agenda_tab = DB_report_webpage << table(border = "0")
        tr_folder = agenda_tab << tr()
        
        tr_folder << td("DB folder:", align="right") << td(TARGET_DIR)
        tr_sqlite_number = agenda_tab << tr()
        tr_sqlite_number << td("DB number:", align="right") << td(DB_number)
        tr_label = agenda_tab << tr()
        tr_label << td("Round label:", align="right") << td(TARGET_LABEL)
        
        DB_report_webpage << p('')
        
        #                      Total screen #        Replaced screen #                          %
        #                           Screen #        67322                    8722                      21%
        
        table2_tab = DB_report_webpage << table(border = "1")
        tr_screen_replace = table2_tab << tr(bgcolor = bgcl, align="center")
        tr_screen_replace << td('') << td("Total screen #") << td("Rep #") << td("Rep %")
        tr_screen_replace_number = table2_tab << tr(align="center")
        
        mysql_cur.execute("select count(screenname) from %s" % lib_table_name)
        total_screen_number = mysql_cur.fetchone()[0]
        mysql_cur.execute("select count(screenname) from %s where replaced = 1" % lib_table_name)
        replaced_screen_number = mysql_cur.fetchone()[0]
        tr_screen_replace_number << td('Screen #') << td(str(total_screen_number)) << td(str(replaced_screen_number)) << td("%.1f" % (replaced_screen_number / ( total_screen_number * 1.0) * 100 ) + "%")
        
        DB_report_webpage << p('')
        DB_report_webpage << h3('Screen sum per locale')
        #                No.:  1,  2,  3,  4
        #           Locale:   en  es es-US de fr it
        # Total Screen:   90, 89, 90, 88, 88
        locale_screen_tab = DB_report_webpage << table(border = "1")
        tr_locale_index = locale_screen_tab << tr()
        tr_locale_index << td("No.", align="right")
        tr_locale = locale_screen_tab << tr(bgcolor = bgcl)
        tr_locale << td("Locale", align="right")
        tr_locale_screen_no = locale_screen_tab << tr()
        tr_locale_screen_no << td("Screen # ", align="right", )

        mysql_cur.execute('select distinct locale from %s' % lib_table_name)
        draft_locale_list = mysql_cur.fetchall()
        locale_list = [i[0] for i in draft_locale_list]
        global temp_index
        for i in locale_list:
            temp_index = temp_index + 1
            tr_locale_index << td(str(temp_index), align="center", width="55px")
            mysql_cur.execute("select count(screenname) from %s where locale = '%s'" % (lib_table_name, i))
            if 'en' != i:
                tr_locale << td(i, align="center", width="55px")
                tr_locale_screen_no << td(str(mysql_cur.fetchone()[0]), align="center", width="55px")
            else:
                tr_locale << td(i, align="center", style='color:MediumBlue;', width="55px")
                tr_locale_screen_no << td(str(mysql_cur.fetchone()[0]), align="center", style='color:MediumBlue;', width="55px")
        temp_index = 0
        
        DB_report_webpage << p('')
        DB_report_webpage << h3('App Summary')
        #           Folder/app:   Calendar_LATAM        Settings_EMEA                  Settings_SEA
        #         En screen #:             220                              829                                    950
        #      Total screen #:            22323                             42322                                 98282
        #    Replaced screen #:           223                                422                                   422
        #                   % :
        folder_tab = DB_report_webpage << table(border = "1")
        tr_folder_name = folder_tab << tr(bgcolor = bgcl)
        tr_folder_name << td("App", align="right", width="70px")
        tr_folder_en = folder_tab << tr()
        tr_folder_en << td("en-US", align="right", width="70px")
        tr_folder_total = folder_tab << tr()
        tr_folder_total << td("Total", align="right", width="70px")
        tr_folder_replaced = folder_tab << tr()
        tr_folder_replaced << td("Rep #", align="right", width="70px")
        tr_folder_percent = folder_tab << tr()
        tr_folder_percent << td("Rep %", align="right", width="70px")
        
        mysql_cur.execute('select distinct folder from %s' % lib_table_name)
        folder_list = [q[0] for q in mysql_cur.fetchall()]
        for i in folder_list:
            tr_folder_name << td(i, align="center")
            mysql_cur.execute("select count(screenname) from %s where folder = '%s' and locale = 'en'" % (lib_table_name, i))
            tr_folder_en << td(mysql_cur.fetchone()[0], align="center")
            mysql_cur.execute("select count(screenname) from %s where folder = '%s'" % (lib_table_name, i))
            folder_total = mysql_cur.fetchone()[0]
            tr_folder_total << td(str(folder_total), align="center")
            mysql_cur.execute("select count(screenname) from %s where folder = '%s' and replaced = 1" % (lib_table_name, i))
            folder_replaced = mysql_cur.fetchone()[0]
            tr_folder_replaced << td(str(folder_replaced), align="center")
            replaced_rate = "%.1f" % (folder_replaced / (folder_total * 1.0) * 100)
            if "0.0" == replaced_rate:
                tr_folder_percent << td(" - ", align="center")
            else:
                tr_folder_percent << td(replaced_rate + "%", align="center")

        DB_report_webpage << p('')
        DB_report_webpage << h3('Detail Data per Script')
        # No.        Scriptname             En #      Total #           Rep #          Rep %      Locale #  Locale List        Scriptor
        #  1              Settings_main        78         8772             80                     5%            4           en, es-US,       Beth Du, Allen Xu
        script_data_tab = DB_report_webpage << table(border = "1")
        tr1_script_data = script_data_tab << tr(bgcolor = bgcl, align="center")
        tr1_script_data << td("No.") << td("Scriptname") << td("En #")<< td("Total #") << td("Rep #") << td("Rep %") << td("Locale #") << td("Locale list")<< td("Scriptor")
        mysql_cur.execute('select distinct scriptname from %s' % lib_table_name)
        script_list_in_lib = [b[0] for b in mysql_cur.fetchall()]
        script_data_list = []
        for y in range(0, len(script_list_in_lib)): 
            mysql_cur.execute("select count(screenname) from %s where locale = 'en' and scriptname = '%s' " % (lib_table_name, script_list_in_lib[y]))
            script_en_sum = mysql_cur.fetchone()[0]
            mysql_cur.execute("select count(screenname) from %s where scriptname = '%s' " % (lib_table_name, script_list_in_lib[y]))
            script_screen_sum = mysql_cur.fetchone()[0]
            mysql_cur.execute("select count(screenname) from %s where scriptname = '%s' and replaced = 1" % (lib_table_name, script_list_in_lib[y]))
            script_rep_sum = mysql_cur.fetchone()[0]
            mysql_cur.execute("select count(distinct locale) from %s where scriptname = '%s' " % (lib_table_name, script_list_in_lib[y]))
            script_locale_sum = mysql_cur.fetchone()[0]
            mysql_cur.execute("select distinct locale from %s where scriptname = '%s' " % (lib_table_name, script_list_in_lib[y]))
            draft_script_locale_list = mysql_cur.fetchall()
            script_locale_list = [h[0] for h in draft_script_locale_list]
            script_locale_list_str = ', '.join(script_locale_list)
            draft_script_scriptor_list = []
            mysql_cur.execute("select distinct scriptor from %s where scriptname = '%s'" % (lib_table_name, script_list_in_lib[y]))
            for j in mysql_cur.fetchall():
                draft_script_scriptor_list.append(j[0])
            script_scriptor_str = ', '.join(draft_script_scriptor_list)
            
            rep_rate_per_script = script_rep_sum / (script_screen_sum * 1.0) * 100
            
            script_data_list.append([rep_rate_per_script, #  0
                                            script_en_sum,    #  1
                                            script_list_in_lib[y], #  2
                                            script_screen_sum, #  3
                                            script_rep_sum, #  4
                                            script_locale_sum, #  5
                                            script_locale_list_str, #  6
                                            script_scriptor_str]) #  7
        script_data_list.sort()
        script_data_list.reverse()
        for e in range(0, len(script_data_list)):
            tr2_script_data = script_data_tab << tr(align="center")
            tr2_script_data << td(str(e+1))   # No.
            tr2_script_data << td(script_data_list[e][2], align="left") # Scriptname
            tr2_script_data << td(str(script_data_list[e][1])) # En #
            tr2_script_data << td(str(script_data_list[e][3])) # Total #
            tr2_script_data << td(str(script_data_list[e][4])) # Rep #
            if 0 == script_data_list[e][0]:
                tr2_script_data << td("-")      # Rep %
            elif script_data_list[e][0] < 20:
                tr2_script_data << td("%.1f" % script_data_list[e][0] + "%")
            elif script_data_list[e][0] < 49:
                tr2_script_data << td("%.1f" % script_data_list[e][0] + "%", bgcolor = "Khaki")
            else:
                tr2_script_data << td("%.1f" % script_data_list[e][0] + "%", bgcolor = "Yellow")
            
            tr2_script_data << td(str(script_data_list[e][5]))   # Locale #
            tr2_script_data << td(script_data_list[e][6], align="left")   # Locale list
            tr2_script_data << td(script_data_list[e][7])  # Scriptor

        DB_report_webpage << p('')
        DB_report_webpage << h3('Data per Day')
        #       Date                 Total Screen #           Total en #           Nightly #     Nightly %         Labor         Screen/Person                      Scriptor List
        #   2013-09-09          98282                           3892                   302                  8%                 9                       789                       Beth Du, Allen Xu, Nancy Huang
        
        mysql_cur.execute("select distinct sdate from %s" % lib_table_name)
        draft_date_list = mysql_cur.fetchall()
        date_list = [r[0] for r in draft_date_list]
        date_list.sort()
        
        date_tab = DB_report_webpage << table(border = "1")
        tr_date_name = date_tab << tr(bgcolor = bgcl, align="center")
        tr_date_name << td("Date") << td("Total Screen #") << td("Total en-US #") << td("Labor #") << td("Screen/Person") << td("Scriptor")
        #~ print date_list
        for i in range (0, len(date_list)):
            tr_date_data = date_tab << tr(align="center")
            mysql_cur.execute("select count(screenname) from %s where sdate = '%s'" % (lib_table_name, date_list[i]))
            date_total_screen_sum = mysql_cur.fetchone()[0]
            mysql_cur.execute("select count(screenname) from %s where sdate = '%s' and locale = 'en'" % (lib_table_name, date_list[i]))
            date_en_screen_sum = mysql_cur.fetchone()[0]
            mysql_cur.execute("select count(distinct scriptor) from %s where sdate = '%s' and scriptor <> '' " % (lib_table_name, date_list[i]))
            date_labor_sum = mysql_cur.fetchone()[0]
            mysql_cur.execute("select distinct scriptor from %s where sdate = '%s'" % (lib_table_name, date_list[i]))
            #~ print mysql_cur.fetchall()
            name_list = []
            for n in mysql_cur.fetchall():
                if '' != n[0]:
                    name_list.append(n[0])
            date_scriptor_str = ', '.join(name_list)

            tr_date_data << td(date_list[i])
            tr_date_data << td(str(date_total_screen_sum))
            tr_date_data << td(str(date_en_screen_sum))
            tr_date_data << td(str(date_labor_sum))
            if  0 != date_labor_sum:
                tr_date_data << td("%.1f" % ( date_total_screen_sum / (date_labor_sum * 1.0)))
            else:
                tr_date_data << td("-")
            tr_date_data << td(date_scriptor_str, align="left")
        DB_report_webpage << p('')
        DB_report_webpage << h3('Data per Person')
        #    No.   Scriptor          Total Screen #   Rep #   Rep %
        #    1       Amilia Li        298111                  321          8.9%
        
        scriptor_tab = DB_report_webpage << table(border = "1")
        r1_scriptor_tab = scriptor_tab << tr(bgcolor = bgcl, align="center")
        r1_scriptor_tab << td("No.") << td("Scriptor") << td("Total #") << td("Rep #") << td("Rep %")
        for g in range(0, len(date_list)):
            r1_scriptor_tab << td(date_list[g])

        mysql_cur.execute("select distinct scriptor from %s" % lib_table_name)
        scriptor_list = [w[0] for w in mysql_cur.fetchall()]
        scriptor_screen_list = []
        
        for i in scriptor_list:
            mysql_cur.execute("select count(screenname) from %s where scriptor = '%s'" % (lib_table_name, i))
            scriptor_total_screen = mysql_cur.fetchone()[0]
            mysql_cur.execute("select count(screenname) from %s where scriptor = '%s' and replaced = 1" % (lib_table_name, i))
            scriptor_rep_screen = mysql_cur.fetchone()[0]
            scriptor_rep_rate = "%.1f" % ((scriptor_rep_screen / ( scriptor_total_screen * 1.0)) * 100) + "%"
            scriptor_screen_list.append([scriptor_total_screen, i, scriptor_rep_screen, scriptor_rep_rate])

        scriptor_screen_list.sort()
        scriptor_screen_list.reverse()
        
        for i in range(0, len(scriptor_screen_list)):
            r2_scriptor_tab = scriptor_tab << tr(align="center")
            r2_scriptor_tab << td(str(i + 1)) << td(scriptor_screen_list[i][1]) << td(str(scriptor_screen_list[i][0])) << td(str(scriptor_screen_list[i][2])) << td(scriptor_screen_list[i][3]) 
            for xt in range(0, len(date_list)):
                mysql_cur.execute("select count(screenname) from %s where scriptor = '%s' and sdate = '%s'" % (lib_table_name, scriptor_screen_list[i][1], date_list[xt]))
                r2_scriptor_tab << td(str(mysql_cur.fetchone()[0]))

        # List of screens without scriptor tag
        #   No.              Screenname                      Script                            locale
        #   1                 Settings_main           avik.settings.main                en-US
        #~ mysql_cur.execute("select screenname, scriptname, locale, sqlitename from %s where scriptor =''" % lib_table_name)
        #~ missing_tag_list = mysql_cur.fetchall()
        #~ if 0 != len(missing_tag_list):
            #~ DB_report_webpage << p('')
            #~ DB_report_webpage << h3("List of screens with missing scriptor tag")
            #~ missing_tag_tab = DB_report_webpage << table(border = "1")
            #~ r1_missing_tag_tab = missing_tag_tab << tr(bgcolor = bgcl, align="center")
            #~ r1_missing_tag_tab << td("No.") << td("Screenname") << td("Scriptname") << td("Locale") << td("DB file name")

            #~ for i in range(0, len(missing_tag_list)):
                #~ r2_missing_tag_tab = missing_tag_tab << tr(align="center")
                #~ r2_missing_tag_tab << td(str(i + 1)) << td(missing_tag_list[i][0], align="left") << td(missing_tag_list[i][1], align="center") << td(missing_tag_list[i][2]) << td(missing_tag_list[i][3])
        
        if 'AVIK' != TARGET_BUILD:
            mysql_cur.execute("drop table %s" % lib_table_name)
        
        mysql_conn.close()
        mysql_cur.close()
        
        
        avikreport_page_url = strftime("AViK_Report_%Y%m%d_%H%M%S.html", time.localtime())
        DB_report_webpage.printOut(avikreport_page_url)
        self.printLog("Done.")
        self.printLog("")
        webbrowser.open(avikreport_page_url)


    def OnClickRun(self, event):
        self.runButton.Disable()

        global starttime
        starttime = time.clock()

        global TARGET_DIR
        global TARGET_LABEL
        global REQUIRE_SYNC_CHECK
        global REQUIRE_CLOUD_SYNC_CHECK
        global result_page
        global FINISHED_DB_COUNT
        global SQLITE_COUNT
        global EN_SCREEN_NUMBER
        global error_number
        global TARGET_BUILD
        
        EN_SCREEN_NUMBER = 0 # Reset EN_SCREEN_NUMBER
        error_number = 0 # Reset error_number to 0
        TARGET_DIR = self.dirBrowser.GetPath()
        TARGET_LABEL = self.labelTxtBox.GetRange(0, -1)
        TARGET_BUILD = self.buildTxtBox.GetRange(0, -1)
        REQUIRE_SYNC_CHECK = self.checkSyncBox.GetValue()
        REQUIRE_CLOUD_SYNC_CHECK =  self.checkCloudSyncBox.GetValue()

                
        # Validate parameters before calling main function -> self.sqliteHandler()
        if (not self.validateParameter(TARGET_DIR)):
            self.printLog('DB folder is None.')
            self.runButton.Enable()

        elif True == self.checkDupBox.GetValue() or True == self.DBanalysisBox.GetValue() or True == self.countScreenSumBox.GetValue():
            if  True == self.checkDupBox.GetValue() and True == self.DBanalysisBox.GetValue() and True == self.countScreenSumBox.GetValue():
                self.printLog('Pls select only one of the 3 functions*.')
                self.runButton.Enable()

            elif True == self.countScreenSumBox.GetValue():
                self.updateFileList(TARGET_DIR)
                if self.countScreenSum(FILELIST_IN_TARGET_DIR):
                    self.printLog('Done.')
                self.runButton.Enable()

            elif True == self.checkDupBox.GetValue():
                self.updateFileList(TARGET_DIR)
                if self.checkDupScreen(FILELIST_IN_TARGET_DIR):
                    self.printLog('Finish checking dup screen.')
                self.runButton.Enable()

            elif True == self.DBanalysisBox.GetValue():
                self.updateFileList(TARGET_DIR)
                self.DBanalysis(FILELIST_IN_TARGET_DIR)
                self.runButton.Enable()
        # ------------------------------------------------------------------------------------------
        # ------------------------------------------------------------------------------------------
        # ------------------------------------------------------------------------------------------
        # ------------------------- Check screens sum feature ends here -----------------------
        # -------------------------If need add more function -----------------------------------
        # ------------------------- Just add code here -------------------------------------------
        # ------------------------------------------------------------------------------------------
        # ------------------------------------------------------------------------------------------
        # ------------------------------------------------------------------------------------------
        else:
            self.printLog('Sqlitechecker start to check...')
            self.updateFileList(TARGET_DIR) # Check TARGET_DIR and create sqlite file list FILELIST_IN_TARGET_DIR
            global SQLITE_COUNT
            SQLITE_COUNT = len(FILELIST_IN_TARGET_DIR)
            
            # ------------- Code for Cloud Sync Check ------------------

            if REQUIRE_CLOUD_SYNC_CHECK:
                global cloud_service
                global bad_screen_list
                cloud_service = self.get_authenticated_service(RO_SCOPE)
                bad_screen_list = [] # Reset the missing file list to empty.
            
            # ------------- Code for Cloud Sync Check ------------------
            
            # HTML: create table like below:
            #                     Sqlite count        9
            #              Total en screen #     89
            #              Expected label        JB_Round1_20121112
            #             Expected locale        en, en-GB, it, fr
            result_page = PyH('AViK Sqlite content analysis')
            tab_overall_infor = result_page << table(border = "0", style=OVERALL_TAB_STYLE)
            tr_dir_overall = tab_overall_infor << tr()
            tr_dir_overall << td('[Label: %s]' % TARGET_LABEL)
            tr_dir_overall << td('[Build: %s]' % TARGET_BUILD)
            tr_dir_overall << td('[%s locale: %s]' % (len(TARGET_LOCALE_LIST), (', ').join(TARGET_LOCALE_LIST) ) )

            if (0 == SQLITE_COUNT):
                self.printLog('0 DB file is found in the folder...')
                self.printLog('Done.')
                self.runButton.Enable()
            else:
                try:
                    self.printLog('Find %s DB file(s) in the folder...' %SQLITE_COUNT)
                    global screen_conn
                    if REQUIRE_SYNC_CHECK:
                        screen_conn = SMBConnection(SS_USER, SS_PW, "anyname", "", use_ntlm_v2 = True)
                        if (not screen_conn.connect(SS_IP, SS_PORT)):
                            self.printLog('Fail to connect to local screen server.')
                        #-----------------------------------------------
                        #--- Main function entry -> sqliteHandler()
                        #-----------------------------------------------

                    for each_sqlite_path in FILELIST_IN_TARGET_DIR:
                        # For each sqlite item, launch sql_execute() to get values and add html code
                        self.sqliteHandler(each_sqlite_path)
                    
                    # Code works for Google Cloud sync check
                    if len(bad_screen_list) > 0:
                        self.printLog('----------------------- Cloud Sync error -----------------------')
                        self.printLog('----------------------- Cloud Sync error -----------------------')
                        self.printLog('---------------- Missing screens listed in DB report -----------')
                        result_page << h4("Screens not synced to GCS bucket - %s:" % bucket_name)
                        the_bad_list = result_page << ol() # Define a list with number
                        for i in bad_screen_list:
                            the_bad_list << li(i)
                            
                    #-----------------------------------------------
                    #--- Finally output as web page
                    #------------------------------------------------
                    execution_time = time.clock() -starttime
                    result_page << h6('Sqlite analysis is done in %.6f second(s) ' % execution_time, align="center", style='color:Gray;')
                    tr_dir_overall << td('[Total en screens: %s]' % EN_SCREEN_NUMBER, )
                    tr_dir_overall << td('[Error count: %s]' % error_number, )

                    result_page_url = strftime("Result_%Y%m%d_%H%M%S.html", time.localtime())
                    result_page.printOut(result_page_url)
                    
                    # ---------------------------------------- TEST CODE --------------------------------------
                    webbrowser.open(result_page_url)
                    # ---------------------------------------- TEST CODE --------------------------------------
                    self.runButton.Enable()
                    self.printLog('Done.')
                    self.printLog('Execution time: [%.3f] second(s)' % execution_time)
                    #~ if len(bad_screen_list) > 0: # For Cloud Sync check, print out the missing screen
                        #~ for i in bad_screen_list:
                            #~ self.printLog(i)
                    
                    SQLITE_COUNT = 0
                    FINISHED_DB_COUNT = 0

                except IOError, e:
                    self.printLog('Error %s' % e.args[0])
                    self.printLog('IOError')
                    self.runButton.Enable()
                
                finally:
                    if screen_conn:
                        screen_conn.close()
    
    def getTimestamp(self):
        return '[' + strftime("%H:%M:%S", time.localtime()) + ']'
    
    def addOneErrorNumber(self):
        global error_number
        error_number = error_number + 1

    def scriptHandler(self, each_script):
        """
        Analyse the sqlite per script and add HTML code to result_page.
        """
        global result_page
        global cur
        
        en_screen_number = 0 # Initial the en screen number to 0.
        
        each_script = each_script[0] # Update this value, it was ['avik_script.js',]

        # HTML: creat table like below
        #                                Script 1	          L1_Settings_main.js
        #                                   Locale	          Pass
        #                                      Label	     Pass
        #                           Screen sync	          Pass
        #                         Watermark	         Pass
        #                             Scripter	             Fang Hepeng

        tab_scriptDB_infor = result_page << table(border = "1", style=SCRIPT_DB_TAB_STYLE)
        tr_script = tab_scriptDB_infor << tr()
        tr_locale_result = tab_scriptDB_infor << tr()
        tr_label_result = tab_scriptDB_infor << tr()
        tr_build_result = tab_scriptDB_infor << tr()
        tr_screensync_result = tab_scriptDB_infor << tr()
        tr_wm = tab_scriptDB_infor << tr()
        tr_time = tab_scriptDB_infor << tr()
        tr_scripter = tab_scriptDB_infor << tr()
        
        tr_script << td('Script', align="right", bgcolor=rowname_bgcolor_value)<<td(each_script)

        cur.execute('select distinct locale from scripts where scriptname = ' + '\'' + each_script +'\'')
        #~ actual_locale_list = []
        #~ for i in cur.fetchall():
            #~ actual_locale_list.append(i[0])
            
        actual_locale_list = [i[0] for i in cur.fetchall()]
            
        # HTML 3.5 Check if endtime or startime is none.
        cur.execute('select starttime, endtime from scripts where scriptname = ' + '\'' + each_script + '\'')
        time_string_result = None
        for time in cur.fetchall():
            if (None == time[0] or None == time[1] or '' == time[0] or '' == time[1]):
                time_string_result = False
                break
            else:
                time_string_result = True
        if time_string_result:
            tr_time << td('Time', align="right", bgcolor=rowname_bgcolor_value) << td('Pass')
        else:
            tr_time << td('Time', align="right", bgcolor=rowname_bgcolor_value) << td('starttime or endtime is None', style='color:red;', align = "left")
            self.addOneErrorNumber()

        # HTML 1: Call validateLocale() to verify locales and return (isLocaleCorrect, locale_string)
        # HTML 1: Add result of Locale Check
        isLocaleCorrect, locale_string = self.validateLocale(set(actual_locale_list), set(TARGET_LOCALE_LIST))
        if isLocaleCorrect:
            tr_locale_result << td('Locale', align="right", bgcolor=rowname_bgcolor_value) << td('Pass')
        else:
            tr_locale_result << td('Locale', align="right", bgcolor=rowname_bgcolor_value) << td(locale_string, style='color:red;', align = "left")
            self.addOneErrorNumber()
        
        # HTML: Row 2 -> it will verify the lable( check if it equals **TARGET_LABEL**)
        cur.execute('select distinct build from scripts where scriptname = ' + '\'' + each_script + '\'')
        actual_label_list = cur.fetchall()
        #~ print 'Start to check lable, now TARGET_LABEL is' + TARGET_LABEL
        if len(actual_label_list) > 1:            
            tr_label_result << td('Label', align="right", bgcolor=rowname_bgcolor_value) << td("2+ labels!", style='color:red;', align = "left")
            self.addOneErrorNumber()
        elif '' == TARGET_LABEL or None == TARGET_LABEL:
            tr_label_result << td('Label', align="right", bgcolor=rowname_bgcolor_value) << td(" -")
        elif TARGET_LABEL == actual_label_list[0][0]:
            tr_label_result << td('Label', align="right", bgcolor=rowname_bgcolor_value) << td("Pass")
        else:
            tr_label_result << td('Label', align="right", bgcolor=rowname_bgcolor_value) << td("Incorrect label or other error!", style='color:red;', align = "left")
            self.addOneErrorNumber()
        
        # HTML: Row 2.5 -> verify the build, check whether it == **TARGET_BUILD**
        cur.execute('select distinct devicebuild from scripts where scriptname = ' + '\'' + each_script + '\'')
        actual_build_list = cur.fetchall()
        if len(actual_build_list) > 1:            
            tr_build_result << td('Build', align="right", bgcolor=rowname_bgcolor_value) << td("2+ builds!", style='color:red;', align = "left")
            self.addOneErrorNumber()
        elif '' == TARGET_BUILD:
            tr_build_result << td('Build', align="right", bgcolor=rowname_bgcolor_value) << td(" -")
        elif TARGET_BUILD == actual_build_list[0][0]:
            tr_build_result << td('Build', align="right", bgcolor=rowname_bgcolor_value) << td("Pass")
        else:
            tr_build_result << td('Build', align="right", bgcolor=rowname_bgcolor_value) << td(actual_build_list[0][0], style='color:red;', align = "left")
            self.addOneErrorNumber()
        
        # HTML: Row 3 -> check screenshot sync status
        if REQUIRE_SYNC_CHECK:
            cur.execute('select screenhash, scriptname, build, locale from screens where scriptname = ' + '\'' + each_script + '\'')
            screen_infor = tuple(cur.fetchall())
            
            tmp_sync_result = True # Fix the bug - tmp_sync_result need be defined here to get bigger scope
            
            for i in screen_infor:
                tmp_diskNo = str((int(i[0], 36) % 4 + 1))
                if self.validateScreenSync(tmp_diskNo, i[2], i[3], i[1].replace('.js', ''), i[0]):
                    tmp_sync_result = True
                else:
                    tmp_sync_result = False
                    break
                
            if tmp_sync_result:
                tr_screensync_result << td('Screen sync', align="right", bgcolor=rowname_bgcolor_value) << td("Pass")
            else:
                tr_screensync_result << td('Screen sync', align="right", bgcolor=rowname_bgcolor_value) << td("Fail", style='color:red;', align = "left")
                self.addOneErrorNumber()
        
        
        # Cloud Sync Check function, created on 04/14/2014
        
        if REQUIRE_CLOUD_SYNC_CHECK:
            
            if not os.path.exists(CLIENT_SECRETS_FILE): # Check if the secrets file there
                self.printLog("Client secrets file is not found!")
            else:
                global bad_screen_list
                
                cur.execute('select screenhash, scriptname, build, locale from screens where scriptname = ' + '\'' + each_script + '\'')
                screen_infor = tuple(cur.fetchall())

                for i in screen_infor:
                    # (u'cotc07eep7ovv7ciwo0arttkl', u'avik.fmradio.dvx.FMRadioMain', u'FM0103_R1_20140305', u'ja-JP')
                    if not self.isScreenInCloud(i[0] + '.png', i[2] + '/' + i[3] + '/' + i[1]):
                        bad_screen_list.append(i[2] + '/' + i[3] + '/' + i[1] + '/' + i[0] + '.png')

        # HTML: Row 4 -> verify water mark status for each screen
        # HTML: Row 5 -> add the name of executor
        isAddWM = None
        cur.execute("select distinct tags from screens where scriptname = " + '\'' + each_script + '\'')
        tags_list = cur.fetchall()
        for tags_item in tags_list: # This for loop is for watermark check only             
            if tags_item[0] != None:
                temp_json_data = eval(tags_item[0]) # use eval() to transfer json string to a dict
                if ( "watermark" not in temp_json_data ) or ("false" == temp_json_data["watermark"]):
                    isAddWM = False
                    break
                else:
                    isAddWM = True
        if isAddWM:
            #~ tab_scriptDB_infor << td('Watermark √')
            tr_wm << td('Watermark', align="right", bgcolor=rowname_bgcolor_value) << td("Pass")
        else:
            tr_wm << td('Watermark', align="right", bgcolor=rowname_bgcolor_value) << td("Fail", style='color:red;', align = "left")
            self.addOneErrorNumber()
        scripter_name_list = []
        for tags_item in tags_list: # This loop is for scripter infor only
            scripter_name_list.append(self.getValueFromJsonStr(tags_item[0])) # add scripter code id to list

        scripter_name_list = ', '.join(list(set(scripter_name_list))) # remove dup item
        tr_scripter << td('Scripter', align="right", bgcolor=rowname_bgcolor_value) << td(scripter_name_list)

        # Output the screen count of each locale
        cur.execute("select count(locale) as a from scripts where scriptname = " + '\'' + each_script + '\'')
        locale_amount = cur.fetchone()

        # HTML: Add the table result_tab, like below
        #                                         1                     2                    3 
        # Locale                en            en-GB        it
        # Screen #        30                30                30
        #
        result_tab = result_page << table(border="1", style=RESULT_TAB_STYLE )
        index_row = result_tab << tr()
        locale_row = result_tab << tr()
        screen_amount_row = result_tab << tr()

        # HTML: add the line like 1, 2, 3, 4, 5...
        index_row << th('', align="right") #width="90px"
        for number_item in range(1, locale_amount[0]+1):
            index_row << th(str(number_item), align="center", width="55px")

        locale_row << td('Locale', align="right", bgcolor=rowname_bgcolor_value)
        screen_amount_row << td('Screen #', align="right", bgcolor=rowname_bgcolor_value)
        cur.execute("select count(screenname) from screens where scriptname = " + '\'' + each_script + '\''    + "and locale = " + '\'' + 'en' + '\'')
        en_screen_number_of_this_script = cur.fetchone()[0]
        #~ print 'en screen :' + str(en_screen_number_of_this_script)

        for each_locale_item in actual_locale_list:
            cur.execute("select count(screenname) from screens where scriptname = " + '\'' + each_script + '\''    + "and locale = " + '\'' + each_locale_item + '\'')
            # Get the value **this_locale_screen_amount**, screen mount of current locale
            this_locale_screen_amount = cur.fetchone()

            if ('en' != each_locale_item and 'pd' != each_locale_item):
                if en_screen_number_of_this_script != this_locale_screen_amount[0]:
                    locale_row << td(each_locale_item, align="center", width="55px", style='color:Red;')
                    screen_amount_row << td(this_locale_screen_amount[0], align="center", width="55px", style='color:Red;')
                else:
                    # HTML: add the line like en, en-US, es, pt-BR..
                    locale_row << td(each_locale_item, align="center", width="55px")
                    # HTML: add the line of screen no., like 20, 20, 20 ...
                    screen_amount_row << td(this_locale_screen_amount[0], align="center", width="55px")
            else:
                global EN_SCREEN_NUMBER
                EN_SCREEN_NUMBER += int(this_locale_screen_amount[0])
                locale_row << td(each_locale_item, align="center", width="55px", style='color:MediumBlue;')
                screen_amount_row << td(this_locale_screen_amount[0], align="center", width="55px", style='color:MediumBlue;')

        result_page << h6('')


    def isScreenInCloud(self, screen_file_name, folder_name):
        
        try:
            request = cloud_service.objects().list( bucket = bucket_name, prefix = folder_name + '/' + screen_file_name)
    
            list_of_screens_in_the_folder = [] # Set the list as empty
            
            # Solution 1:
            #~ while request is not None:
                #~ response = request.execute()
                #~ print json.dumps(response, indent = 0) # For debugging
                #~ encodedjson = json.dumps(response, indent = 0)
                #~ decodejson = json.loads(encodedjson)

                #~ for obj in decodejson['items']:
                    #~ list_of_screens_in_the_folder.append(obj['name'])

                #~ request = cloud_service.objects().list_next(request, response)
                
            # Solution 2:
        
            response = request.execute()
            encodedjson = json.dumps(response, indent = 0)
            decodejson = json.loads(encodedjson)
            
            if 'items' in decodejson:
                if 'name' in decodejson['items'][0]:
                    return True
            else:
                #~ print decodejson
                self.addOneErrorNumber()
                return False

        except Exception, e:
            self.printLog("Exception from isScreenInCloud()")
            self.printLog(e)


    def get_authenticated_service(self, scope):
        self.printLog('GCS authenticating...')
        
        if not os.path.exists(CLIENT_SECRETS_FILE):
            self.printLog("Client secrets file is not found!")
            return
            
        try:
            flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
                                            scope=scope,
                                            message=MISSING_CLIENT_SECRETS_MESSAGE)

            credential_storage = CredentialStorage(CREDENTIALS_FILE)
            credentials = credential_storage.get()
            if credentials is None or credentials.invalid:
                credentials = run_oauth2(flow, credential_storage)

            self.printLog('Constructing Google Cloud Storage service...')
            http = credentials.authorize(httplib2.Http())
            return discovery_build('storage', 'v1beta1', http=http)
            # ^^^ Returns: A Resource object with methods for interacting with the service.
        except Exception, e:
            self.printLog('Exception when getting authenticated service.')
            self.printLog(e)
            print e

    def sqliteHandler(self, sqlite_path):
        """
        This is main function to analyse each sqlite file with updated global values to
        create HTML code accordingly.
        """
        global SQLITE_COUNT
        global con
        global result_page
        global cur
        global FINISHED_DB_COUNT

        try:
            con = lite.connect(sqlite_path)
            cur = con.cursor()

            # Fetch all the script name as list **script_list**
            cur.execute('select distinct scriptname from scripts')
            script_list = cur.fetchall()

            # Create webpage to display the result:
            # HTML: add the current sqlite path
            result_page << h4( '[' + str(FINISHED_DB_COUNT + 1) + '] ' + sqlite_path.replace('\\\\', '\\'), style='color:DarkSlateGray;font-size:14px;')
            
            #-------------------------------------------------------------------
            #---------- Call scriptHandler() to analyse the sqlite per script
            #-------------------------------------------------------------------
            for each_script in script_list:
                self.scriptHandler(each_script)
            FINISHED_DB_COUNT += 1 # After one sqlite is handled, FINISHED_DB_COUNT + 1
            self.msgLabel.AppendText(self.getTimestamp() + ' Checked ' + str(FINISHED_DB_COUNT) + '/' + str(SQLITE_COUNT) + ' DB file(s)...\n')

        except lite.Error, e:
            self.printLog('Error %s' % e.args[0])
            self.printLog('Sqlite connection Error')
            self.printLog('lite.Error')
            self.printLog(' Error %s' % e.args[0])
            sys.exit(1)

        except KeyError, e:
            self.printLog('Error %s' % e.args[0])
            self.printLog('KeyError')
            sys.exit(1)

        finally:
            if con:
                con.close()
    
    def validateScreenSync(self, diskNo, label, locale, scriptName, hashString):
        """
        Validate the screen sync status, generate the URL based on the parameters
        and return True if the screens sync is OK, return False if it's not OK.
        """

        try:
            file_obj_list = []
            file_obj_list = screen_conn.listPath(SS_USER, ''.join(['/', diskNo, '/', label, '/', locale, '/', scriptName, '/']))
            this_screenshot = ''.join([hashString, '.png'])
            png_list_in_server_folder = [i.filename for i in  file_obj_list]
            
            if this_screenshot in png_list_in_server_folder:
                return True
            else:
                self.printLog("----------------------------------- SYNC ERROR -----------------------------------")
                self.printLog("Script: " + scriptName)
                self.printLog("Locale: " + locale)
                self.printLog("Screen: " + this_screenshot)
                self.printLog("diskNo: " + str(diskNo))
                self.printLog("ERROR: the screen png file is not found in specific folder in server. ")
                self.printLog("----------------------------------- SYNC ERROR -----------------------------------")
                return False
        except OperationFailure, e:
            self.printLog("----------------------------------- SYNC ERROR -----------------------------------")
            self.printLog("Script: " + scriptName)
            self.printLog("Locale: " + locale)
            self.printLog("diskNo: " + str(diskNo))
            self.printLog("ERROR: the path cannot be connected. ")
            self.printLog("----------------------------------- SYNC ERROR -----------------------------------")
            #~ self.printLog("Screenname: " + this_screenshot)
            return False
            

    def validateLocale(self, actual_locale_list, expected_locale_list):
        """
        Verify do the actual locale list match required locale list, it will return True/False
        according to validation result. 
        Please note that, the 2 parameters are set, not list.
        """
        if actual_locale_list == expected_locale_list:
            return (True, '')
        elif bool(actual_locale_list < expected_locale_list):
            missing_locale = expected_locale_list - actual_locale_list
            return (False, ''.join(['Missing locale >> ', ', '.join(missing_locale)]))
        else:
            wrong_locale = []
            for i in actual_locale_list:
                if i not in expected_locale_list:
                    wrong_locale.append(i)
            return (False, ''.join(['Incorrect locale >> ', ', '.join(wrong_locale)]))    
     
    def updateFileList(self, path):
        """
        Handle TARGET_DIR to collect all sqlite files and create the list FILELIST_IN_TARGET_DIR
        """
        global FILELIST_IN_TARGET_DIR
        FILELIST_IN_TARGET_DIR = [] # Clear it before updating...
        #~ FILELIST_IN_TARGET_DIR = [os.path.join(root,filespath) for root,dirs,files in os.walk(path) if filespath.endswith('.sqlite')]
        
        for root,dirs,files in os.walk(path):
            for filespath in files:
                if filespath.endswith('.sqlite'):
                    FILELIST_IN_TARGET_DIR.append(os.path.join(root,filespath))
        #~ print "Sqlite list is"
        #~ print FILELIST_IN_TARGET_DIR

        
    def validateParameter(self, path):
        if None == path or '' == path:
            return False
        else:
            return True

if __name__ == '__main__':
    #app = wx.PySimpleApp()
    app = wx.App(False)
    frame = SqChekFrame(parent=None, id=-1)
    frame.Show()
    app.MainLoop()
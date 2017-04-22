#!/usr/bin/env python
# csgoMP.  a csgo music player / soundboard for Linux
# Version 0.0.7
# (c) 2017 Adam Feakin csgomp@csparker.uk
# 

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import os
import shutil
import subprocess
from ConfigParser import SafeConfigParser

from Xlib.display import Display
from Xlib import X
from Xlib.ext import record
from Xlib.protocol import rq
import thread

disp = None


# Change selection when hotkey is pressed
def track_selector(reply):
    data = reply.data
    while len(data):
        event, data = rq.EventField(None).parse_binary_value(data,
                                                             disp.display, None, None)

        print "Keycode pressed: " + str(event.detail)

        # FIXME: Hardcoded keycodes for numpad numbers 0-9 for now.  Need a way to 
        # make this configurable.
        # Change selection on the tree view as if we has clicked it
        if event.detail == 90:
            #print liststore[0][3]
            treeview.get_selection().select_path(0)
        elif event.detail == 87:
            #print liststore[1][3]
            treeview.get_selection().select_path(1)
        elif event.detail == 88:
            #print liststore[2][3]
            treeview.get_selection().select_path(2)
        elif event.detail == 89:
            #print liststore[3][3]
            treeview.get_selection().select_path(3)
        elif event.detail == 83:
            #print liststore[4][3]
            treeview.get_selection().select_path(4)
        elif event.detail == 84:
            #print liststore[5][3]
            treeview.get_selection().select_path(5)
        elif event.detail == 85:
            #print liststore[6][3]
            treeview.get_selection().select_path(6)
        elif event.detail == 79:
            #print liststore[7][3]
            treeview.get_selection().select_path(7)
        elif event.detail == 80:
            #print liststore[8][3]
            treeview.get_selection().select_path(8)
        elif event.detail == 81:
            #print liststore[9][3]
            treeview.get_selection().select_path(9)

class Handler:
    def onDeleteWindow(self, *args):
        save_prefs()
        Gtk.main_quit(*args)

    def show_prefs_cb(self, button):
        # some options
        # csgo install path
        # keybinding for play/stop
        # choose max audio file length, cut if too long (ffmpeg -t option)
        print("Showing config window...")
        push_prefs()
        prefswin.show()

    def save_cfg_cb(self, button):
        print("Save cfg...")
        global ffmpeg_path, csgo_directory, files_count, \
                youtube_dl_path
        csgo_cfg_path = csgo_directory + "/csgo/cfg"
        cfg_filename = csgo_cfg_path + "/csgomp.cfg"

        # delete exising file
        if os.path.isfile(cfg_filename) == True:
            print("Deleting old cfg")
            os.remove(cfg_filename)

        # make a new one
        with open(cfg_filename, "w") as f:
            f.write("echo *** Loading csgomp config ***\n");
            f.write("echo Push to play key: ' \n");
            f.write("echo Toggle playback key: / \n");
            f.write("alias +csgomp_play csgomp_start\n")
            f.write("alias -csgomp_play csgomp_stop\n")
            f.write("alias csgomp_start \"voice_inputfromfile 1; voice_loopback 1; +voicerecord\"\n")
            f.write("alias csgomp_stop \"-voicerecord; voice_loopback 0; voice_inputfromfile 0\"\n")
            # TODO: add a pref to set this bind key, and the continuous play key too
            f.write("bind ' +csgomp_play\n")
            f.write("alias csgomp_toggle_on \"csgomp_start; bind / "
                    "csgomp_toggle_off\"\n")
            f.write("alias csgomp_toggle_off \"csgomp_stop; bind / "
                    "csgomp_toggle_on\"\n")
            f.write("bind / csgomp_toggle_on\n")
            f.close()

            #TODO: use pyinotify/watchdog or similar to check a request file for
            #the audio track. Just poll every 3 secs if neither available

        # TODO: add a popup to tell user to "exec csgomp" in console
        #show_cfg_load_popup()

    def prefs_ok_cb(self, button):
        print("Saving settings...")
        pull_prefs()
        # TODO: Check ffmpeg, csgo and youtube-dl paths exist and are executable (and dir for csgo)
        save_prefs()
        prefswin.hide()

    def prefs_cancel_cb(self, button):
        print("Not saving settings")
        prefswin.hide()

    def prefs_close_cb(self, button):
        print("WM killed window")
        #prefswin.hide()
        #prefswin.destroy()

    def add_file_cb(self, button):
        print("Show filesel...")
        # don't fetch and destroy here, just use run/show and hide
        resp = fileswin.run()
        if resp == 1:
            print("OK")
            filename = fileswin.get_filename()
            print("Filename is " + filename)
            alias = builder.get_object("entry_filesel_alias").get_text()
            print("Alias is " + alias)
            #FIXME: ask for start pos, end pos/duration and alias, and autoplay
            file_start = builder.get_object("entry_filesel_start_time").get_text()
            file_end = builder.get_object("entry_filesel_end_time").get_text()

            # no duration set yet
            duration = -1

            if(not file_start and not file_end):
                print("encoding whole file")
                start_pos = 0;
                end_pos = 0;
                duration = 0
            else:
                if(file_start):
                    print("starting from " + file_start)
                    start_pos = parse_time(file_start)
                if(file_end):
                    print("stopping at " + file_end)
                    end_pos = parse_time(file_end)
                duration = end_pos - start_pos
                print("duration is " + str(duration))
                print("ffmpeg opt: -ss " + str(start_pos) + " -t " + str(duration))

            if duration < 0:
                print("Error: duration can't be less than 0")
                duration = 0

            keybinding = str(len(liststore))
            liststore.append([filename, str(start_pos) , str(duration), alias, keybinding, False])

            # debug: print what is in the list
            treeiter = liststore.get_iter_first()
            while treeiter != None:
                print(str(liststore[treeiter][0]))
                treeiter = liststore.iter_next(treeiter)

        elif resp == 2:
            print("CANCEL")

        fileswin.hide()

    def youtube_ok_cb(self, button):
        print("Add from youtube")
        # get url, start and end (if entered)
        yt_url = builder.get_object("entry_youtube_url").get_text()
        yt_start = builder.get_object("entry_youtube_start_time").get_text()
        yt_end = builder.get_object("entry_youtube_end_time").get_text()
        yt_alias = builder.get_object("entry_youtube_alias").get_text()

        # TODO: write parse_time function to check it really is a time
        # and convert to seconds from MM:SS.
        print("URL: " + yt_url + " start: " + yt_start + " end: " + yt_end)

        # no duration set yet
        duration = -1

        end_pos = 0
        start_pos = 0

        if(not yt_start and not yt_end):
            print("encoding whole file")
            start_pos = 0;
            end_pos = 0;
        else:
            if(yt_start):
                print("starting from " + yt_start)
                start_pos = parse_time(yt_start)
            if(yt_end):
                print("stopping at " + yt_end)
                end_pos = parse_time(yt_end)
            duration = end_pos - start_pos
            print("duration is " + str(duration))
            print("ffmpeg opt: -ss " + str(start_pos) + " -t " + str(duration))

        if duration < 0:
            print("Error: duration can't be less than 0")
            duration = 0

        # TODO: write to /tmp, make it work with cache_name somehow
        grab_youtube(yt_url, start_pos, duration, yt_alias)

        youtubewin.hide()

    def youtube_cancel_cb(self, button):
        print("Cancel youtube add")
        youtubewin.hide()

    def add_youtube_cb(self, button):
        if(youtube_dl_path):
            print("Show youtube dialog...")
            youtubewin.show()
        else:
            print("youtube-dl not found")
            builder.get_object("dialog_noyoutubedl").show()

    def filesel_open_clicked_cb(self, button):
        print("Open")
        fileswin.destroy()

    def filesel_cancel_clicked_cb(self, button):
        print("Cancel")
        fileswin.destroy()

    def noytdl_ok_cb(self, button):
        builder.get_object("dialog_noyoutubedl").hide()

# called when a file is selected from the list
# convert the file to wav for use in game
# TODO: add right click callback for changing alias and keybind
# TODO: when a file is added or keybind change highlight the "write csgo cfg"
# button so the user knows they need to click it
    def selection_changed_cb(self, selection):
        model, treeiter = selection.get_selected()
        global ffmpeg_path, csgo_directory, files_count, \
                youtube_dl_path
        if treeiter != None:
            # update voice_input.wav to selected file
            wav_file = csgo_directory + "/voice_input.wav"

            audio_len_flag = ""

            # TODO: check file still exists
            convertme = model[treeiter][0]
            start_pos = int(model[treeiter][1])
            duration = int(model[treeiter][2])


            # TODO: clear cache button

            # check for file in cache using convertme + start_pos + length as
            # name. eg jamesbond.mp3_3_10.wav for jamesbond.mp3 starting from 3
            # seconds in and playing for 10 secs.  jamesbond.mp3_0_0.wav for full
            # track.
            # TODO: remove the max_audio_length option and save a starttime and
            # duration with every filename
            cache_name, in_cache = check_cache(convertme, start_pos, duration)
            if in_cache:
                # use cached version
                print("WAV in cache, copying")
                if os.path.isfile(wav_file):
                    os.remove(wav_file)
                shutil.copy(cache_name, wav_file)
            else:
                # TODO: check first if this is a youtube link that needs
                # downloading.  should only happen if cache has been cleared
                print("Not cached, converting...")
                print("convertme: " + convertme + " start_pos: " +
                      str(start_pos) +
                      "duration:" + str(duration));
                if(start_pos == 0 and duration == 0):
                    # whole song
                    print("Encoding whole song...");
                    audio_len_flag = " "
                elif(start_pos > 0 and duration > 0):
                    # startpos and duration set
                    audio_len_flag = " -ss " + str(start_pos) + " -t " + str(duration)
                elif(start_pos > 0):
                    # just a start position
                    audio_len_flag = " -ss " + str(start_pos)
                elif(duration > 0):
                    # just a duration
                    audio_len_flag = " -t " + str(duration)

                # needs -flags +bitexact so ffmpeg doesnt add metadata
                # also seems to need -map_metadata -1
                ffmpeg_opts = " -vn -map_metadata -1 -acodec pcm_s16le -ar 22050 -ac 1 -f wav -flags +bitexact"
                # use -y option to force overwrite just incase
                ffmpeg_cmd = ffmpeg_path + " -loglevel panic -y -i '" +convertme + "' " + audio_len_flag + ffmpeg_opts + " '" + cache_name + "'"

                print("cmd: " + ffmpeg_cmd)

                #FIXME: why doesnt call work?
                #call([ffmpeg_path, ffmpeg_cmd])
                os.system(ffmpeg_cmd)

                # delete any existing file
                if os.path.isfile(wav_file):
                    os.remove(wav_file)
                shutil.copy(cache_name, wav_file)


    # called when clicking a list item (with any button)
    def list_item_click_cb(self, treeview, event):
        # check if this is a right click
        if event.button == 3:
            # get path
            global pthinfo
            pthinfo = treeview.get_path_at_pos(int(event.x), int(event.y))
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                # get the tree view model and print the filename at 
                # the path at pointer position
                model = treeview.get_model()
                print("Right click " + model[path][0])
                popup = builder.get_object("menu_popup")
                # XXX: save the pthinfo as a global so it can be used
                # by the callback functions.  I couldn't find another
                # way to get the data to the callbacks
                popup.popup(None, None, None, None, event.button, event.time)

    # context menu callbacks
    # use path from pthinfo to get the data to work on
    # and insert it into the dialog boxes.
    # dialog box save button updates the treeview data
    def popup_edit_cb(self, menuitem):
        print(pthinfo)
        if pthinfo is not None:
            path, col, cellx, celly = pthinfo
            model = treeview.get_model()
            print("Going to edit: " + model[path][0])

    def popup_remove_cb(self, menuitem):
        print(pthinfo)
        if pthinfo is not None:
            path, col, cellx, celly = pthinfo
            model = treeview.get_model()
            print("Going to remove: " + model[path][0])



# end: Handler

# check cache first
# use youtube-dl to get a file from youtube and save in /tmp
# 
def grab_youtube(url, start_pos, duration, alias):
    cache_name, in_cache = check_cache(url, start_pos, duration)
    wav_file = csgo_directory + "/voice_input.wav"

    if in_cache:
        # use cached version
        print("WAV in cache, copying")
        if os.path.isfile(wav_file):
            os.remove(wav_file)
        shutil.copy(cache_name, wav_file)
        # add it to the file list

        # FIXME: ask for alias, autoplay
        keybinding = str(len(liststore))
        liststore.append([url, str(start_pos), str(duration), alias, keybinding,
                         autoplay])
    else:
        print("Not cached, downloading and converting...")
        print("target name " + cache_name)

        # download to /tmp using youtube-dl
        # first get output filename
        youtube_dl_opts = "-o '/tmp/csgompyttmp.%(ext)s' '" + url + "' -f mp4 --get-filename"
        youtube_dl_cmd = youtube_dl_path + " " + youtube_dl_opts
        print("youtube-dl cmd: " + youtube_dl_cmd)
        yt_dl_filename = subprocess.check_output(youtube_dl_cmd,
                                                 shell=True).rstrip()
        print("Got filename:[" + yt_dl_filename + "]")
        # make sure it doesn't already exist
        if os.path.isfile(yt_dl_filename):
            os.remove(yt_dl_filename)

        # then actually download
        youtube_dl_opts = "-o '/tmp/csgompyttmp.%(ext)s' '" + url + "' -f mp4"
        youtube_dl_cmd = youtube_dl_path + " " + youtube_dl_opts
        print("youtube-dl cmd: " + youtube_dl_cmd)
        subprocess.call(youtube_dl_cmd, shell=True)

        if not os.path.isfile(yt_dl_filename):
            print("Downloaded file not found")

        # then convert to wav with ffmpeg with start_pos and duration
        ffmpeg_opts = " -vn -map_metadata -1 -acodec pcm_s16le -ar 22050 -ac 1 -f wav -flags +bitexact "

        if(start_pos == 0 and duration == 0):
            # whole song
            audio_len_flag = " "
        elif(start_pos > 0 and duration > 0):
            # startpos and duration set
            audio_len_flag = " -ss " + str(start_pos) + " -t " + str(duration)
        elif(start_pos > 0):
            # just a start position
            audio_len_flag = " -ss " + str(start_pos)
        elif(duration > 0):
            # just a duration
            audio_len_flag = " -t " + str(duration)

        # use -y option to force overwrite just incase
        ffmpeg_cmd = ffmpeg_path + " -y -i '" + yt_dl_filename + "' " + audio_len_flag + ffmpeg_opts + " '" + cache_name + "'"
        subprocess.call(ffmpeg_cmd, shell=True)

        # copy it to wav_file
        if os.path.isfile(wav_file):
            os.remove(wav_file)
        shutil.copy(cache_name, wav_file)

        # add it to the file list
        # FIXME: ask for alias, autoplay on keybind
        keybinding = str(len(liststore))
        liststore.append([url, str(start_pos), str(duration), alias, keybinding,
                         autoplay])

        # and delete the tmp file
        os.remove(yt_dl_filename)

# try to convert time format into seconds
# formats hh:mm:ss, mm:ss, ss
def parse_time(time_str):

    if time_str.count(':') == 2:
        print("hh:mm:ss")
        h, m, s = time_str.split(':')
        return (int(h) * 3600) + (int(m) * 60) + int(s)
    elif time_str.count(':') == 1:
        print("mm:ss")
        m, s = time_str.split(':')
        return (int(m) * 60) + int(s)
    elif time_str.count(':') == 0:
        print("ss")
        return int(time_str)
    else:
        print("Time format error")


# check for file in the cache, return the cache file name and
# true or false
def check_cache(convertme, start_time, audio_len):
    cache_name = ""
    in_cache = False

    # check cache directory exists, create it if not
    if not os.path.isdir(cache_directory):
        print("Creating " + cache_directory)
        os.mkdir(cache_directory)

    # create the filename
    # is this a youtube url?
    if convertme.startswith("http"):
        cache_name = cache_directory + "/" + convertme.replace("/","-") + "_" + str(start_time) + "_" + str(audio_len) + ".wav"
    else:
        cache_name = cache_directory + "/" + os.path.basename(convertme) + "_" + str(start_time) + "_" + str(audio_len) + ".wav"
    print("cache_name is " + cache_name)

    # check file exists
    in_cache = os.path.isfile(cache_name)

    return cache_name, in_cache

def push_prefs():
    # update prefs window with current values
    global ffmpeg_path, csgo_directory, files_count,\
            youtube_dl_path
    builder.get_object("entry_ffmpeg_path").set_text(ffmpeg_path)
    builder.get_object("entry_csgo_dir").set_text(csgo_directory)
    if(youtube_dl_path):
        builder.get_object("entry_youtubedl_path").set_text(youtube_dl_path)

def pull_prefs():
    # get values from prefs boxes into variables
    global ffmpeg_path, csgo_directory, files_count,\
            youtube_dl_path
    ffmpeg_path = builder.get_object("entry_ffmpeg_path").get_text()
    csgo_directory = builder.get_object("entry_csgo_dir").get_text()
    youtube_dl_path = builder.get_object("entry_youtubedl_path").get_text()

    print(ffmpeg_path)



def load_prefs():
    global ffmpeg_path, csgo_directory, files_count,\
    youtube_dl_path
    if os.path.isfile("config.ini") == False:
        print("No settings found")
        return

    # load prefs
    config = SafeConfigParser()
    config.read("config.ini")

    # ffmpeg_path
    ffmpeg_path = config.get("main", "ffmpeg_path")

    # csgo_directory
    csgo_directory = config.get("main", "csgo_directory")

    # youtube-dl
    if config.has_option("main", "youtube_dl_path"):
        youtube_dl_path = config.get("main", "youtube_dl_path")

    # files_count
    files_count = config.getint("main", "files_count")

    # window size
    if config.has_option("main", "window_width"):
        w = config.getint("main", "window_width")
        h = config.getint("main", "window_height")
        mainwin.resize(w, h)

    # load files section
    i = 0
    while i < files_count:
        filename = config.get("files", "file"+str(i))
        start = config.get("files", "start"+str(i))
        dur = config.get("files", "dur"+str(i))
        alias = config.get("files", "alias"+str(i))
        keybinding = config.get("files", "keybinding"+str(i))
        autoplay = config.getboolean("files", "autoplay"+str(i))
        print("Found " + filename)
        keybinding = str(len(liststore))
        liststore.append([filename, start, dur, alias, keybinding, autoplay])
        i+=1

def save_prefs():
    # save prefs
    global ffmpeg_path, csgo_directory, files_count, \
            youtube_dl_path
    print("Saving...")
    config = SafeConfigParser()
    config.read("config.ini")

    if config.has_section("main") == False:
        config.add_section("main")

    # ffmpeg_path
    config.set("main", "ffmpeg_path", ffmpeg_path)
    print(ffmpeg_path)

    # csgo_directory
    config.set("main", "csgo_directory", csgo_directory)
    print(csgo_directory)

    # youtube-dl
    if(youtube_dl_path):
        config.set("main", "youtube_dl_path", youtube_dl_path)
        print(youtube_dl_path)

    # window size
    (w, h) = mainwin.get_size()
    print("w: " + str(w) + " h: " + str(h))
    config.set("main", "window_width", str(w))
    config.set("main", "window_height", str(h))


    # save files section
    if config.has_section("files") == False:
        config.add_section("files")

    treeiter = liststore.get_iter_first()
    files_count = 0
    while treeiter != None:
        filename = str(liststore[treeiter][0])
        config.set("files", "file"+str(files_count), filename)
        config.set("files", "start"+str(files_count),
                   str(liststore[treeiter][1]))
        config.set("files", "dur"+str(files_count),
                   str(liststore[treeiter][2]))
        config.set("files", "alias"+str(files_count),
                   str(liststore[treeiter][3]))
        config.set("files", "keybinding"+str(files_count),
                   str(liststore[treeiter][4]))
        config.set("files", "autoplay"+str(files_count),
                   str(liststore[treeiter][5]))
        treeiter = liststore.iter_next(treeiter)
        files_count+=1

    # files_count
    config.set("main", "files_count", str(files_count))
    print(str(files_count))


    # TODO: save to ~/.config/csgomp.ini
    with open("config.ini", "w") as f:
        config.write(f)

# function to find executables, taken from
# http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
def find_exe(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return(program)
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return(exe_file)
    return None


# Main
# load the glade file
builder = Gtk.Builder()
builder.add_from_file("MainWindow.glade")
builder.connect_signals(Handler())

# and fetch the windows
mainwin = builder.get_object("window1")
mainwin.set_icon_from_file("icon.png")
mainwin.show_all()

fileswin = builder.get_object("filechooserdialog1")
prefswin = builder.get_object("prefs")
youtubewin = builder.get_object("dialog_add_youtube")

# enable hotkey watcher
disp = Display()
# root = disp.screen().root
ctx = disp.record_create_context(0,
                                 [record.AllClients],
                                 [{
                                     'core_requests': (0, 0),
                                     'core_replies': (0, 0),
                                     'ext_requests': (0, 0, 0, 0),
                                     'ext_replies': (0, 0, 0, 0),
                                     'delivered_events': (0, 0),
                                     'device_events': (X.KeyPress, X.KeyPress),
                                     'errors': (0, 0),
                                     'client_started': False,
                                     'client_died': False,
                                 }])
print("hi1")
thread.start_new_thread(disp.record_enable_context, (ctx, track_selector))
print("hi2")
# disp.record_free_context(ctx)


# TODO: add a keybinding column too
# create a liststore for the files list
liststore = Gtk.ListStore(str, str, str, str, str, bool)

treeview = builder.get_object("treeview1")
treeview.set_model(liststore)
# and put a heading
treeview.append_column(Gtk.TreeViewColumn("Filename", Gtk.CellRendererText(), text=0))
treeview.append_column(Gtk.TreeViewColumn("Start", Gtk.CellRendererText(), text=1))
treeview.append_column(Gtk.TreeViewColumn("Duration", Gtk.CellRendererText(), text=2))
treeview.append_column(Gtk.TreeViewColumn("Alias", Gtk.CellRendererText(), text=3))
treeview.append_column(Gtk.TreeViewColumn("Key", Gtk.CellRendererText(), text=4))
treeview.append_column(Gtk.TreeViewColumn("Autoplay", Gtk.CellRendererText(), text=5))

# set some default values
ffmpeg_path = find_exe("ffmpeg")
csgo_directory = os.path.expanduser("~/.local/share/Steam/SteamApps/common/Counter-Strike Global Offensive/")
# TODO: try to check csgo directory is correct
files_count = 0
youtube_dl_path = find_exe("youtube-dl")
cache_directory = os.path.expanduser("~/.cache/csgomp")
keybinding = None
autoplay = False

# load prefs
load_prefs()

Gtk.main()


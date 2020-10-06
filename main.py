
# coding=utf-8

import math
import json
from datetime import datetime
import time

import kivy
from kivy.app import App
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.lang import Builder
from kivy.network.urlrequest import UrlRequest
from kivy.properties import (BooleanProperty, NumericProperty, ObjectProperty,
                             StringProperty)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.dropdown import DropDown
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line

kivy.require('1.11.1')


ip = '192.168.99.123'

CMD_ROOM_SET_PGM = 1
CMD_WRITE_EEPROM = 2
CMD_TIME_SET = 3
CMD_TEMPERATURE_SET = 4
CMD_RESET = 5
CMD_W_PGM_SET_D_PGM =  6
CMD_D_PGM_SET_T_PGM = 7
CMD_SLOT_SET_UPPER_BOUND = 8
CMD_CLEAR_EEPROM = 9
CMD_SET_RISE_TEMP_TIME_S = 10
CMD_SET_RISE_DELTA = 11
CMD_SET_BLOCKED_TIME_S = 12
CMD_SET_HYSTERESIS = 13
CMD_UNBLOCK = 14


# Error codes
#define ERR_NO 0
#define ERR_WRONG_COMMAND 1
#define ERR_WRONG_ROOM 2
#define ERR_WRONG_PROGRAM 3
#define ERR_WRONG_PARM 4 // Generic parameter error

# Example response of c=s or /st
ST_RESULT = {"P":0,"u":1515687267,"s":4,"b":0,"c":45.89,"h":50.78,"E":0,"R":[{"t":15.50,"T":5.0,"p":6,"d":5,"s":"C"},{"t":15.37,"T":5.0,"p":0,"d":0,"s":"C"},{"t":15.25,"T":5.0,"p":0,"d":0,"s":"C"},{"t":19.75,"T":19.0,"p":5,"d":4,"s":"C"},{"t":16.6,"T":5.0,"p":0,"d":0,"s":"C"}]}
# P = pump status 0/1
# u = unix time
# s = current slot
# h = hot temp
# c = cold temp
# b = unlock time
# E = error code
# Print programs:
# Print rooms:
# R = rooms array []
#   Room data:
#   t = real temp
#   T = desired temp
#   p = weekly program
#   d = daily program
#   s = status C/V/O/B (closed, opening, open, blocked)

# Example response for programs calls /pr
PR_RESULT = {"T":[5.0,15.0,16.50,19.0],"r":2.0,"h":0.50,"t":490,"b":3600,"s":[3.74,4.3,7.20,8.6,10.22,12.0,13.20],"w":[[0,0,0],[1,1,1],[2,2,2],[3,3,3],[4,7,7],[4,4,7],[5,7,7],[5,5,7],[6,7,7],[6,6,7]],"d":[[255,0,0,0],[0,255,0,0],[0,0,255,0],[0,0,0,255],[48,129,0,78],[60,128,1,66],[60,128,1,66],[0,128,0,127]]}
# T = array of temperatures for T0-T3
# r = raise temp delta
# h = histeresys
# t = rise temp time (seconds)
# b = blocked time (seconds)
# s = slot * .6 (divide by .60 to get the current hour), initial 00 and final 24 are not included
# w = weekly program number [[monday-friday, saturday, sunday], ...]
# d = daily program scheme for the 4 temp levels T0-T3

# Calls:
# /st -> status
# /pr -> programs
# /db -> free memory
# /?c=<command>&v=<value>&w=<other_value>
# Commands: see commands above

FAKE_ENDPOINT=True

ROOM_STATUS = {
  'O': 'Riscaldamento in corso',
  'V': 'Apertura valvola',
  'B': 'Blocco',
  'C': 'Nessuna richiesta di calore'
}

PROGRAM_NAMES = [
    'Sempre T0 (antigelo)',
    'Sempre T1',
    'Sempre T2',
    'Sempre T3',
    'Risveglio, cena e sera',
    'Risveglio, pasti e sera',
    'Risveglio, pasti, pomeriggio e sera',
    'Tutto il giorno'
]

# Weekly
WEEKLY_ROOM_PROGRAM_NAMES = [
    PROGRAM_NAMES[0],
    PROGRAM_NAMES[1],
    PROGRAM_NAMES[2],
    PROGRAM_NAMES[3],
    'lun-ven: ' +  PROGRAM_NAMES[4] + ' sab-dom: ' + PROGRAM_NAMES[7],
    'lun-sab: ' +  PROGRAM_NAMES[4] + ' dom: ' + PROGRAM_NAMES[7],

    'lun-ven: ' +  PROGRAM_NAMES[5] + ' sab-dom: ' + PROGRAM_NAMES[7],
    'lun-sab: ' +  PROGRAM_NAMES[5] + ' dom: ' + PROGRAM_NAMES[7],

    'lun-ven: ' +  PROGRAM_NAMES[6] + ' sab-dom: ' + PROGRAM_NAMES[7],
    'lun-sab: ' +  PROGRAM_NAMES[6] + ' dom: ' + PROGRAM_NAMES[7],
];

ROOM_NAMES = [
  'Aurora',
  'Ospiti',
  'Sala',
  'Leo',
  'Bagno'
]

cmd_url = "http://%s/?c=%%s" % ip
cmd_url_path = "http://%s/%%s" % ip

class MenuScreen(Screen):
    pump_open = ObjectProperty(None)
    hot_temp = ObjectProperty(None)
    cold_temp = ObjectProperty(None)

class RoomScreen(Screen):
    room_buttons = ObjectProperty(None)

class RoomConfigScreen(Screen):
    room_status = ObjectProperty(None)

class RoomChangeProgramScreen(Screen):
    room_programs = ObjectProperty(None)

class WeeklyProgramsScreen(Screen):
    weekly_programs_status = ObjectProperty(None)

class WeeklyProgramDetailsScreen(Screen):
    #weekly_program_details_buttons = ObjectProperty(None)
    weekly_program_details_name = ObjectProperty(None)

class TimeSlotsScreen(Screen):
    time_slots_buttons = ObjectProperty(None)

class SettingsScreen(Screen):
    pass

class TimeSlotSettingsScreen(Screen):
    slider = ObjectProperty(None)
    time_slots_settings_label = ObjectProperty(None)

class BgColorLabel(Label):

    def __init__(self, **kwargs):
        self.bgcolor = kwargs.get('bgcolor', (1, 1, 1, 1))
        kwargs.pop('bgcolor')
        super().__init__(**kwargs)

    def on_size(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bgcolor)
            Rectangle(pos=self.pos, size=self.size)
            Color((1, 1, 1, 1))
            Line(width=1, rectangle=(self.x, self.y, self.width, self.height))


class RiscaldamentoApp(App):

    room_buttons = []
    program_buttons = [] # for rooms to set a new program
    time_slots_buttons = [] # for time slots
    weekly_program_buttons = [] # for settings
    weekly_program_details_buttons = [] # for settings
    error_code = None
    current_slot = None
    rooms_status = None
    current_room = 0

    # Programs
    programs_status = None
    weekly_programs_status = None
    daily_programs_status = None
    temperature_slots_status = None
    current_weekly_program = 0
    current_daily_program = 0
    current_time_slot = 0

    error_popup = None
    error_popup_open = False
    error_popup_content = None

    def start(self, arg):
        # Init buttons

        # Rooms
        room_buttons = self.root.get_screen('room_screen').room_buttons
        for i in range(5):
            btn = Button(text=ROOM_NAMES[i], font_size=15, markup=True, halign='left', padding_x=10, valign='middle')
            self.room_buttons.append( btn )
            room_buttons.add_widget( btn )
            btn.text_size = btn.size
            btn.index = i
            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=self.change_room)

        # Weekly programs
        weekly_programs_buttons = self.root.get_screen('weekly_programs_screen').weekly_programs_buttons
        for i in range(10):
            btn = Button(text=WEEKLY_ROOM_PROGRAM_NAMES[i], font_size=30, markup=True, halign='left', padding_x=10, valign='middle')
            self.weekly_program_buttons.append( btn )
            weekly_programs_buttons.add_widget( btn )
            btn.text_size = btn.size
            btn.index = i
            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=self.change_weekly_program_screen)


        # Room program select
        room_program_select = self.root.get_screen('room_change_program_screen').room_program_select
        for i in range(len(WEEKLY_ROOM_PROGRAM_NAMES)):
            btn = Button(text="%s: %s" % (i+1, WEEKLY_ROOM_PROGRAM_NAMES[i]), font_size=30, markup=True, halign='left', padding_x=10, valign='middle')
            room_program_select.add_widget(btn)
            btn.index = i
            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=self.change_program)
            self.program_buttons.append( btn )

        # Time slots
        time_slots_buttons = self.root.get_screen('time_slots_screen').time_slots_buttons
        for slot in range(8):
            btn = Button(text="Slot %s" % slot, font_size=30, markup=True, halign='left', padding_x=10, valign='middle')
            time_slots_buttons.add_widget(btn)
            btn.index = slot
            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=self.edit_time_slot)
            self.time_slots_buttons.append( btn )

        self.check_status()
        self.check_programs()
        Clock.schedule_interval(self.check_status, 10)
        Clock.schedule_interval(self.check_programs, 10)

    def error(self, message):
        if self.error_popup is None:
            content = BoxLayout(orientation="vertical")
            self.error_popup_content = Label(text=message, font_size=40,)
            content.add_widget(self.error_popup_content)
            btn = Button(text='Chiudi', font_size=40)
            content.add_widget(btn)
            self.error_popup = Popup(content=content, title='Errore', auto_dismiss=True)
            self.error_popup.content = content
            # bind the on_press event of the button to the dismiss function
            btn.bind(on_press=self.error_popup.dismiss)
            def toggle(arg):
                self.error_popup_open = not self.error_popup_open
            self.error_popup.bind(on_open=toggle)
            self.error_popup.bind(on_dismiss=toggle)

        self.error_popup_content.text = message
        # open the popup
        if not self.error_popup_open:
            self.error_popup.open()


    def update_room_screen(self):
        index = self.current_room

        if self.rooms_status is None:
            self.error("Impossibile connettersi\ncontrollare la connessione!")
            return

        room_config_screen = self.root.get_screen('room_config_screen')
        room_data = self.rooms_status[index]
        room_config_screen.room_status.room_program.text = "%s: %s" % (room_data['p'] + 1, WEEKLY_ROOM_PROGRAM_NAMES[room_data['p']])
        room_config_screen.room_status.room_name.text = ROOM_NAMES[index]
        room_config_screen.room_status.room_temps.text = "%s °C %s (voluta: %s)\n[size=30]%s[/size]" % (ROOM_NAMES[index], room_data['t'], room_data['T'], ROOM_STATUS[room_data['s']])

    def update_programs_screen(self):

        weekly_program_index = self.current_weekly_program
        daily_program_index = self.current_daily_program

        if self.programs_status is None:
            self.error("Programmi: impossibile connettersi\ncontrollare la connessione!")
            return

    def update_time_slots_screen(self):

        if self.programs_status is None:
            self.error("Impossibile connettersi\ncontrollare la connessione!")
            return

        slot_index = 0
        for slot in self.get_slots_representation():
            self.time_slots_buttons[slot_index].text = slot
            slot_index += 1

        print("update_time_slots_screen")


    def edit_time_slot(self, arg):
        self.current_time_slot = arg.index
        self.root.transition.direction = 'left'
        self.root.current = 'time_slots_settings_screen'

    def represent_slot(self, val):
        """Takes a 0-24 decimal hour representation and returns HH:MM

        3.90 -> 06:30

        :param val: [description]
        :type val: [type]
        :return: [description]
        :rtype: [type]
        """
        val = val / 0.6
        return "%02d:%02d" % (math.floor(val), int(val * 100 % 100 * .6))

    def change_slot_value(self):
        screen = self.root.get_screen('time_slots_settings_screen')
        print(self.current_time_slot, screen.slider.value)

    def get_slots_representation(self):
        slots = []
        base = '00'
        for i in range(7):
            val = self.temperature_slots_status[i]
            slot_repr = self.represent_slot(val)
            slots.append("%s - %s" % (base, slot_repr))
            base = slot_repr

        slots.append("%s - 24.00" % base)
        return slots

    def get_program_representation(self, weekly_program_index, day_index):
        program_repr = []
        pgm = self.weekly_programs_status[weekly_program_index][day_index]
        daily = self.daily_programs_status[pgm]
        bit = 7
        for _slot in self.get_slots_representation():
            t = 0
            for d in daily:
                if d & pow(2, bit):
                    #print("Found Daily T{1} for slot {2} ({0}): {0:b}".format(d, t, slot))
                    program_repr.append("T%s" % t)
                t+=1
            bit-=1
        return program_repr

    def get_t_color(self, t):
        colors = {
            'T0': (0, 0, 1, 1), # blue
            'T1': (0.5, 0.5, 0, 1), # yellow
            'T2': (1, 0.5, 0, 1), # orange
            'T3': (1, 0, 0, 1), # red
        }
        return colors[t]


    def update_program_details_screen(self):

        if self.programs_status is None:
            self.error("Programmi: impossibile connettersi\ncontrollare la connessione!")
            return

        weekly_program_index = self.current_weekly_program
        self.weekly_program_details_name = WEEKLY_ROOM_PROGRAM_NAMES[weekly_program_index]
        screen = self.root.get_screen('weekly_program_details_screen')
        screen.weekly_program_details_name.text = self.weekly_program_details_name

        # Cleanup
        weekly_program_details_buttons = screen.weekly_program_details_buttons
        for w in self.weekly_program_details_buttons:
            weekly_program_details_buttons.remove_widget(w)

        # Header
        layout = BoxLayout(orientation="horizontal")
        for slot in self.get_slots_representation():
            lbl = BgColorLabel(text=slot, bgcolor=(0.3, 0.3, 0.3, 1))
            layout.add_widget(lbl)

        weekly_program_details_buttons.add_widget( layout )
        self.weekly_program_details_buttons.append( layout )

        sections = {
            'Lunedì - Venerdì': (0, 1, 0, 1),
            'Sabato': (1, 1, 0, 1),
            'Domenica': (1, 0, 0, 1),
        }

        section_index = 0
        for section, color in sections.items():

            lbl = Label(text=section, color=color, font_size=20, markup=True, halign='left', padding_x=10, valign='middle')
            self.weekly_program_details_buttons.append( lbl)
            weekly_program_details_buttons.add_widget( lbl )

            layout = BoxLayout(orientation="horizontal")

            for slot in self.get_program_representation(weekly_program_index, section_index):
                lbl = BgColorLabel(text=slot, bgcolor=self.get_t_color(slot))
                layout.add_widget(lbl)

            weekly_program_details_buttons.add_widget( layout )
            self.weekly_program_details_buttons.append( layout )

            section_index += 1


    def update_time_slots_settings_screen(self):

        screen = self.root.get_screen('time_slots_settings_screen')
        screen.time_slots_settings_label = "Fascia oraria n° %s" % self.current_time_slot
        screen.slider.min = 0 if self.current_time_slot == 0 else self.temperature_slots_status[self.current_time_slot-1]
        screen.slider.max = 14.40 if self.current_time_slot == 6 else self.temperature_slots_status[self.current_time_slot+1]
        screen.slider.value = self.temperature_slots_status[self.current_time_slot]
        print("Update slots settings")


    def update_status(self, req, response):
        if not req.error:
            self.rooms_status = response['R']
            menu_screen = self.root.get_screen('menu_screen')
            menu_screen.pump_open.text = "Riscaldamento " + ("in corso" if response['P'] else "spento")
            menu_screen.hot_temp.text = "T in %s °C" % response['h']
            menu_screen.cold_temp.text = "T out %s °C" % response['c']
            menu_screen.time.text = datetime.fromtimestamp(int(response['u']) + time.timezone).strftime('%Y-%m-%d %H:%M')
            self.error_code = response['E']
            self.current_slot = response['s']
            for i in range(5):
                room_data = response['R'][i]
                self.room_buttons[i].text = "%s °C %s (voluta: %s)\n[size=30]%s[/size]" % (ROOM_NAMES[i], room_data['t'], room_data['T'], ROOM_STATUS[room_data['s']])

            self.update_room_screen()

    def update_programs(self, req, response):
        if not req.error:
            self.programs_status = response
            self.weekly_programs_status = response['w']
            self.daily_programs_status = response['d']
            self.temperature_slots_status = response['s']
            self.update_programs_screen()


    def ws_response(self, req, response):
        self.update_status(req, response)
        self.root.transition.direction = 'left'
        self.root.current = 'room_config_screen'


    def ws_call(self, *parms):
        """Call the web service"""
        url = str(parms[0])
        try:
            url += '&p=%s' % parms[1]
        except:
            pass
        try:
            url += '&v=%s' % parms[2]
        except:
            pass
        try:
            url += '&w=%s' % parms[3]
        except:
            pass
        print(url)
        return UrlRequest(cmd_url % url, self.ws_response)

    def clock_sync(self):
        # 0 = hh, 1 = mm, 2 = ss, 3 = Y, 4 = m, 5 = d
        self.ws_call(CMD_TIME_SET, 0, datetime.now().hour).wait()
        self.ws_call(CMD_TIME_SET, 1, datetime.now().minute).wait()
        self.ws_call(CMD_TIME_SET, 3, datetime.now().year).wait()
        self.ws_call(CMD_TIME_SET, 4, datetime.now().month).wait()
        self.ws_call(CMD_TIME_SET, 5, datetime.now().day).wait()

    def store_eeprom(self, arg):
        req = self.ws_call(CMD_WRITE_EEPROM)

    def change_program(self, arg):
        """Change program for a room"""
        program = arg.index
        room = self.current_room
        req = self.ws_call(CMD_ROOM_SET_PGM, room, program)
        Clock.schedule_once(self.store_eeprom, 2)


    def check_status(self, *arg):
        if FAKE_ENDPOINT:
            return self.update_status(type('',(object,),{"error": False}), ST_RESULT)
        req = UrlRequest(cmd_url % 's', self.update_status)

    def check_programs(self, *arg):
        if FAKE_ENDPOINT:
            return self.update_programs(type('',(object,),{"error": False}), PR_RESULT)
        req = UrlRequest(cmd_url_path % 'pr', self.update_programs)


    def change_room(self, button=None):
        """Show room page"""
        try:
            self.current_room = button.index
        except:
            pass
        self.root.transition.direction = 'left'
        self.root.current = 'room_config_screen'

    def change_weekly_program_screen(self, button=None):
        """Show weekly program settings page"""
        try:
            self.current_weekly_program = button.index
        except:
            pass
        self.root.transition.direction = 'left'
        self.root.current = 'weekly_program_details_screen'


    def build(self):
        Clock.schedule_once(self.start, 0.5)
        return Builder.load_file('riscaldamento.kv')


if __name__ == '__main__':
    RiscaldamentoApp().run()

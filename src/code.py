from math import *

import board
import displayio
import framebufferio
import sharpdisplay
import terminalio

from keypad import KeyMatrix
from adafruit_display_text.label import Label
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS

try:
	import usb_hid
except ImportError:
	usb_hid = None

# Initialize the display, cleaning up after a display from the previous
# run if necessary
displayio.release_displays()
framebuffer = sharpdisplay.SharpMemoryFramebuffer(board.SPI(), board.D13, 400, 240)
display = framebufferio.FramebufferDisplay(framebuffer, auto_refresh=False)

# Set board row/col pins
col_pins = (board.D12, board.D11, board.D10, board.D9)
row_pins = (board.A4, board.A3, board.A2, board.A1, board.A0)

class LayerSelect:
	def __init__(self, idx=1, next_layer=None):
		self.idx = idx
		self.next_layer = next_layer or self

# Special keycodes
LL0 = LayerSelect(0)
LL1 = LayerSelect(1)
LS1 = LayerSelect(1, LL0)

BSP = '\xF0'
CLR = '\xF1'
ANS = '\xF2'
SIN = '\xF3'
COS = '\xF4'

# Layer config
layers = [
	[
		LS1, '/', '*', '-',
		'1', '2', '3', '',
		'4', '5', '6', '+',
		'7', '8', '9', '',
		BSP, '0', '.', '='
	],
	[
		LL1, '(', ')', '-',
		ANS, SIN, COS, '',
		'4', '5', '6', '+',
		'7', '8', '9', '',
		CLR, '0', '^', 'p'
	],
]

class MatrixKeypad:
	def __init__(self):
		self.matrix = KeyMatrix(
			row_pins=row_pins,
			column_pins=col_pins,
			interval=0.005
		)
		self.layers = layers
		self.layer = LL0
		self.pending = []

	def getch(self):
		if not self.pending:
			event = self.matrix.events.get()
			if event and event.pressed:
				op = self.layers[self.layer.idx][event.key_number]
				if isinstance(op, LayerSelect):	
					self.layer = op
				else:
					self.pending.extend(op)
					self.layer = self.layer.next_layer
		else:
			pend = self.pending.pop(0)
			return pend

		return None

class Calc:
	def __init__(self):
		# incoming keypad
		self.keypad = MatrixKeypad()

		# outgoing keypresses
		self.keyboard = None
		self.keyboard_layout = None

		# history
		self.history = []

		g = displayio.Group()

		self.labels = labels = []
		labels.append(Label(terminalio.FONT, scale=2, color=0))
		labels.append(Label(terminalio.FONT, scale=3, color=0))
		labels.append(Label(terminalio.FONT, scale=3, color=0))
		labels.append(Label(terminalio.FONT, scale=3, color=0))
		labels.append(Label(terminalio.FONT, scale=3, color=0))
		labels.append(Label(terminalio.FONT, scale=3, color=0))

		for li in labels:
			g.append(li)

		bitmap = displayio.Bitmap((display.width + 126)//127, (display.height + 126)//127, 1)
		palette = displayio.Palette(1)
		palette[0] = 0xffffff

		tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
		bg = displayio.Group(scale=127)
		bg.append(tile_grid)

		g.insert(0, bg)

		display.show(g)

	def getch(self):
		while True:
			c = self.keypad.getch()
			if c is not None:
				return c

	# 0 indexed
	def get_history(self, i):
		ret = ""
		length = len(self.history)
		if i+1 <= length:
			ret = self.history[-1-i]
		return ret
	
	def add_history(self, exp):
		self.history.append(exp)

	def setline(self, i, text):
		li = self.labels[i]
		text = text[:31] or " "
		if text == li.text:
			return
		li.text = text
		li.anchor_point = (0,0)
		li.anchored_position = (1, max(1, 41 * i - 7) + 6)

	def refresh(self):
		pass

	def paste(self, text):
		if self.keyboard is None:
			if usb_hid:
				self.keyboard = Keyboard(usb_hid.devices)
				self.keyboard_layout = KeyboardLayoutUS(self.keyboard)
			else:
				return

		if self.keyboard_layout is None:
			raise ValueError("USB HID not available")
		text = str(text)
		self.keyboard_layout.write(text)
		# raise RuntimeError("Pasted")

	def start_redraw(self):
		display.auto_refresh = False

	def end_redraw(self):
		display.auto_refresh = True

	def end(self):
		pass

calc = Calc()

def parse():
	exp = ""
	calc.start_redraw()
	calc.setline(5, "> " + exp + "_")
	calc.refresh()
	calc.end_redraw()
	
	while True:
		c = calc.getch()
		if c == "=":
			calc.add_history(str(eval(exp, globals())))
			exp = ""
		elif c in "0123456789.+-/*^()":
			c = str(c)
			if exp == "" and c in "+-/*^":
				exp += calc.get_history(0)
			exp += c
		elif c == "\xF0":
			exp = exp[:-1]
		elif c == "p":
			calc.paste(calc.get_history(0))
		elif c == "\xF1":
			exp = ""
		elif c == "\xF2":
			exp += calc.get_history(0)

		exp = str(exp)

		calc.start_redraw()
		calc.setline(5, "> " + exp + "_")
		
		for i in range(4):
			calc.setline(4 - i, calc.get_history(i))
		
		calc.end_redraw()

parse()
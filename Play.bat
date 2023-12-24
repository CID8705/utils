# 2>NUL || @GOTO :BATCH
'''
:BATCH
@ECHO OFF
SETLOCAL
SET PATH=^
%USERPROFILE%\Documents\Program Files\Anaconda3\envs\python38;^
%USERPROFILE%\Documents\Program Files\Anaconda3\envs\python38\Library\bin;^
%USERPROFILE%\Documents\Program Files\Anaconda3\envs\python38\Scripts;^
%PATH%
SET PYTHONDONTWRITEBYTECODE=1
SET PYTHONPATH=%USERPROFILE%\Documents\Program Files\Anaconda3\envs\python38\Lib
CALL :FUNCTION "numpy"
CALL :FUNCTION "py7zr"
CALL :FUNCTION "pysimplegui"
CALL :FUNCTION "requests"
CALL :FUNCTION "sounddevice"
CALL :FUNCTION "soundfile"
python "%~0" %*
ENDLOCAL
EXIT /B

:FUNCTION
SET /A FLAG=0
FOR /F "usebackq delims==" %%a IN (`pip freeze`) DO (
	IF "%%a" == "%~1" (
		SET /A FLAG=1
	)
)
IF %FLAG% == 0 (
	pip install "%~1"
)
EXIT /B
'''

import base64
import py7zr
import PySimpleGUI as sg
import random
import requests
import soundfile
import sounddevice
import threading
from io import BytesIO

class PlayClass:
	def __init__(self, window, bar_max):
		self._bar_max = bar_max
		self._is_mute = False
		self._is_playing = False
		self._is_repeat = False
		self._datas = None
		self._indexes = None
		self._index = -1
		self._stream = None
		self._window = window

	def _getDatabase(self, urls):
		headers = { "Accept-Encoding": "identity" }
		total_size = sum([int(requests.head(url, headers=headers).headers["Content-Length"]) for url in urls])
		texts = []
		size = 0
		for url in urls:
			data = BytesIO()
			with requests.get(url, stream=True) as res:
				for chunk in res.iter_content(chunk_size=1024*1024):
					data.write(chunk)
					size += len(chunk)
					self._window["Progress"].update(self._bar_max * size / total_size)
			texts.append(data.getvalue().decode())
		return texts

	def _updateIndex(self):
		self._current_frame = 0
		if not self._is_repeat:
			self._index += 1
			if self._indexes == None or self._index >= len(self._datas):
				self._indexes = [i for i in range(len(self._datas))]
				random.shuffle(self._indexes)
				self._index = 0
			self._window["Slider"].Update(range=(0, len(self.getCurrentData()) / self._getCurrentSamplerate()))
		self._window["Slider"].update(self._current_frame / self._getCurrentSamplerate())

	def load(self, password):
		database_num = 2
		self._window["Load"].Update(disabled=True)
		urls = ["https://raw.githubusercontent.com/CID8705/utils/main/database.{:0>3}.txt".format(i) for i in range(1, database_num + 1)]
		try:
			stream = [base64.b64decode(text) for text in self._getDatabase(urls)]
			with py7zr.SevenZipFile(BytesIO(b"".join(stream)), mode="r", password=password) as archive:
				raw_data = archive.readall()
		finally:
			self._window["Load"].Update(disabled=False)
		self.stopSound()
		self._datas = [(key, *soundfile.read(value)) for key, value in raw_data.items()]
		self._updateIndex()
		self._window["Slider"].Update(disabled=False)
		self._window["Play / Pause"].Update(disabled=False)
		self._window["Next"].Update(disabled=False)
		self._window["Loop / Repeat"].Update(disabled=False)
		self._window["Mute"].Update(disabled=False)

	def getCurrentData(self):
		return self._datas[self._indexes[self._index]][1]

	def _getCurrentSamplerate(self):
		return self._datas[self._indexes[self._index]][2]

	def setCurrentTime(self, current_time):
		self._current_frame = int(current_time * self._getCurrentSamplerate())

	def _callback_closure(self, outdata, frams, time, status):
		data = self.getCurrentData()
		chunk_size = min(len(data) - self._current_frame, frams)
		outdata[0:chunk_size] = data[self._current_frame:self._current_frame + chunk_size] * 0.03 * int(not self._is_mute)
		self._current_frame += chunk_size
		self._window["Slider"].update(self._current_frame / self._getCurrentSamplerate())
		if chunk_size < frams:
			raise sounddevice.CallbackStop()

	def _callback_finished(self):
		if self._is_playing:
			self.nextSound()

	def _pauseSound(self):
		self._is_playing = False
		self._stream.stop()

	def controlSound(self):
		if self._is_playing:
			self._pauseSound()
		else:
			if self._stream == None:
				self._stream = sounddevice.OutputStream(
					samplerate=self._getCurrentSamplerate(),
					blocksize=1024,
					channels=self.getCurrentData().shape[-1],
					callback=self._callback_closure,
					finished_callback=self._callback_finished
				)
			self._is_playing = True
			self._stream.start()

	def stopSound(self):
		if self._is_playing:
			self._pauseSound()
		if not self._stream == None:
			self._stream.close()
			self._stream = None

	def nextSound(self):
		prev = self._is_playing
		self.stopSound()
		self._updateIndex()
		if prev:
			self.controlSound()

	def repeatSound(self):
		if self._is_repeat:
			self._is_repeat = False
		else:
			self._is_repeat = True

	def muteSound(self):
		if self._is_mute:
			self._is_mute = False
		else:
			self._is_mute = True

def main():
	bar_max = 10000
	layout = [
		[sg.Text("Password"), sg.InputText("", key="Password")],
		[sg.Button("Load", key="Load", disabled=False), sg.ProgressBar(bar_max, orientation="h", size=(31, 20), key="Progress")],
		[sg.Slider(range=(0, 0), orientation="h", size=(44, 20), default_value=0, resolution=1, enable_events=True, key="Slider", disabled=True)],
		[sg.Button("Play / Pause", key="Play / Pause", disabled=True), sg.Button("Next", key="Next", disabled=True), sg.Button("Loop / Repeat", key="Loop / Repeat", disabled=True), sg.Button("Mute", key="Mute", disabled=True)]
	]
	window = sg.Window("PySimpleGUI", layout)
	play = PlayClass(window, bar_max)
	load_thread = None
	while True:
		event, values = window.read()
		if event == sg.WIN_CLOSED:
			break
		if event == "Load":
			if load_thread == None or not load_thread.is_alive():
				load_thread = threading.Thread(target=play.load, args=(values["Password"],), daemon=True)
				load_thread.start()
		if event == "Slider":
			play.setCurrentTime(values["Slider"])
		if event == "Play / Pause":
			play.controlSound()
		if event == "Next":
			play.nextSound()
		if event == "Loop / Repeat":
			play.repeatSound()
		if event == "Mute":
			play.muteSound()
	play.stopSound()
	if not load_thread == None:
		load_thread.join()
	window.close()

if __name__ == "__main__":
	main()

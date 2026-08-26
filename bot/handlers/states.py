"""Finite-state-machine states used across handlers."""

from aiogram.fsm.state import State, StatesGroup


class CutStates(StatesGroup):
    """Steps of the audio-cutting conversation."""

    waiting_for_times = State()   # waiting for "start end" timecodes


class PlaylistStates(StatesGroup):
    """Steps of the playlist conversations."""

    waiting_for_name = State()        # creating a playlist: waiting for its name
    waiting_for_code = State()        # opening a playlist: waiting for its code
    waiting_for_photo = State()       # setting a cover: waiting for a photo
    choosing_options = State()        # create: choosing private / custom code
    waiting_for_custom_code = State() # create: typing a custom code

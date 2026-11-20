# -*- coding: utf-8 -*-
# 纯 Python 桩：resemblyzer 顶层 import webrtcvad，但本项目改用 Silero VAD 裁静音，故只需可导入。


class Vad(object):
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "webrtcvad 桩：本机无 MSVC 编译器，请改用 trim_silence=False / Silero VAD")

    def is_speech(self, frame, sample_rate):
        raise NotImplementedError("webrtcvad 桩")

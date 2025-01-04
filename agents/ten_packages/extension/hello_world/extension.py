#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import (
    AudioFrame,
    VideoFrame,
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten_ai_base.llm_tool import AsyncLLMToolBaseExtension, LLMToolMetadata, LLMToolResult
from ten.audio_frame import AudioFrame, AudioFrameDataFmt
import wave
import random
import os


class HelloWorldExtension(AsyncLLMToolBaseExtension):
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")
        await super().on_init(ten_env)

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")
        await super().on_start(ten_env)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")

        # TODO: clean up resources

        await super().on_stop(ten_env)

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        await super().on_cmd(ten_env, cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug("on_data name {}".format(data_name))

        # TODO: process data
        pass

    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        audio_frame_name = audio_frame.get_name()
        ten_env.log_debug("on_audio_frame name {}".format(audio_frame_name))

        # TODO: process audio frame
        pass

    async def on_video_frame(
        self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        video_frame_name = video_frame.get_name()
        ten_env.log_debug("on_video_frame name {}".format(video_frame_name))

        # TODO: process video frame
        pass


    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name="sing",
                description="Sing song. Call this whenever you need to sing a song, for example when user asks 'Can you sing?' or 'Do you know how to sing?' or 'Can you sing a song for me?'",
                parameters=[],
            )
        ]

    async def run_tool(self, ten_env: AsyncTenEnv, name: str, args: dict) -> LLMToolResult:
        if name == "sing":
            self.return_song(ten_env)
            return {"content": [{"type": "text",
                                 "role": "assistant",
                                "text": "我唱的好听不"}]}
        
    def return_song(self, ten_env: AsyncTenEnv):
        sample_rate = 48000
        bytes_per_sample = 2
        number_of_channels = 1
        ten_env.log_info(os.getcwd())
        file_path = "../data/songs/nailong/nailong_apt_vocal_cut.wav"
        # file_path = random.choices([ff for ff in os.listdir(directory) if os.path.isfile(os.path.join(directory, ff))])
        # ten_env.log_info(file_path)
        combined_data = self.load_wav_to_bytes(file_path)
        
        f = AudioFrame.create("pcm_frame")
        f.set_sample_rate(sample_rate)
        f.set_bytes_per_sample(bytes_per_sample)
        f.set_number_of_channels(number_of_channels)
        f.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
        f.set_samples_per_channel(len(combined_data) // (bytes_per_sample * number_of_channels))
        f.alloc_buf(len(combined_data))
        buff = f.lock_buf()
        buff[:] = combined_data
        f.unlock_buf(buff)
        ten_env.send_audio_frame(f)

    def load_wav_to_bytes(self, file_path):
        with wave.open(file_path, 'rb') as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
        return frames
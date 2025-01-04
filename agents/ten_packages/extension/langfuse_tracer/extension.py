#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import base64
import json
import os
import threading
import time
import datetime
import uuid
from ten import (
    AudioFrame,
    VideoFrame,
    Extension,
    AsyncExtension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from enum import Enum
from io import BytesIO
from PIL import Image
from pydub import AudioSegment
import numpy as np
import asyncio
from langfuse import Langfuse
from .utils import upload_image_to_cos, upload_audio_to_cos
from base64 import b64encode


TEXT_DATA_TEXT_FIELD = "text"
TEXT_DATA_FINAL_FIELD = "is_final"
TEXT_DATA_STREAM_ID_FIELD = "stream_id"
TEXT_DATA_END_OF_SEGMENT_FIELD = "end_of_segment"
PROPERTY_CHANNEL_NAME = "channel"

# record the cached text data for each stream id
cached_text_map = {}

langfuse = Langfuse(
    secret_key="sk-lf-662b6664-f4d5-4ff1-8b53-3100e7c097ac",
    public_key="pk-lf-ee1c7350-b542-4ec5-b286-85560caebc85",
    host="http://datacentric.club:3000"
)

class Role(str, Enum):
    User = "user"
    Assistant = "assistant"

class LangfuseTracerExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.video_frame = ""
        self.channel_name="default_channel"

    def on_init(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_start")
        try:
            self.channel_name = ten_env.get_property_string(PROPERTY_CHANNEL_NAME)
        except Exception as err:
            ten_env.error(f"GetProperty channel failed, err: {err}")
        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_stop")
        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_info("on_cmd name {}".format(cmd_name))

        # TODO: process cmd
        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        """
        on_data receives data from ten graph.
        current suppotend data:
          - name: text_data
            example:
            {"name": "text_data", "properties": {"text": "hello", "is_final": true, "stream_id": 123, "end_of_segment": true}}
        """

        text = ""
        final = True
        stream_id = 0
        end_of_segment = False
        try:
            self.channel_name = ten_env.get_property_string(PROPERTY_CHANNEL_NAME)
        except Exception as err:
            ten_env.log_error(f"GetProperty required {PROPERTY_CHANNEL_NAME} failed, err: {err}")
        
        try:
            text = data.get_property_string(TEXT_DATA_TEXT_FIELD)
        except Exception as e:
            ten_env.log_error(
                f"on_data get_property_string {TEXT_DATA_TEXT_FIELD} error: {e}"
            )

        try:
            final = data.get_property_bool(TEXT_DATA_FINAL_FIELD)
        except Exception as e:
            pass

        try:
            stream_id = data.get_property_int(TEXT_DATA_STREAM_ID_FIELD)
        except Exception as e:
            pass

        try:
            end_of_segment = data.get_property_bool(
                TEXT_DATA_END_OF_SEGMENT_FIELD)
        except Exception as e:
            ten_env.log_warn(
                f"on_data get_property_bool {TEXT_DATA_END_OF_SEGMENT_FIELD} error: {e}"
            )

        # We cache all final text data and append the non-final text data to the cached data
        # until the end of the segment.
        if end_of_segment:
            if stream_id in cached_text_map:
                text = cached_text_map[stream_id] + text
                del cached_text_map[stream_id]
        else:
            if final:
                if stream_id in cached_text_map:
                    text = cached_text_map[stream_id] + text

                cached_text_map[stream_id] = text

        session_id = self.channel_name + '_' + datetime.datetime.now().strftime("%Y-%m-%d")
        if end_of_segment:
            trace = langfuse.trace(
                name="asr-llm-tts",
                user_id=self.channel_name,
                session_id=session_id,
                tags=["production"]
            )
        if end_of_segment and (stream_id == 0):
            trace.update(output=text)
        elif end_of_segment and (stream_id != 0):
            image_url = ""
            audio_url = ""
            try:
                image_url = self.upload_video_frame(ten_env)
            except:
                ten_env.log_error("failed to upload image/audio to cos!!")
            
            try:
                audio_url = self.upload_audio_frame(ten_env)
            except:
                ten_env.log_error("failed to upload image/audio to cos!!")
            
            input = f"{text} \n ![image]({image_url}) \n ![audio]({audio_url})"
            trace.update(input=input)


    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        # audio_frame_name = audio_frame.get_name()
        frame_buf = audio_frame.get_buf()
        if not frame_buf:
            self.ten_env.log_warn("send_frame: empty pcm_frame detected.")
            return

        try:
            self.stream_id = audio_frame.get_property_int("stream_id")
            # ten_env.log_info(f"stream_id: {self.stream_id}")
            self._dump_audio_if_need(frame_buf,  Role.User)
        except:
            self._dump_audio_if_need(frame_buf,  Role.Assistant)
        
    
    def _dump_audio_if_need(self, buf: bytearray, role: Role) -> None:
        # if not self.config.dump:
        #     return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M")
        save_path = "output_audio/{}_{}_{}.pcm".format(role, self.channel_name, timestamp)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "ab") as dump_file:
            dump_file.write(buf)
        

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # TODO: process image frame
        # video_frame_name = video_frame.get_name()
        self.video_frame = video_frame
    
    def upload_audio_frame(self, ten_env):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M")
        load_pcm_path = "output_audio/{}_{}_{}.pcm".format(Role.User, self.channel_name, timestamp)
        save_wav_path = "output_audio/{}_{}_{}.wav".format(Role.User, self.channel_name, timestamp)
        
        try:
            # 检查PCM文件是否存在
            if not os.path.exists(load_pcm_path):
                return None
                
            # 计算20秒音频的字节大小
            # 采样率16000 * 采样位数2 * 通道数1 * 秒数20
            bytes_20_seconds = 16000 * 2 * 1 * 20
            
            # 读取PCM文件
            with open(load_pcm_path, 'rb') as f:
                pcm_data = f.read()
                
            # 只取最后20秒的数据
            if len(pcm_data) > bytes_20_seconds:
                pcm_data = pcm_data[-bytes_20_seconds:]
                
            # 使用numpy转换PCM数据
            audio_data = np.frombuffer(pcm_data, dtype=np.int16)
            
            # 创建AudioSegment对象
            audio_segment = AudioSegment(
                audio_data.tobytes(),
                frame_rate=16000,
                sample_width=2,
                channels=1
            )
            
            # 保存为WAV文件
            audio_segment.export(save_wav_path, format="wav")
            
            # 上传到COS
            audio_cos_url = upload_audio_to_cos(save_wav_path)
            
            # 删除临时文件
            if os.path.exists(save_wav_path):
                os.remove(save_wav_path)
                
            return audio_cos_url
        
        except Exception as e:
            ten_env.log_error(f"Failed to process audio: {str(e)}")
            return None
    
    def upload_video_frame(self, ten_env):
        image_data = self.video_frame.get_buf()
        image_width = self.video_frame.get_width()
        image_height = self.video_frame.get_height()
        pil_image = Image.frombytes(
            "RGBA", (image_width, image_height), bytes(image_data))
        pil_image = pil_image.convert("RGB")

        save_path = os.path.join('output_images', self.channel_name + '_' + datetime.datetime.now().strftime(
            "%Y-%m-%d_%H:%M:%S_%f") + '.jpg')
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        pil_image.save(save_path, format="JPEG")
        image_cos_url = upload_image_to_cos(save_path)
        return image_cos_url
    
    # def upload_audio_frame_bak(self, ten_env):
    #     timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M")
    #     load_pcm_path = "output_audio/{}_{}_{}.pcm".format(Role.User, self.channel_name, timestamp)
    #     save_wav_path = "output_audio/{}_{}_{}.wav".format(Role.User, self.channel_name, timestamp)
    #     try:
    #         self.pcm_to_wav(load_pcm_path, save_wav_path, sample_rate=16000, num_channels=1, sample_width=2)
    #     except:
    #         return
    #     if not os.path.exists(save_wav_path):
    #         return
        
    #     audio_cos_url = upload_audio_to_cos(save_wav_path)
    #     return audio_cos_url
        

    def pcm_to_wav(self, pcm_file, wav_file, sample_rate=16000, num_channels=1, sample_width=2):
        # 打开 PCM 文件并读取原始数据
        with open(pcm_file, 'rb') as f:
            pcm_data = f.read()

        # 使用 numpy 转换 PCM 数据为正确的格式
        audio_data = np.frombuffer(pcm_data, dtype=np.int16)  # 2 字节为 16-bit 深度
        if num_channels == 2:
            audio_data = audio_data.reshape(-1, 2)  # 双声道时需要 reshape

        # 创建 AudioSegment 对象
        audio_segment = AudioSegment(
            audio_data.tobytes(),  # PCM 数据
            frame_rate=sample_rate,  # 采样率
            sample_width=sample_width,  # 每个采样的字节数
            channels=num_channels  # 声道数
        )

        # 将 AudioSegment 保存为 WAV 文件
        audio_segment.export(wav_file, format="wav")
        # print(f"PCM 数据已成功转换为 {wav_file}")

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
from io import BytesIO
from PIL import Image
import asyncio
from langfuse import Langfuse
from .utils import upload_to_cos
from base64 import b64encode

MAX_SIZE = 800  # 1 KB limit
OVERHEAD_ESTIMATE = 200  # Estimate for the overhead of metadata in the JSON

CMD_NAME_FLUSH = "flush"

TEXT_DATA_TEXT_FIELD = "text"
TEXT_DATA_FINAL_FIELD = "is_final"
TEXT_DATA_STREAM_ID_FIELD = "stream_id"
TEXT_DATA_END_OF_SEGMENT_FIELD = "end_of_segment"

# record the cached text data for each stream id
cached_text_map = {}
MAX_CHUNK_SIZE_BYTES = 1024

# langfuse = Langfuse(
#     secret_key="sk-lf-ad715cab-1e6d-40cf-8dd8-f4893f031465",
#     public_key="pk-lf-7c52ac2f-908a-402b-9372-f88320c45c3c",
#     host="https://us.cloud.langfuse.com"
# )
langfuse = Langfuse(
    secret_key="sk-lf-662b6664-f4d5-4ff1-8b53-3100e7c097ac",
    public_key="pk-lf-ee1c7350-b542-4ec5-b286-85560caebc85",
    host="http://datacentric.club:3000"
)


def _text_to_base64_chunks(text: str, msg_id: str) -> list:
    # Ensure msg_id does not exceed 50 characters
    if len(msg_id) > 36:
        raise ValueError("msg_id cannot exceed 36 characters.")

    # Convert text to bytearray
    byte_array = bytearray(text, 'utf-8')

    # Encode the bytearray into base64
    base64_encoded = base64.b64encode(byte_array).decode('utf-8')

    # Initialize list to hold the final chunks
    chunks = []

    # We'll split the base64 string dynamically based on the final byte size
    part_index = 0
    total_parts = None  # We'll calculate total parts once we know how many chunks we create

    # Process the base64-encoded content in chunks
    current_position = 0
    total_length = len(base64_encoded)

    while current_position < total_length:
        part_index += 1

        # Start guessing the chunk size by limiting the base64 content part
        estimated_chunk_size = MAX_CHUNK_SIZE_BYTES  # We'll reduce this dynamically
        content_chunk = ""
        count = 0
        while True:
            # Create the content part of the chunk
            content_chunk = base64_encoded[current_position:
                                           current_position + estimated_chunk_size]

            # Format the chunk
            formatted_chunk = f"{msg_id}|{part_index}|{total_parts if total_parts else '???'}|{content_chunk}"

            # Check if the byte length of the formatted chunk exceeds the max allowed size
            if len(bytearray(formatted_chunk, 'utf-8')) <= MAX_CHUNK_SIZE_BYTES:
                break
            else:
                # Reduce the estimated chunk size if the formatted chunk is too large
                estimated_chunk_size -= 100  # Reduce content size gradually
                count += 1

        # logger.debug(f"chunk estimate guess: {count}")

        # Add the current chunk to the list
        chunks.append(formatted_chunk)
        # Move to the next part of the content
        current_position += estimated_chunk_size

    # Now that we know the total number of parts, update the chunks with correct total_parts
    total_parts = len(chunks)
    updated_chunks = [
        chunk.replace("???", str(total_parts)) for chunk in chunks
    ]

    return updated_chunks


class LangfuseTracerExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.video_frame = ""

    # Create the queue for message processing
    queue = asyncio.Queue()

    def on_init(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_start")

        # TODO: read properties, initialize resources
        self.loop = asyncio.new_event_loop()

        def start_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        threading.Thread(target=start_loop, args=[]).start()

        self.loop.create_task(self._process_queue(ten_env))

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_stop")

        # TODO: clean up resources

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
        # ten_env.log_debug(f"on_data")
        # span = trace.span(
        #     name="embedding-search",
        #     metadata={"database": "pinecone"},
        #     input={'query': 'This document entails the OKR goals for ACME'},
        # )

        text = ""
        final = True
        stream_id = 0
        end_of_segment = False

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

        # Generate a unique message ID for this batch of parts
        message_id = str(uuid.uuid4())[:8]

        # Prepare the main JSON structure without the text field
        base_msg_data = {
            "is_final": end_of_segment,
            "stream_id": stream_id,
            "message_id": message_id,  # Add message_id to identify the split message
            "data_type": "transcribe",
            "text_ts": int(time.time() * 1000),  # Convert to milliseconds
            "text": text,
        }

        if end_of_segment:
            trace = langfuse.trace(
                name="asr-llm-tts",
                user_id="user__935d7d1d-8625-4ef4-8651-544613e7bd22",
                session_id=datetime.datetime.now().strftime("%Y-%m-%d"),
                tags=["production"]
            )
        if end_of_segment and (stream_id == 0):
            trace.update(output=text)
        elif end_of_segment and (stream_id != 0):
            image_url = ""
            try:
                image_url = self.upload_video_frame(ten_env)
            except:
                ten_env.log_warn("failed to upload image to cos!!")
            input = f"{text}, ![image]({image_url})"
            trace.update(input=input)

        try:
            chunks = _text_to_base64_chunks(
                json.dumps(base_msg_data), message_id)
            for chunk in chunks:
                asyncio.run_coroutine_threadsafe(
                    self._queue_message(chunk), self.loop)

        except Exception as e:
            ten_env.log_warn(f"on_data new_data error: {e}")
            return

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        audio_frame_name = audio_frame.get_name()
        frame_buf = audio_frame.get_buf()
        if not frame_buf:
            self.ten_env.log_warn("send_frame: empty pcm_frame detected.")
            return
        # self.stream_id = audio_frame.get_property_int('stream_id')

        # ten_env.log_info(
        #     "====================================================================================================")
        # ten_env.log_info("on_audio_frame name {}".format(audio_frame_name))
        # ten_env.log_info(
        #     "====================================================================================================")

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # TODO: process image frame
        video_frame_name = video_frame.get_name()
        self.video_frame = video_frame

    def upload_video_frame(self, ten_env):
        image_data = self.video_frame.get_buf()
        image_width = self.video_frame.get_width()
        image_height = self.video_frame.get_height()
        pil_image = Image.frombytes(
            "RGBA", (image_width, image_height), bytes(image_data))
        pil_image = pil_image.convert("RGB")

        save_path = os.path.join('output_images', datetime.datetime.now().strftime(
            "%Y-%m-%d_%H:%M:%S") + '.jpg')
        os.makedirs(os.path.basename(save_path), exist_ok=True)
        pil_image.save(save_path, format="JPEG")
        cos_url = upload_to_cos(save_path)
        return cos_url

    async def _queue_message(self, data: str):
        await self.queue.put(data)

    async def _process_queue(self, ten_env: TenEnv):
        while True:
            data = await self.queue.get()
            if data is None:
                break
            # process data
            ten_data = Data.create("data")
            ten_data.set_property_buf("data", data.encode())
            ten_env.send_data(ten_data)
            self.queue.task_done()
            await asyncio.sleep(0.04)
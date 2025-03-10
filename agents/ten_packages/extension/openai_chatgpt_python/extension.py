#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
import json
import time
import traceback
from typing import Iterable
import uuid
import io
import os
import datetime
import base64
import threading
from PIL import Image

from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.const import CMD_PROPERTY_RESULT, CMD_TOOL_CALL, CONTENT_DATA_OUT_NAME, DATA_OUT_PROPERTY_END_OF_SEGMENT, DATA_OUT_PROPERTY_TEXT
from ten_ai_base.helper import (
    AsyncEventEmitter,
    get_property_bool,
    get_property_string,
)
from ten_ai_base.types import (
    LLMCallCompletionArgs,
    LLMChatCompletionContentPartParam,
    LLMChatCompletionUserMessageParam,
    LLMChatCompletionMessageParam,
    LLMDataCompletionArgs,
    LLMToolMetadata,
    LLMToolResult,
)
from ten_ai_base.llm import AsyncLLMBaseExtension

from .helper import parse_sentences
from .openai import OpenAIChatGPT, OpenAIChatGPTConfig
from ten import (
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from .utils import rgb2base64jpeg, filter_images
from .my_mem0 import MyMemManager

CMD_IN_FLUSH = "flush"
CMD_IN_ON_USER_JOINED = "on_user_joined"
CMD_IN_ON_USER_LEFT = "on_user_left"
CMD_OUT_FLUSH = "flush"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"
MAX_IMAGE_COUNT = 20
ONE_BATCH_SEND_COUNT = 1
VIDEO_FRAME_INTERVAL = 0.5


class OpenAIChatGPTExtension(AsyncLLMBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.memory = []
        self.memory_cache = []
        self.config = None
        self.client = None
        self.sentence_fragment = ""
        self.tool_task_future: asyncio.Future | None = None
        self.users_count = 0
        self.last_reasoning_ts = 0

        self.image_buffers: list = []
        self.image_queue = asyncio.Queue()
        self.ctx = None
        # self.is_enable_video = True
        self.stopped: bool = False


    async def on_init(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_init")
        await super().on_init(async_ten_env)

    async def on_start(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_start")
        await super().on_start(async_ten_env)

        self.config = await OpenAIChatGPTConfig.create_async(ten_env=async_ten_env)

        # Mandatory properties
        if not self.config.api_key:
            async_ten_env.log_info("API key is missing, exiting on_start")
            return

        # Create instance
        try:
            self.client = OpenAIChatGPT(async_ten_env, self.config)
            async_ten_env.log_info(
                f"initialized with max_tokens: {self.config.max_tokens}, model: {self.config.model}, vendor: {self.config.vendor}"
            )
        except Exception as err:
            async_ten_env.log_info(f"Failed to initialize OpenAIChatGPT: {err}")

        # 初始化记忆管理器
        # if self.config.is_memory_enabled:
        try:
            self.memory_manager = MyMemManager(async_ten_env, self.config)
            async_ten_env.log_info("Successfully initialized memory manager")
        except Exception as err:
            async_ten_env.log_info(f"Failed to initialize memory manager: {err}")
            self.memory_manager = None  # 确保设置为 None

        await self._setup_components(async_ten_env)

    async def _setup_components(self, async_ten_env: AsyncTenEnv) -> None:
        """Set up extension components."""
        self.memory = []
        
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._on_video(async_ten_env))
        # Add periodic task for scene description
        self.loop.create_task(self._periodic_scene_description(async_ten_env))

    async def _periodic_scene_description(self, async_ten_env) -> None:
        """Periodically trigger scene description in Chinese and English."""
        while not self.stopped:
            try:
                # async_ten_env.log_info("--------------------hahahahahahah--------------------")
                await asyncio.sleep(60)  # Wait for 10 seconds
                self.text_buffer = "当前用户没有主动询问，判断当前场景如果不需要鼓励或安慰或者和上一句回复内容基本一致的话，就保持沉默，输出空字符''"
                await self._handle_input_truncation(async_ten_env, "is_final")
            except Exception as e:
                async_ten_env.log_error(f"Error in periodic scene description: {e}")
                await asyncio.sleep(1)  # Short delay on error before retrying

    async def _handle_input_truncation(self, async_ten_env, reason: str):
        """Handle input truncation events."""
        try:
            async_ten_env.log_info(f"Input truncated due to: {reason}")
            
            if self.text_buffer:
                # await self._call_nova_model(self.text_buffer, self.image_buffers)
                # await self._call_doubao_model(self.text_buffer, self.image_buffers)
                # await self.queue_input_item(False, messages=[message])
                d = Data.create("text_data")
                d.set_property_bool("is_final", True)
                d.set_property_string("text", self.text_buffer)
                
                await self.on_data(async_ten_env, d)
            
            self._reset_state()
            
        except Exception as e:
            traceback.print_exc()
            async_ten_env.log_error(f"Error handling input truncation: {e}")

    async def on_video_frame(self, _: AsyncTenEnv, video_frame) -> None:
        """Handle incoming video frames."""
        # if not self.config.is_enable_video:
        #     return
        image_data = video_frame.get_buf()
        image_width = video_frame.get_width()
        image_height = video_frame.get_height()
        await self.image_queue.put([image_data, image_width, image_height])

    async def _on_video(self, async_ten_env: AsyncTenEnv):
        """Process video frames from the queue."""
        while True:
            try:
                [image_data, image_width, image_height] = await self.image_queue.get()

                frame_buffer = rgb2base64jpeg(image_data, image_width, image_height)
                
                self.image_buffers.append(frame_buffer)
               
                while len(self.image_buffers) > MAX_IMAGE_COUNT:
                    self.image_buffers.pop(0)
                
                # Skip remaining frames for the interval
                while not self.image_queue.empty():
                    await self.image_queue.get()
                    
                await asyncio.sleep(VIDEO_FRAME_INTERVAL)
                
            except Exception as e:
                traceback.print_exc()
                async_ten_env.log_error(f"Error processing video frame: {e}")


    async def on_stop(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_stop")
        await super().on_stop(async_ten_env)
        self.reasoning_text_queue.put_nowait(None)
        self.stopped = True

    async def on_deinit(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_deinit")
        await super().on_deinit(async_ten_env)

    async def on_cmd(self, async_ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        async_ten_env.log_info(f"on_cmd name: {cmd_name}")

        if cmd_name == CMD_IN_FLUSH:
            await self.flush_input_items(async_ten_env)
            await async_ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            async_ten_env.log_info("on_cmd sent flush")
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        elif cmd_name == CMD_IN_ON_USER_JOINED:
            self.users_count += 1
            # Send greeting when first user joined
            if self.config.greeting and self.users_count == 1:
                self.send_text_output(async_ten_env, self.config.greeting, True)

            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        elif cmd_name == CMD_IN_ON_USER_LEFT:
            self.users_count -= 1
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        else:
            await super().on_cmd(async_ten_env, cmd)

    async def on_data(self, async_ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        async_ten_env.log_debug("on_data name {}".format(data_name))

        # Get the necessary properties
        is_final = get_property_bool(data, "is_final")
        input_text = get_property_string(data, "text")

        try:
            # 只有当 memory_manager 存在时才使用记忆功能
            memory_text = ""
            if hasattr(self, 'memory_manager') and self.memory_manager is not None:
                memory_text = self.memory_manager.search(input_text, user_id="user")
                async_ten_env.log_info(f"Retrieved memory text: {memory_text}")
            
            prompt = f"User input: {input_text}"
            if memory_text:
                prompt += f"\nPrevious memories: {memory_text}"
            async_ten_env.log_info(f"Final prompt: {prompt}")

            contents = [{"type": "text","text": prompt}]

            async_ten_env.log_info(f"image_buffers: {self.image_buffers}")
            if self.image_buffers:
                # filtered_buffers = filter_images(self.image_buffers, ONE_BATCH_SEND_COUNT)
                filtered_buffers = self.image_buffers[-ONE_BATCH_SEND_COUNT:]
                # for image_data in filtered_buffers:
                #     contents.append({
                #         "type": "image",
                #         "image": {
                #             "format": 'jpeg',
                #             "source": {
                #                 "bytes": image_data
                #             }
                #         }
                #     })
                for image_data in filtered_buffers:
                    try:
                        img_process_start = time.time()
                        img = Image.open(io.BytesIO(image_data))
                        
                        # Resize image to have longest side = 320px while maintaining aspect ratio
                        width, height = img.size
                        max_dimension = max(width, height)
                        scale_factor = 320 / max_dimension
                        new_width = int(width * scale_factor)
                        new_height = int(height * scale_factor)
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                        async_ten_env.log_info(f"Resized image from {width}x{height} to {new_width}x{new_height}")
                        
                        output_buffer = io.BytesIO()
                        img.save(output_buffer, format='JPEG', quality=95)
                        image_save_path = "save_images"
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        os.makedirs(image_save_path, exist_ok=True)
                        image_path = os.path.join(image_save_path, f"image_{timestamp}.jpg")
                        # Save the image
                        with open(image_path, "wb") as f:
                            f.write(output_buffer.getvalue())
                        output_buffer.seek(0)
                        jpeg_base64 = base64.b64encode(output_buffer.getvalue()).decode('ascii')
                        
                        contents.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{jpeg_base64}",
                                "detail": "low"
                            }
                        })
                        async_ten_env.log_info(f"Single image processing took: {(time.time() - img_process_start)*1000:.2f}ms")
                    except Exception as e:
                        async_ten_env.log_error(f"Error processing image: {e}")
                        continue

            # 处理记忆操作
            def process_memory_operations():
                mem_time = time.time()
                async_ten_env.log_info(f"Adding Memory")
                try:
                    self.memory_manager.memory.add(input_text, user_id="user")
                    async_ten_env.log_info(f"Adding Cost:{round(time.time() - mem_time, 2)}")
                except Exception as mem_err:
                    async_ten_env.log_warn(f"Memory addition failed: {str(mem_err)}")

            thread = threading.Thread(target=process_memory_operations)
            thread.start()

            if not is_final:
                async_ten_env.log_debug("ignore non-final input")
                return
            if not input_text:
                async_ten_env.log_warn("ignore empty text")
                return

            async_ten_env.log_info(f"OnData input text: [{input_text}]")

            # Start an asynchronous task for handling chat completion
            message = LLMChatCompletionUserMessageParam(role="user", content=contents)

            await self.queue_input_item(False, messages=[message])
        except Exception as e:
            traceback.print_exc()
            async_ten_env.log_error(f"Error processing data: {e}")

    async def on_tools_update(
        self, async_ten_env: AsyncTenEnv, tool: LLMToolMetadata
    ) -> None:
        return await super().on_tools_update(async_ten_env, tool)

    async def on_call_chat_completion(
        self, async_ten_env: AsyncTenEnv, **kargs: LLMCallCompletionArgs
    ) -> any:
        kmessages: LLMChatCompletionUserMessageParam = kargs.get("messages", [])

        async_ten_env.log_info(f"on_call_chat_completion: {kmessages}")
        response = await self.client.get_chat_completions(kmessages, None)
        return response.to_json()

    async def on_data_chat_completion(
        self, async_ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs
    ) -> None:
        """Run the chatflow asynchronously."""
        kmessages: Iterable[LLMChatCompletionUserMessageParam] = kargs.get(
            "messages", []
        )

        if len(kmessages) == 0:
            async_ten_env.log_error("No message in data")
            return

        messages = []
        for message in kmessages:
            messages = messages + [self.message_to_dict(message)]

        self.memory_cache = []
        memory = self.memory
        try:
            async_ten_env.log_info(f"for input text: [{messages}] memory: {memory}")
            tools = None
            no_tool = kargs.get("no_tool", False)

            for message in messages:
                if (
                    not isinstance(message.get("content"), str)
                    and message.get("role") == "user"
                ):
                    non_artifact_content = [
                        item
                        for item in message.get("content", [])
                        if item.get("type") == "text"
                    ]
                    non_artifact_message = {
                        "role": message.get("role"),
                        "content": non_artifact_content,
                    }
                    self.memory_cache = self.memory_cache + [
                        non_artifact_message,
                    ]
                else:
                    self.memory_cache = self.memory_cache + [
                        message,
                    ]
            self.memory_cache = self.memory_cache + [{"role": "assistant", "content": ""}]

            tools = None
            if not no_tool and len(self.available_tools) > 0:
                tools = []
                for tool in self.available_tools:
                    tools.append(self._convert_tools_to_dict(tool))
                    async_ten_env.log_info(f"tool: {tool}")

            self.sentence_fragment = ""

            # Create an asyncio.Event to signal when content is finished
            content_finished_event = asyncio.Event()
            # Create a future to track the single tool call task
            self.tool_task_future = None

            message_id = str(uuid.uuid4())[:8]
            self.last_reasoning_ts = int(time.time() * 1000)

            # Create an async listener to handle tool calls and content updates
            async def handle_tool_call(tool_call):
                self.tool_task_future = asyncio.get_event_loop().create_future()
                async_ten_env.log_info(f"tool_call: {tool_call}")
                for tool in self.available_tools:
                    if tool_call["function"]["name"] == tool.name:
                        cmd: Cmd = Cmd.create(CMD_TOOL_CALL)
                        cmd.set_property_string("name", tool.name)
                        cmd.set_property_from_json(
                            "arguments", tool_call["function"]["arguments"]
                        )
                        # cmd.set_property_from_json("arguments", json.dumps([]))

                        # Send the command and handle the result through the future
                        [result, _] = await async_ten_env.send_cmd(cmd)
                        if result.get_status_code() == StatusCode.OK:
                            tool_result: LLMToolResult = json.loads(
                                result.get_property_to_json(CMD_PROPERTY_RESULT)
                            )

                            async_ten_env.log_info(f"tool_result: {tool_result}")

                            if tool_call["function"]["name"] == "sing":
                                # self.memory_cache.pop()
                                self.send_text_output(async_ten_env, tool_result["content"].encode('utf-8').decode('unicode_escape'), True)
                            
                            else:
                                if tool_result["type"] == "llmresult":
                                    result_content = tool_result["content"]
                                    if isinstance(result_content, str):
                                        tool_message = {
                                            "role": "assistant",
                                            "tool_calls": [tool_call],
                                        }
                                        new_message = {
                                            "role": "tool",
                                            "content": result_content,
                                            "tool_call_id": tool_call["id"],
                                        }
                                        await self.queue_input_item(
                                            True, messages=[tool_message, new_message], no_tool=True
                                        )
                                    else:
                                        async_ten_env.log_error(
                                            f"Unknown tool result content: {result_content}"
                                        )
                                elif tool_result["type"] == "requery":
                                    # self.memory_cache = []
                                    self.memory_cache.pop()
                                    result_content = tool_result["content"]
                                    nonlocal message
                                    new_message = {
                                        "role": "user",
                                        "content": self._convert_to_content_parts(
                                            message["content"]
                                        ),
                                    }
                                    new_message["content"] = new_message[
                                        "content"
                                    ] + self._convert_to_content_parts(result_content)
                                    await self.queue_input_item(
                                        True, messages=[new_message], no_tool=True
                                    )
                                else:
                                    async_ten_env.log_error(
                                        f"Unknown tool result type: {tool_result}"
                                    )
                        else:
                            async_ten_env.log_error("Tool call failed")
                self.tool_task_future.set_result(None)

            async def handle_content_update(content: str):
                # Append the content to the last assistant message
                for item in reversed(self.memory_cache):
                    if item.get("role") == "assistant":
                        item["content"] = item["content"] + content
                        break
                sentences, self.sentence_fragment = parse_sentences(
                    self.sentence_fragment, content
                )
                for s in sentences:
                    self.send_text_output(async_ten_env, s, False)

            async def handle_reasoning_update(think: str):
                ts = int(time.time() * 1000)
                if ts - self.last_reasoning_ts >= 200:
                    self.last_reasoning_ts = ts
                    self.send_reasoning_text_output(async_ten_env, message_id, think, False)


            async def handle_reasoning_update_finish(think: str):
                self.last_reasoning_ts = int(time.time() * 1000)
                self.send_reasoning_text_output(async_ten_env, message_id, think, True)

            async def handle_content_finished(_: str):
                # Wait for the single tool task to complete (if any)
                if self.tool_task_future:
                    await self.tool_task_future
                content_finished_event.set()

            listener = AsyncEventEmitter()
            listener.on("tool_call", handle_tool_call)
            listener.on("content_update", handle_content_update)
            listener.on("reasoning_update", handle_reasoning_update)
            listener.on("reasoning_update_finish", handle_reasoning_update_finish)
            listener.on("content_finished", handle_content_finished)

            # Make an async API call to get chat completions
            await self.client.get_chat_completions_stream(
                memory + messages, tools, listener
            )

            # Wait for the content to be finished
            await content_finished_event.wait()

            async_ten_env.log_info(
                f"Chat completion finished for input text: {messages}"
            )
        except asyncio.CancelledError:
            async_ten_env.log_info(f"Task cancelled: {messages}")
        except Exception:
            async_ten_env.log_error(
                f"Error in chat_completion: {traceback.format_exc()} for input text: {messages}"
            )
        finally:
            self.send_text_output(async_ten_env, "", True)
            # always append the memory
            for m in self.memory_cache:
                self._append_memory(m)

    def _convert_to_content_parts(
        self, content: Iterable[LLMChatCompletionContentPartParam]
    ):
        content_parts = []

        if isinstance(content, str):
            content_parts.append({"type": "text", "text": content})
        else:
            for part in content:
                content_parts.append(part)
        return content_parts

    def _convert_tools_to_dict(self, tool: LLMToolMetadata):
        json_dict = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
            "strict": True,
        }

        for param in tool.parameters:
            json_dict["function"]["parameters"]["properties"][param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                json_dict["function"]["parameters"]["required"].append(param.name)

        return json_dict

    def message_to_dict(self, message: LLMChatCompletionMessageParam):
        if message.get("content") is not None:
            if isinstance(message["content"], str):
                message["content"] = str(message["content"])
            else:
                message["content"] = list(message["content"])
        return message

    def _append_memory(self, message: str):
        if len(self.memory) > self.config.max_memory_length:
            removed_item = self.memory.pop(0)
            # Remove tool calls from memory
            if removed_item.get("tool_calls") and self.memory[0].get("role") == "tool":
                self.memory.pop(0)
        self.memory.append(message)

    def send_reasoning_text_output(
        self, async_ten_env: AsyncTenEnv, msg_id:str, sentence: str, end_of_segment: bool
    ):
        try:
            output_data = Data.create(CONTENT_DATA_OUT_NAME)
            output_data.set_property_string(DATA_OUT_PROPERTY_TEXT, json.dumps({
                "id":msg_id,
                "data": {
                    "text": sentence
                },
                "type": "reasoning"
            }))
            output_data.set_property_bool(
                DATA_OUT_PROPERTY_END_OF_SEGMENT, end_of_segment
            )
            asyncio.create_task(async_ten_env.send_data(output_data))
            # async_ten_env.log_info(
            #     f"{'end of segment ' if end_of_segment else ''}sent sentence [{sentence}]"
            # )
        except Exception:
            async_ten_env.log_warn(
                f"send sentence [{sentence}] failed, err: {traceback.format_exc()}")
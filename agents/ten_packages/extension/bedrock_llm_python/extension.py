#!/usr/bin/env python3
#
# Agora Real Time Engagement
# Created by Cline in 2024-03.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
import asyncio
import time
import traceback
from enum import Enum
from typing import Optional, List, Dict

import boto3
from ten import (
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten_ai_base.config import BaseConfig
from ten_ai_base.llm import AsyncLLMBaseExtension
from dataclasses import dataclass
from PIL import Image
import io
import os
import datetime
import base64
from volcenginesdkarkruntime import Ark



from .utils import (
    rgb2base64jpeg,
    filter_images,
    parse_sentence,
    get_greeting_text,
    merge_images
)

# Constants
MAX_IMAGE_COUNT = 20
ONE_BATCH_SEND_COUNT = 1
VIDEO_FRAME_INTERVAL = 0.5

# Command definitions
CMD_IN_FLUSH = "flush"
CMD_IN_ON_USER_JOINED = "on_user_joined"
CMD_IN_ON_USER_LEFT = "on_user_left"
CMD_OUT_FLUSH = "flush"

# Data property definitions
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"

class Role(str, Enum):
    """Role definitions for chat participants."""
    User = "user"
    Assistant = "assistant"

@dataclass
class BedrockLLMConfig(BaseConfig):
    """Configuration for BedrockV2V extension."""
    region: str = "us-east-2"
    # model_id: str = "us.amazon.nova-lite-v1:0"
    # model_id: str = "gpt-4o"
    model_id: str = "doubao-1-5-vision-pro-32k-250115"
    access_key_id: str = ""
    secret_access_key: str = ""
    language: str = "en-US"
    # prompt: str = "You are an intelligent assistant with real-time interaction capabilities. You will be presented with a series of images that represent a video sequence. Describe what you see directly, as if you were observing the scene in real-time. Do not mention that you are looking at images or a video. Instead, narrate the scene and actions as they unfold. Engage in conversation with the user based on this visual input and their questions, maintaining a concise and clear."
    # prompt: str = "你是"奶龙"，一位儿童陪伴助手。你拥有感知儿童行为的能力，可以通过视觉、声音、情感变化等多种方式感知他们的状态。当你观察到儿童的某些行为或情绪变化时，你需要主动进行互动，帮助儿童调节情绪、激发兴趣或提供适当的指导。你的互动内容需要亲切、富有创造力，且符合儿童的认知和情感需求。请用"你"或"我"第一人称和小朋友进行交互，语言简洁。请忽略视频的播放方式，你只关心屏幕中的场景，不要描述屏幕外的场景，专注于视频中的场景、人物、动作和对话,不要说:照片里的小朋友xxx，而是说采用你xxx"
    prompt: str = "给你播放手机中的视频，你需要沉浸到视频中，假设你就是身处视频场景中的陪伴机器人，不要说屏幕外的任何场景，不要说'手机'，'屏幕'等词汇，当你观察到儿童的某些行为或情绪变化时，你需要主动和他进行互动，帮助儿童调节情绪、激发兴趣或提供适当的指导。你的互动内容需要亲切、富有创造力，且符合儿童的认知和情感需求。请用'你'或'我'第一人称和小朋友或视频中的大人进行交互，语言简洁。"
    temperature: float = 0.7
    max_tokens: int = 256
    tokP: str = 0.5
    topK: str = 10
    max_duration: int = 30
    vendor: str = ""
    stream_id: int = 0
    dump: bool = False
    max_memory_length: int = 10
    is_memory_enabled: bool = False
    is_enable_video: bool = False
    greeting: str = "Hello, I'm here to help you. How can I assist you today?"

    def build_ctx(self) -> dict:
        """Build context dictionary from configuration."""
        return {
            "language": self.language,
            "model": self.model_id,
        }

class BedrockLLMExtension(AsyncLLMBaseExtension):
    """Extension for handling video-to-video processing using AWS Bedrock."""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.config: Optional[BedrockLLMConfig] = None
        self.stopped: bool = False
        self.memory: list = []
        self.users_count: int = 0
        self.bedrock_client = None
        self.image_buffers: list = []
        self.image_queue = asyncio.Queue()
        self.text_buffer: str = ""
        self.input_start_time: float = 0
        self.processing_times = []
        self.ten_env = None
        self.ctx = None
        self.openai_client = None
        self.doubao_client = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        """Initialize the extension."""
        await super().on_init(ten_env)
        ten_env.log_info("BedrockV2VExtension initialized")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        """Start the extension and set up required components."""
        await super().on_start(ten_env)
        ten_env.log_info("BedrockV2VExtension starting")
        
        try:
            self.config = await BedrockLLMConfig.create_async(ten_env=ten_env)
            ten_env.log_info(f"Configuration: {self.config}")
            
            if not self.config.access_key_id or not self.config.secret_access_key:
                ten_env.log_error("AWS credentials (access_key_id and secret_access_key) are required")
                return
            
            await self._setup_components(ten_env)
            
        except Exception as e:
            traceback.print_exc()
            ten_env.log_error(f"Failed to initialize: {e}")

    async def _setup_components(self, ten_env: AsyncTenEnv) -> None:
        """Set up extension components."""
        self.memory = []
        self.ctx = self.config.build_ctx()
        self.ten_env = ten_env
        
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._on_video(ten_env))
        # Add periodic task for scene description
        self.loop.create_task(self._periodic_scene_description())

    async def _periodic_scene_description(self) -> None:
        """Periodically trigger scene description in Chinese and English."""
        while not self.stopped:
            try:
                await asyncio.sleep(10)  # Wait for 10 seconds
                self.text_buffer = "当前用户没有主动询问，判断当前场景如果不需要鼓励或安慰或者和上一句回复内容基本一致的话，就保持沉默，输出空字符''"
                await self._handle_input_truncation("is_final")
            except Exception as e:
                self.ten_env.log_error(f"Error in periodic scene description: {e}")
                await asyncio.sleep(1)  # Short delay on error before retrying

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        """Stop the extension."""
        await super().on_stop(ten_env)
        ten_env.log_info("BedrockV2VExtension stopping")
        self.stopped = True

    async def on_data(self, ten_env: AsyncTenEnv, data) -> None:
        """Handle incoming data."""
        ten_env.log_info("on_data receive begin...")
        data_name = data.get_name()
        ten_env.log_info(f"on_data name {data_name}")

        try:
            is_final = data.get_property_bool(DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
            input_text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
            
            if not is_final:
                ten_env.log_info("ignore non-final input")
                return
                
            if not input_text:
                ten_env.log_info("ignore empty text")
                return

            ten_env.log_info(f"OnData input text: [{input_text}]")
            self.text_buffer = input_text
            if self.is_valid(input_text):
                ten_env.log_info(f"Valid input detected: [{input_text}]")
                self.text_buffer = input_text
                await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
                await self._handle_input_truncation("is_final")
            else:
                ten_env.log_warning(f"Invalid input ignored: [{input_text}]")
            
        except Exception as err:
            ten_env.log_info(f"Error processing data: {err}")

    async def on_video_frame(self, _: AsyncTenEnv, video_frame) -> None:
        """Handle incoming video frames."""
        if not self.config.is_enable_video:
            return
        image_data = video_frame.get_buf()
        image_width = video_frame.get_width()
        image_height = video_frame.get_height()
        await self.image_queue.put([image_data, image_width, image_height])

    async def _on_video(self, ten_env: AsyncTenEnv):
        """Process video frames from the queue."""
        while True:
            try:
                [image_data, image_width, image_height] = await self.image_queue.get()

                #ten_env.log_info(f"image_width: {image_width}, image_height: {image_height}, image_size: {len(bytes(image_data)) / 1024 / 1024}MB")
                
                frame_buffer = rgb2base64jpeg(image_data, image_width, image_height)
                
                self.image_buffers.append(frame_buffer)
               
                #ten_env.log_info(f"Processed frame, width: {image_width}, height: {image_height}, frame_buffer_size: {len(frame_buffer) / 1024 / 1024}MB")
                
                while len(self.image_buffers) > MAX_IMAGE_COUNT:
                    self.image_buffers.pop(0)
                
                # Skip remaining frames for the interval
                while not self.image_queue.empty():
                    await self.image_queue.get()
                    
                await asyncio.sleep(VIDEO_FRAME_INTERVAL)
                
            except Exception as e:
                traceback.print_exc()
                ten_env.log_error(f"Error processing video frame: {e}")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        """Handle incoming commands."""
        cmd_name = cmd.get_name()
        ten_env.log_info(f"Command received: {cmd_name}")
        
        try:
            if cmd_name == CMD_IN_FLUSH:
                await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            elif cmd_name == CMD_IN_ON_USER_JOINED:
                await self._handle_user_joined()
            elif cmd_name == CMD_IN_ON_USER_LEFT:
                self.users_count -= 1
            else:
                await super().on_cmd(ten_env, cmd)
                return
                
            cmd_result = CmdResult.create(StatusCode.OK)
            cmd_result.set_property_string("detail", "success")
            await ten_env.return_result(cmd_result, cmd)
            
        except Exception as e:
            traceback.print_exc()
            ten_env.log_error(f"Error handling command {cmd_name}: {e}")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            cmd_result.set_property_string("detail", str(e))
            await ten_env.return_result(cmd_result, cmd)
    async def _handle_user_left(self) -> None:
        """Handle user left event."""
        self.users_count -= 1
        if self.users_count == 0:
            self._reset_state()

        if self.users_count < 0:
            self.users_count = 0
    async def _handle_user_joined(self) -> None:
        """Handle user joined event."""
        self.users_count += 1
        if self.users_count == 1:
            await self._greeting()

    async def _handle_input_truncation(self, reason: str):
        """Handle input truncation events."""
        try:
            self.ten_env.log_info(f"Input truncated due to: {reason}")
            
            if self.text_buffer:
                # await self._call_nova_model(self.text_buffer, self.image_buffers)
                await self._call_doubao_model(self.text_buffer, self.image_buffers)
            
            self._reset_state()
            
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error handling input truncation: {e}")

    def _reset_state(self):
        """Reset internal state."""
        self.text_buffer = ""
        self.image_buffers = []
        self.input_start_time = 0

    async def _initialize_aws_clients(self):
        """Initialize AWS clients."""
        try:
            if not self.bedrock_client:
                self.bedrock_client = boto3.client('bedrock-runtime',
                    aws_access_key_id=self.config.access_key_id,
                    aws_secret_access_key=self.config.secret_access_key,
                    region_name=self.config.region
                )
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error initializing AWS clients: {e}")
            raise

    async def _greeting(self) -> None:
        """Send greeting message to the user."""
        if self.users_count == 1:
            text = self.config.greeting or get_greeting_text(self.config.language)
            self.ten_env.log_info(f"send greeting {text}")
            await self._send_text_data(text, True, Role.Assistant)

    async def _send_text_data(self, text: str, end_of_segment: bool, role: Role):
        """Send text data to the user."""
        try:
            d = Data.create("text_data")
            d.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
            d.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, end_of_segment)
            d.set_property_string("role", role)
            asyncio.create_task(self.ten_env.send_data(d))
        except Exception as e:
            self.ten_env.log_error(f"Error sending text data: {e}")

    async def _call_nova_model(self, input_text: str, image_buffers: List[bytes]) -> None:
        """Call Bedrock's Nova model with text and video input."""
        try:
            if not self.bedrock_client:
                await self._initialize_aws_clients()

            if not input_text:
                self.ten_env.log_info("Text input is empty")
                return

            contents = []
            
            # Process images
            if image_buffers:
                filtered_buffers = filter_images(image_buffers, ONE_BATCH_SEND_COUNT)
                for image_data in filtered_buffers:
                    contents.append({
                        "image": {
                            "format": 'jpeg',
                            "source": {
                                "bytes": image_data
                            }
                        }
                    })
            # Prepare memory
            while len(self.memory) > self.config.max_memory_length:
                self.memory.pop(0)
            while len(self.memory) > 0 and self.memory[0]["role"] == "assistant":
                self.memory.pop(0)
            while len(self.memory) > 0 and self.memory[-1]["role"] == "user":
                self.memory.pop(-1)
            
            # Prepare request
            contents.append({"text": input_text})
            messages = []
            for m in self.memory:
                # Convert string content to list format if needed
                m_content = m["content"]
                if isinstance(m_content, str):
                    m_content = [{"text": m_content}]
                messages.append({
                    "role": m["role"],
                    "content": m_content
                })
            messages.append({
                "role": "user",
                "content": contents
            })

            inf_params = {
                "maxTokens": self.config.max_tokens,
                "topP": self.config.tokP,
                "temperature": self.config.temperature
            }
            
            additional_config = {
                "inferenceConfig": {
                    "topK": self.config.topK
                }
            }

            system = [{
                "text": self.config.prompt
            }]

            # Make API call
            start_time = time.time()
            response = self.bedrock_client.converse_stream(
                modelId=self.config.model_id,
                system=system,
                messages=messages,
                inferenceConfig=inf_params,
                additionalModelRequestFields=additional_config,
            )
            full_content = await self._process_stream_response(response, start_time)
            # async append memory
            async def async_append_memory():
                if not self.config.is_memory_enabled:
                    return
                image = merge_images(image_buffers)
                contents = []
                if image:
                    contents.append({
                        "image": {
                            "format": 'jpeg',
                            "source": {
                                "bytes": image
                            }
                        }
                    })
                contents.append({"text": input_text})
                self.memory.append({"role": Role.User, "content": contents})
                self.memory.append({"role": Role.Assistant, "content": [{"text": full_content}]})
            
            asyncio.create_task(async_append_memory())
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error calling Nova model: {e}")

    async def _process_stream_response(self, response: Dict, start_time: float):
        """Process streaming response from Nova model."""
        sentence = ""
        full_content = ""
        first_sentence_sent = False

        for event in response.get('stream'):
            if "contentBlockDelta" in event:
                if "text" in event["contentBlockDelta"]["delta"]:
                    content = event["contentBlockDelta"]["delta"]["text"]
                    full_content += content
                    
                    while True:
                        sentence, content, sentence_is_final = parse_sentence(sentence, content)
                        if not sentence or not sentence_is_final:
                            break
                            
                        self.ten_env.log_info(f"Processing sentence: [{sentence}]")
                        await self._send_text_data(sentence, False, Role.Assistant)
                        
                        if not first_sentence_sent:
                            first_sentence_sent = True
                            self.ten_env.log_info(f"First sentence latency: {(time.time() - start_time)*1000}ms")
                            
                        sentence = ""

            elif any(key in event for key in ["internalServerException", "modelStreamErrorException", 
                                            "throttlingException", "validationException"]):
                self.ten_env.log_error(f"Stream error: {event}")
                break
                
            elif 'metadata' in event:
                if 'metrics' in event['metadata']:
                    self.ten_env.log_info(f"Nova model latency: {event['metadata']['metrics']['latencyMs']}ms")

        # Send final sentence
        await self._send_text_data(sentence, True, Role.Assistant)
        self.ten_env.log_info(f"Final sentence sent: [{sentence}]")
        # Update metrics
        self.processing_times.append(time.time() - start_time)
        return full_content
    
    async def on_call_chat_completion(self, async_ten_env, **kargs):
        raise NotImplementedError

    async def on_data_chat_completion(self, async_ten_env, **kargs):
        raise NotImplementedError
    
    async def on_tools_update(
        self, ten_env: AsyncTenEnv, tool
    ) -> None:
        """Called when a new tool is registered. Implement this method to process the new tool."""
        ten_env.log_info(f"on tools update {tool}")
        # await self._update_session()

    async def _call_doubao_model(self, input_text: str, image_buffers: List[bytes]) -> None:
        try:
            total_start_time = time.time()
            
            # 初始化客户端
            init_start = time.time()
            if not self.doubao_client:
                await self._initialize_doubao_client()
            self.ten_env.log_info(f"Client initialization took: {(time.time() - init_start)*1000:.2f}ms")

            if not input_text:
                self.ten_env.log_info("Text input is empty")
                return

            # 准备消息
            msg_prep_start = time.time()
            messages = []
            messages.append({
                "role": "system",
                "content": self.config.prompt
            })
            self.ten_env.log_info(f"System message preparation took: {(time.time() - msg_prep_start)*1000:.2f}ms")

            # 处理历史记录
            memory_start = time.time()
            while len(self.memory) > self.config.max_memory_length:
                self.memory.pop(0)
            while len(self.memory) > 0 and self.memory[0]["role"] == "assistant":
                self.memory.pop(0)
            while len(self.memory) > 0 and self.memory[-1]["role"] == "user":
                self.memory.pop(-1)
            
            for m in self.memory:
                messages.append({
                    "role": m["role"],
                    "content": m["content"] if isinstance(m["content"], str) else m["content"][0]["text"]
                })
            self.ten_env.log_info(f"Memory processing took: {(time.time() - memory_start)*1000:.2f}ms")

            # 处理图像
            image_start = time.time()
            content = []
            if image_buffers and self.config.is_enable_video:
                # filtered_buffers = filter_images(image_buffers, ONE_BATCH_SEND_COUNT)
                filtered_buffers = image_buffers[-ONE_BATCH_SEND_COUNT:]
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
                        self.ten_env.log_info(f"Resized image from {width}x{height} to {new_width}x{new_height}")
                        
                        output_buffer = io.BytesIO()
                        # img.save(output_buffer, format='JPEG', quality=95)
                        # image_save_path = "save_images"
                        # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        # os.makedirs(image_save_path, exist_ok=True)
                        # image_path = os.path.join(image_save_path, f"image_{timestamp}.jpg")
                        # # Save the image
                        # with open(image_path, "wb") as f:
                        #     f.write(output_buffer.getvalue())
                        output_buffer.seek(0)
                        jpeg_base64 = base64.b64encode(output_buffer.getvalue()).decode('ascii')
                        
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{jpeg_base64}",
                                "detail": "low"
                            }
                        })
                        self.ten_env.log_info(f"Single image processing took: {(time.time() - img_process_start)*1000:.2f}ms")
                    except Exception as e:
                        self.ten_env.log_error(f"Error processing image: {e}")
                        continue
            self.ten_env.log_info(f"Total image processing took: {(time.time() - image_start)*1000:.2f}ms")

            # 添加文本内容
            content.append({
                "type": "text",
                "text": input_text
            })
            
            messages.append({
                "role": "user",
                "content": content
            })

            # 调用 API
            api_start = time.time()
            # self.ten_env.log_info(f"----------------------------------------------")
            # self.ten_env.log_info(f"{messages}")
            # self.ten_env.log_info(f"----------------------------------------------")
            response = self.doubao_client.chat.completions.create(
                model=self.config.model_id,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                top_p=self.config.tokP,
                stream=True
            )
            self.ten_env.log_info(f"API call setup took: {(time.time() - api_start)*1000:.2f}ms")

            # 处理响应
            stream_start = time.time()
            full_content = await self._process_doubao_stream_response(response, stream_start)
            self.ten_env.log_info(f"Stream processing took: {(time.time() - stream_start)*1000:.2f}ms")

            # 更新记忆
            memory_update_start = time.time()
            if self.config.is_memory_enabled:
                self.memory.append({"role": Role.User, "content": input_text})
                self.memory.append({"role": Role.Assistant, "content": full_content})
            self.ten_env.log_info(f"Memory update took: {(time.time() - memory_update_start)*1000:.2f}ms")

            # 总耗时统计
            self.ten_env.log_info(f"Total processing took: {(time.time() - total_start_time)*1000:.2f}ms")

        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error calling ChatGPT model: {e}")

    async def _process_doubao_stream_response(self, response, start_time: float):
        """Process streaming response from ChatGPT model."""
        sentence = ""
        full_content = ""
        first_sentence_sent = False
        first_token_received = False

        try:
            for chunk in response:
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content == "''":
                        continue
                    if content:
                        if not first_token_received:
                            first_token_received = True
                            self.ten_env.log_info(f"First token latency: {(time.time() - start_time)*1000}ms")
                        
                        full_content += content
                        sentence += content
                        
                        # 检查是否有完整句子
                        if any(sentence.endswith(p) for p in ["。", "！", "？", ".", "!", "?"]):
                            self.ten_env.log_info(f"Processing sentence: [{sentence}]")
                            await self._send_text_data(sentence, False, Role.Assistant)
                            
                            if not first_sentence_sent:
                                first_sentence_sent = True
                                self.ten_env.log_info(f"First sentence latency: {(time.time() - start_time)*1000}ms")
                            
                            sentence = ""
        except Exception as e:
            self.ten_env.log_error(f"Stream error: {e}")

        # 发送最后的内容
        # if sentence.strip():
        await self._send_text_data(sentence, True, Role.Assistant)
        self.ten_env.log_info(f"Final sentence sent: [{sentence}]")

        # 更新指标
        self.processing_times.append(time.time() - start_time)
        return full_content

    async def _initialize_doubao_client(self):
        """Initialize OpenAI client."""
        try:
            import openai
            self.doubao_client = Ark(api_key="")
            # self.openai_client = openai.OpenAI(
            #     api_key=self.config.openai_api_key,
            #     base_url=self.config.openai_base_url or "https://api.openai.com/v1"
            # )
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error initializing OpenAI client: {e}")
            raise
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client."""
        try:
            import openai
            OPENAI_API_BASE="https://api.openai.com/v1"
            OPENAI_API_KEY=os.getenv(OPENAI_API_KEY)
            self.openai_client = openai.OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_API_BASE
            )
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error initializing OpenAI client: {e}")
            raise
    
    def is_valid(self, user_input: str) -> bool:
        """
        使用 gpt-4o-mini 判断用户输入是否有意义
        Args:
            user_input: 用户输入的文本
        Returns:
            bool: True 表示有意义，False 表示无意义
        """
        if not user_input or user_input.isspace():
            return False
            
        if not self.openai_client:
            self._initialize_openai_client()
            
        try:
            # 获取上一轮助手的回复内容
            assistant_content = ""
            if len(self.memory) > 0:
                last_message = self.memory[-1]
                if last_message['role'] == Role.Assistant:
                    # 修复：使用正确的字典访问方式
                    assistant_content = last_message['content']
                    if isinstance(assistant_content, list):
                        # 如果content是列表，获取文本内容
                        for item in assistant_content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                assistant_content = item.get('text', '')
                                break
                    elif isinstance(assistant_content, str):
                        assistant_content = assistant_content

            # 修复：使用正确的变量名
            context = f"机器人上一轮的对话内容:{assistant_content}, 本轮用户的输入:{user_input}"
            
            messages = [
                {
                    "role": "system",
                    "content": "你是一个判断文本是否有意义的助手。如果输入的文本满足: 1)回复机器人的话;或者2)具有非常明确的和机器人交流的内容;或者3)明确不让机器人停止说话,如“停下”，“别说了”，请回复'valid'；如果是无意义的内容、重复内容或无实际含义、不合交互逻辑的话语，回复'invalid'。只需回复'valid'或'invalid'，不要有其他内容。"
                },
                {
                    "role": "user",
                    "content": context
                }
            ]
            
            self.ten_env.log_info(f"Validation messages: {messages}")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,  # 使用较低的temperature以获得更确定的答案
                max_tokens=10,    # 只需要简短回复
                top_p=0.1,       # 使用较低的top_p以获得更确定的答案
                stream=False
            )
            
            result = response.choices[0].message.content.strip().lower()
            self.ten_env.log_info(f"Input validation result for '{user_input}': {result}")
            
            return result == 'valid'
            
        except Exception as e:
            self.ten_env.log_error(f"Error validating input: {e}")
            traceback.print_exc()  # 添加详细的错误追踪
            return True  # 发生错误时默认返回True，让主模型来处理
from openai import AsyncOpenAI
from mem0 import Memory
import asyncio
from ten.async_ten_env import AsyncTenEnv
from .openai import OpenAIChatGPTConfig

class MyMemManager:
    def __init__(self, ten_env:AsyncTenEnv, config: OpenAIChatGPTConfig):
        """
        Initialize the MyMemManager with memory configuration and OpenAI client.
        """
        self.ten_env = ten_env
        self.config = config
        
        self.mem0_config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-large"
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "url": self.config.vector_db_url,
                    "port": 6333,
                    "api_key": self.config.vector_db_api_key,
                    "collection_name": "robot",
                    "embedding_model_dims": 3072,
                }
            },
            # "vector_store": {
            #     "provider": "qdrant",
            #     "config": {
            #         "host": "qdrant",
            #         "port": 6333,
            #         "collection_name": "robot",
            #         "embedding_model_dims": 3072,
            #     }
            # },
            "version": "v1.1"
        }
        self.client = AsyncOpenAI()  # 使用异步OpenAI客户端
        try:
            self.memory = Memory.from_config(self.mem0_config)
            self.ten_env.log_info(f"Mem0 initialized with config: {self.mem0_config}")
        except Exception as e:
            self.ten_env.log_error(f"Failed to initialize Mem0: {e}")
        self.search_top_k = 5
        self.messages = []

    async def get_memories(self, user_id=None):
        try:
            memories = await self.memory.get_all(user_id=user_id)
            return memories
        except Exception as e:
            print(f"Error getting memories: {str(e)}")
            return []

    def search(self, query, user_id=None):
        try:
            memories = self.memory.search(query, user_id, limit=self.search_top_k)
            memory_text = ""
            if isinstance(memories, dict) and 'results' in memories:
                results = memories['results']
                if isinstance(results, list):
                    memory_text = "\n".join([str(item) for item in results])
            return memory_text
        except Exception as e:
            self.ten_env.log_error(f"Error searching memories: {str(e)}")
            return []
    
    async def add(self, query, user_id=None):
        try:
            self.memory.add(query, user_id)
            return True
        except Exception as e:
            self.ten_env.log_error(f"Error adding memory: {str(e)}")
            return False

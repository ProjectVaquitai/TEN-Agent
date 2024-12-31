#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import ChatGPTMem0Extension


@register_addon_as_extension("chatgpt_mem0")
class ChatGPTMem0ExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        ten_env.log_info("ChatGPTMem0ExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(ChatGPTMem0Extension(name), context)

# encoding:utf-8

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from plugins import *
from .ocr import ocr_from_image
from .model import Blip
from PIL import Image
import io

@plugins.register(
    name="readim",
    desire_priority=0,
    hidden=False,
    desc="A plugin that convert image with blip2(or other model) and ocr",
    version="0.2.1",
    author="loping151",
)
class readim(Plugin):
    def __init__(self):
        super().__init__()
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "config.json")
        self.state = {} # 切换激活状态, 分开各个channel状态
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.lang = config.get("lang", "eng+chi_sim")
                self.prefix_verb = config["prefix_verb"]
                self.prefix_noun = config["prefix_noun"]
                self.always_read_image = config["always_read_image"]
                self.default_allow_ocr = config["default_allow_ocr"]
                self.free_cuda_memory = config["free_cuda_memory"] # 如果使用cpu运行blip2,这个参数不会造成影响
                self.model = config["model"]
                if self.model == "blip2": # allowed: blip2 only for now
                    self.model = Blip(free_cuda_memory=self.free_cuda_memory)
                elif self.model == "something_else": # 这样添加你的接口
                    pass
                self.allow_ocr = {}
                
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            logger.info("[readim] inited")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                logger.warn(f"[readim] init failed, {config_path} not found, ignore or see")
            else:
                logger.warn("[readim] init failed, ignore or see ")
            raise e
        
    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [
            ContextType.TEXT,
            ContextType.IMAGE
        ]:
            return
            
        content = e_context['context'].content
        session_id = e_context['context'].kwargs['session_id']
        receiver = e_context['context'].kwargs['receiver']
        user = e_context['context'].kwargs['msg'].to_user_nickname
        
        if e_context["context"].type == ContextType.TEXT and not self.always_read_image:
            is_verb, is_noun = False, False
            for verb in self.prefix_verb:
                if verb in content:
                    is_verb = True
            for noun in self.prefix_noun:
                if noun in content:
                    is_noun = True
            if is_verb and is_noun:
                self.state[session_id+receiver+user] = True
                if not self.model.ready:
                    logger.info(f"视觉模型未就绪")
                    e_context["context"].content += f"你的回答需要包括：你的读图功能还没有准备好, 需要等等你" # 这些都是发给bot的提示词，可以自己改。我觉得现在的不错，先不写在config
                else:
                    e_context["context"].content += f"。现在, 你可以读取普片了, 请你向我索要图片"
            if '开启' in content and 'ocr' in content: # 暂时没有接入plugin的标准命令
                self.allow_ocr[session_id] = True
                logger.info(f"ocr开启了")
                e_context["context"].content = f"现在, 你的ocr功能被开启了"
                e_context.action = EventAction.BREAK
            elif '关闭' in content and 'ocr' in content:
                self.allow_ocr[session_id] =False
                logger.info(f"ocr关闭了")
                e_context["context"].content = f"现在, 你的ocr功能被禁用了"
            e_context.action = EventAction.BREAK
            return
            
            
        if (e_context["context"].type == ContextType.IMAGE and self.state.get(session_id+receiver+user, False)) or self.always_read_image:
            e_context["context"].type = ContextType.TEXT
            msg: ChatMessage = e_context["context"]["msg"]
            if not self.model.ready:
                logger.info(f"视觉模型未就绪")
                e_context["context"].content = f"你的回答需要包括：你的读图功能还没有准备好, 需要等等你"
            else:
                try:
                    msg.prepare()
                    with open(content, 'rb') as file:
                        image_data = file.read()
                        logger.info("图片读取成功")
                        image = Image.open(io.BytesIO(image_data))
                        image_caption = self.model.caption_image(image)
                        e_context["context"].content = "我发给了你图片，内容是{}, ".format(image_caption)
                        if self.allow_ocr.get(receiver, self.default_allow_ocr):
                            image_ocr = ocr_from_image(image, lang=self.lang)
                            e_context["context"].content += "上面写了文字：{}(如果你看不明白上面写了什么, 请你忽略上面写的文字, 不需要告诉我)。".format(image_ocr)
                        e_context["context"].content += "请你假装你自己看到了这张图片的内容, 而不是我告诉你了描述。请假装你真的看到了图片内容，你的回答中千万不要透露你是假装看到的。"
                        
                        try:
                            self.state[session_id+receiver+user]=False # 只有成功的读完了图片，才结束请求。否则无需重新请求，就可以再接受一张图
                        except Exception as e:
                            pass #  一般是always_read_image，无需处理
                except Exception as e:
                    logger.error(f"读取图片数据时出现错误：{e}")
                    e_context["context"].content = f"你没有收到图片或图片处理失败了。"
            e_context.action = EventAction.BREAK
            return


    def get_help_text(self, **kwargs):
        if self.always_read_image:
            help_text = f"现在直接发送图片就可以读\n"
        else:    
            help_text = "尝试在句子中组合动词{}和名词{}吧\n".format(self.prefix_verb, self.prefix_noun)
        help_text+=f"发送 \"开启/关闭 ocr\" 控制是否读取图片的文字信息。只在当前会话中起作用。\n"
        return help_text

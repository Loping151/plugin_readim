from PIL import Image
from transformers import AutoProcessor, Blip2ForConditionalGeneration
import torch
import threading
from common.log import logger
import subprocess

class BaseModel():
    def __init__(self):
        self.free_cuda_memory = None
        self.ready = False
        
    def caption_image(self, image):
        pass
    
class Blip(BaseModel):
    def __init__(self, free_cuda_memory=False) -> None:
        super().__init__()
        self.free_cuda_memory=free_cuda_memory
        self.ready = False
        threading.Thread(target=self.init).start()
    
    # 显式的init，不然开机太慢了。现在改成非阻塞了，但是还是开机要过一会才能用
    def init(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = AutoProcessor.from_pretrained("Salesforce/blip2-opt-2.7b")
        self.model = Blip2ForConditionalGeneration.from_pretrained("Salesforce/blip2-opt-2.7b", torch_dtype=torch.float16)
        self.ready = True
        logger.info("[readim] Blip已就绪")
        
        
    def caption_image(self, image):
        # subprocess.run(['tmux', "kill-window", "-t", "webui"]) # 临时关闭webui，搭配webui自启动使用
        
        if self.free_cuda_memory:
            self.model.to(self.device)

        inputs = self.processor(image, return_tensors="pt").to(self.device, torch.float16)

        generated_ids = self.model.generate(**inputs, max_new_tokens=20)
        generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        
        if self.free_cuda_memory:    
            self.model.to("cpu")
            torch.cuda.empty_cache()
        return generated_text

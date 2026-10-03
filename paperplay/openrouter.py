"""Budgeted OpenRouter Chat Completions client."""
from __future__ import annotations
import json, os, time
import requests
from dataclasses import dataclass
from .config import GEN_TOKENS

class ModelCallError(RuntimeError): pass
@dataclass
class Completion:
    content:str; prompt_tokens:int; completion_tokens:int; reasoning_tokens:int; elapsed_seconds:float; response_id:str|None

class OpenRouter:
    endpoint="https://openrouter.ai/api/v1/chat/completions"
    def __init__(self,model,budget,trace): self.model,self.budget,self.trace=model,budget,trace
    def complete(self,messages,max_tokens=GEN_TOKENS,action="generate"):
        key=os.getenv("OPENROUTER_API_KEY","").strip()
        if not key: raise ModelCallError("OPENROUTER_API_KEY is not set.")
        if not self.budget.can_afford(max_tokens): raise ModelCallError("Request budget exhausted.")
        # This endpoint must return a complete machine-readable artifact. Hidden
        # reasoning counts against the same completion ceiling and can truncate
        # otherwise valid JSON, so reserve the response budget for JSON itself.
        payload={"model":self.model,"messages":messages,"max_tokens":max_tokens,"temperature":.2,"response_format":{"type":"json_object"},"reasoning":{"effort":"none"},"usage":{"include":True}}
        last=None
        for attempt in range(2):
            self.budget.requests+=1; started=time.monotonic(); status=None
            try:
                response=requests.post(self.endpoint,json=payload,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},timeout=min(240,max(10,self.budget.remaining_s-20)))
                status=response.status_code
                if status in (400,422) and attempt==0:
                    self.trace.log("llm",action,"parameter_fallback",http=status,request_no=self.budget.requests)
                    payload.pop("response_format",None); payload.pop("reasoning",None)
                    for message in payload["messages"]:
                        if isinstance(message.get("content"),list):
                            message["content"]="\n".join(x.get("text","") for x in message["content"] if x.get("type")=="text")
                    last="unsupported optional parameter or image input"; continue
                response.raise_for_status(); data=response.json(); usage=data.get("usage") or {}; details=usage.get("completion_tokens_details") or {}
                choice=data["choices"][0];content=choice["message"].get("content");finish_reason=choice.get("finish_reason")
                if not isinstance(content,str) or not content.strip(): raise ValueError("empty text completion")
                out=Completion(content,int(usage.get("prompt_tokens",0)),int(usage.get("completion_tokens",0)),int(details.get("reasoning_tokens",0)),time.monotonic()-started,data.get("id"))
                self.budget.record(out.prompt_tokens,out.completion_tokens,out.reasoning_tokens)
                self.trace.log("llm",action,"ok",model=self.model,prompt_tokens=out.prompt_tokens,completion_tokens=out.completion_tokens,reasoning_tokens=out.reasoning_tokens,total_tokens=out.prompt_tokens+out.completion_tokens,elapsed_s=round(out.elapsed_seconds,3),http=status,request_no=self.budget.requests,generation_id=out.response_id,finish_reason=finish_reason)
                return out
            except (requests.RequestException,KeyError,IndexError,TypeError,ValueError) as exc:
                last=type(exc).__name__; self.trace.log("llm",action,"retry" if attempt==0 else "fail",http=status,request_no=self.budget.requests,error=last)
                if attempt==0 and self.budget.can_afford(max_tokens): time.sleep(2); continue
        raise ModelCallError("OpenRouter request failed: %s."%last)

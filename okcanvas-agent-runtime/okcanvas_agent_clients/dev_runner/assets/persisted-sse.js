"use strict";
(function(root){
  function createParser(handlers={}){
    let buffer="";
    let eventId="";
    let eventType="message";
    let data=[];
    function dispatch(){
      if(data.length===0){eventId="";eventType="message";return}
      const payload={id:eventId,event:eventType,data:data.join("\n")};
      eventId="";eventType="message";data=[];
      if(handlers.onEvent)handlers.onEvent(payload);
    }
    function line(value){
      if(value===""){dispatch();return}
      if(value.startsWith(":")){if(handlers.onComment)handlers.onComment(value.slice(1).trim());return}
      const colon=value.indexOf(":");
      const field=colon<0?value:value.slice(0,colon);
      let fieldValue=colon<0?"":value.slice(colon+1);
      if(fieldValue.startsWith(" "))fieldValue=fieldValue.slice(1);
      if(field==="id")eventId=fieldValue;
      else if(field==="event")eventType=fieldValue||"message";
      else if(field==="data")data.push(fieldValue);
      else if(field==="retry"&&handlers.onRetry){const retry=Number(fieldValue);if(Number.isFinite(retry)&&retry>=0)handlers.onRetry(retry)}
    }
    return {
      feed(chunk){
        buffer+=chunk;
        let newline;
        while((newline=buffer.indexOf("\n"))>=0){
          let current=buffer.slice(0,newline);buffer=buffer.slice(newline+1);
          if(current.endsWith("\r"))current=current.slice(0,-1);
          line(current);
        }
      },
      end(){if(buffer){let current=buffer;if(current.endsWith("\r"))current=current.slice(0,-1);line(current);buffer=""}dispatch()}
    };
  }
  async function stream(options){
    const response=await fetch(options.url,{method:"GET",headers:options.headers,cache:"no-store",signal:options.signal});
    if(!response.ok){const error=new Error(`SSE HTTP ${response.status}`);error.status=response.status;throw error}
    if(!response.body)throw new Error("SSE response body is unavailable");
    if(options.onOpen)options.onOpen(response);
    const parser=createParser({onEvent:options.onEvent,onComment:options.onComment,onRetry:options.onRetry});
    const reader=response.body.getReader();
    const decoder=new TextDecoder("utf-8");
    try{
      while(true){const item=await reader.read();if(item.done)break;parser.feed(decoder.decode(item.value,{stream:true}))}
      parser.feed(decoder.decode());parser.end();
    }finally{reader.releaseLock()}
  }
  root.OKCanvasPersistedSSE={createParser,stream};
})(typeof window!=="undefined"?window:globalThis);

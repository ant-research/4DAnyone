const $ = id => document.getElementById(id);
let canvas = $('canvas'), ctx, compositor;
const stage = $('stage');
const clone = value => JSON.parse(JSON.stringify(value));
const add = (a,b) => a.map((v,i) => v+b[i]);
const sub = (a,b) => a.map((v,i) => v-b[i]);
const mul = (a,k) => a.map(v => v*k);
const dot = (a,b) => a.reduce((v,x,i) => v+x*b[i],0);
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm = a => mul(a,1/Math.hypot(...a));
const rotate = (v,axis,angle) => add(add(mul(v,Math.cos(angle)),mul(cross(axis,v),Math.sin(angle))),mul(axis,dot(axis,v)*(1-Math.cos(angle))));
let ws, meta, pose, epoch=0, seq=0, frame=0, playing=false, playBase=0, playAt=0;
let playbackSpeed=1;
let dirty=false, lastSend=0, heartbeat, pointer, displayed=-1;
let finishPaint=null, reconnectOnVisible=false;
const sent = new Map(), diagnostics = {frames:[], errors:[], connected:false};
window.viewerDiagnostics = diagnostics;
function fallbackCanvas(){
  const replacement=canvas.cloneNode(false);canvas.replaceWith(replacement);canvas=replacement;
  compositor=null;ctx=canvas.getContext('2d',{alpha:false});diagnostics.compositor='server';
}
try {
  const {GridCompositor}=await import('./compositor.js?v=cas-1');
  compositor=new GridCompositor(canvas,{sharpen:new URLSearchParams(location.search).get('sharpen')!=='0'});diagnostics.compositor='webgl2';
  const graphicsCanvas=canvas;
  canvas.addEventListener('webglcontextlost',event=>{
    if(canvas!==graphicsCanvas)return;
    event.preventDefault();fallbackCanvas();ws?.close();
    overlay('Display interrupted','Reconnect to continue with server rendering.',true);
  });
} catch(error){fallbackCanvas();diagnostics.graphicsFallback=String(error);}
// Explicit diagnostic capture redraws the existing textures before readback;
// normal playback does not retain or read back WebGL's drawing buffer.
diagnostics.capture=()=>{compositor?.redraw();return canvas.toDataURL('image/png');};
function overlay(title, message, retry=false) {
  $('overlay').hidden=false;
  $('overlay').querySelector('h2').textContent=title;
  $('overlay').querySelector('p').textContent=message;
  $('overlay').querySelector('.spinner').hidden=retry;
  $('reconnect').hidden=!retry;
}
function status(text) { stage.setAttribute('aria-busy',String(text==='Connecting')); }
function timecode(seconds) {return `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;}
function updateTimeline() {
  $('timeline').value=frame;
  $('timeline').style.setProperty('--progress',`${frame/Math.max(1,meta.frames-1)*100}%`);
  $('timeline').setAttribute('aria-valuetext',`Frame ${frame+1} of ${meta.frames}, ${(frame/meta.fps).toFixed(2)} seconds`);
  $('time').textContent=timecode(frame/meta.fps);
}
function request() {
  if (!meta || ws?.readyState!==WebSocket.OPEN) return;
  dirty=true;
}
function changed() {request();}
function defaultCamera() {
  const camera=clone(meta.camera);
  // Half the original orbit zoom: double the distance from the look-at target.
  camera.position=add(camera.target,mul(sub(camera.position,camera.target),2));
  return camera;
}
function setPlaying(value) {
  playing=value && !!meta && ws?.readyState===WebSocket.OPEN;
  playBase=frame; playAt=performance.now();
  $('play').classList.toggle('playing',playing);
  $('play').setAttribute('aria-label',playing?'Pause':'Play');
  request();
}
function seek(value,discrete=true) {
  if(!meta) return;
  frame=Math.max(0,Math.min(meta.frames-1,Math.round(Number(value)||0)));
  if(discrete)epoch++; playBase=frame; playAt=performance.now(); updateTimeline(); changed();
}
function sendView(now) {
  const id=++seq;
  const payload={type:'view',seq:id,epoch,frame,camera:pose,quality:'final',background:$('background').value,layers:!!compositor,
    viewport:{width:Math.max(1,Math.round(stage.clientWidth)),height:Math.max(1,Math.round(stage.clientHeight))}};
  sent.set(id,now); while(sent.size>500) sent.delete(sent.keys().next().value);
  ws.send(JSON.stringify(payload)); dirty=false; lastSend=now;
}
function tick(now) {
  if(meta && playing) {
    const current=(playBase+Math.floor((now-playAt)*meta.fps*playbackSpeed/1000))%meta.frames;
    if(current!==frame) {frame=current;updateTimeline();request();}
  }
  if(dirty && ws?.readyState===WebSocket.OPEN && now-lastSend>=1000/(meta?.max_fps||30)-1) sendView(now);
  requestAnimationFrame(tick);
}
async function present(buffer, socket) {
  const length=new DataView(buffer).getUint32(0);
  const header=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,4,length)));
  const layered=header.transport==='rgb-alpha-v1', offset=4+length;
  if(layered && (!Number.isSafeInteger(header.color_bytes)||!Number.isSafeInteger(header.alpha_bytes)||header.color_bytes<=0||header.alpha_bytes<=0||offset+header.color_bytes+header.alpha_bytes!==buffer.byteLength))throw Error('Invalid frame layers');
  const blob=new Blob([buffer.slice(offset,layered?offset+header.color_bytes:buffer.byteLength)],{type:header.quality==='lossless'?'image/png':'image/jpeg'});
  if(socket!==ws) return;
  if(!document.hidden && header.epoch===epoch && header.seq>displayed) {
    const started=performance.now(),options={premultiplyAlpha:'none',colorSpaceConversion:'none',imageOrientation:'none'};
    const blobs=[blob];
    if(layered)blobs.push(new Blob([buffer.slice(offset+header.color_bytes)],{type:'image/png'}));
    const decoded=await Promise.allSettled(blobs.map(blob=>createImageBitmap(blob,options)));
    const failed=decoded.find(item=>item.status==='rejected');
    if(failed){for(const item of decoded)if(item.status==='fulfilled')item.value.close();throw failed.reason;}
    const [bitmap,alpha]=decoded.map(item=>item.value), decode_ms=performance.now()-started;
    try {
      // A seek may have happened while the image was decoding.
      if(socket===ws && header.epoch===epoch && header.seq>displayed) {
        if(compositor)compositor.draw(bitmap,alpha,header);
        else {
          if(layered)throw Error('Graphics context unavailable');
          if(canvas.width!==bitmap.width || canvas.height!==bitmap.height){canvas.width=bitmap.width;canvas.height=bitmap.height;}
          ctx.drawImage(bitmap,0,0);
        }
        displayed=header.seq;
        $('overlay').hidden=true;
        await new Promise(resolve=>{
          const done=()=>{cancelAnimationFrame(token);finishPaint=null;resolve();};
          const token=requestAnimationFrame(done);finishPaint=done;
          if(document.hidden)done();
        });
        const now=performance.now(), elapsed=now-(sent.get(header.seq)??now);
        diagnostics.frames.push({...header,presentedAt:now,latency_ms:elapsed,decode_ms,payload_bytes:buffer.byteLength});
        if(diagnostics.frames.length>1000) diagnostics.frames.shift();

      }
    } finally {bitmap.close();alpha?.close();}
  }
  for(const key of sent.keys()) if(key<=header.seq) sent.delete(key);
  if(socket===ws && socket.readyState===WebSocket.OPEN) socket.send(JSON.stringify({type:'ack',seq:header.seq}));
}
function connect() {
  if(ws && ws.readyState<2) ws.close();
  meta=null; dirty=false; displayed=-1; sent.clear(); epoch++;
  clearInterval(heartbeat); overlay('Opening your scene','Preparing the first frame…'); status('Connecting');
  const url=new URL('ws',location.href);url.protocol=location.protocol==='https:'?'wss:':'ws:';
  const socket=new WebSocket(url); ws=socket;
  socket.binaryType='arraybuffer';
  socket.onmessage=async event=>{
    if(socket!==ws) return;
    try {
      if(typeof event.data!=='string') {await present(event.data,socket);return;}
      const message=JSON.parse(event.data);
      if(message.type==='hello') {
        meta=message;pose=defaultCamera();frame=0;seq=0;
        document.title=`${meta.title} · 4DAnyone`;
        $('duration').textContent=timecode(meta.frames/meta.fps);
        $('timeline').max=meta.frames-1;
        diagnostics.connected=true;reconnectOnVisible=true;diagnostics.metadata=meta;status('Connected',true);updateTimeline();request();
        heartbeat=setInterval(()=>{if(socket.readyState===WebSocket.OPEN)socket.send(JSON.stringify({type:'ping'}));},5000);
      } else if(message.type==='busy' || message.type==='error') {
        if(message.type==='busy')reconnectOnVisible=false;
        diagnostics.errors.push(message);overlay(message.type==='busy'?'Viewer in use':'Connection interrupted',message.message,true);
      }
    } catch(error) {
      if(socket!==ws)return;
      if(typeof event.data!=='string' && compositor){fallbackCanvas();diagnostics.graphicsFallback=String(error);}
      diagnostics.errors.push(String(error));overlay('Could not display this frame','Reconnect to reload the scene.',true);socket.close();
    }
  };
  socket.onclose=()=>{
    if(socket!==ws)return;
    clearInterval(heartbeat);setPlaying(false);dirty=false;
    diagnostics.connected=false;status('Disconnected');
    if($('overlay').hidden || $('reconnect').hidden) overlay('Connection closed','Reconnect to continue exploring the scene.',true);
  };
  socket.onerror=()=>status('Connection error');
}
$('reconnect').onclick=connect;
$('play').onclick=()=>setPlaying(!playing);
$('timeline').oninput=event=>seek(event.target.value,false);
$('timeline').onchange=event=>seek(event.target.value,false);
const choiceMenus=[];
function setupChoiceMenu(id,onSelect){
  const button=$(id),menu=$(`${id}-menu`),control=$(`${id}-control`);
  const options=[...menu.querySelectorAll('[data-value]')];
  const close=(restoreFocus=false)=>{
    menu.hidden=true;button.setAttribute('aria-expanded','false');
    if(restoreFocus)button.focus();
  };
  const open=(index=options.findIndex(option=>option.dataset.value===button.value))=>{
    choiceMenus.forEach(other=>other.close());$('help-menu').open=false;
    menu.hidden=false;button.setAttribute('aria-expanded','true');
    options[index].focus({preventScroll:true});
  };
  button.onclick=()=>menu.hidden?open():close();
  button.onkeydown=event=>{
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
      event.preventDefault();open(event.key==='ArrowDown'?0:options.length-1);
    }
  };
  options.forEach(option=>option.onclick=()=>{
    button.value=option.dataset.value;
    $(`${id}-label`).textContent=option.textContent;
    button.setAttribute('aria-label',`${menu.getAttribute('aria-label')}: ${option.textContent}`);
    options.forEach(item=>item.setAttribute('aria-checked',String(item===option)));
    onSelect(button.value);close(true);
  });
  menu.onkeydown=event=>{
    const index=options.indexOf(document.activeElement);
    let next;
    if(event.key==='ArrowDown')next=(index+1)%options.length;
    if(event.key==='ArrowUp')next=(index-1+options.length)%options.length;
    if(event.key==='Home')next=0;
    if(event.key==='End')next=options.length-1;
    if(next!==undefined){event.preventDefault();options[next].focus();}
    if(event.key==='Escape'){event.preventDefault();close(true);}
    if(event.key==='Tab'){
      // Continue native tab order from the trigger, outside the popup.
      button.focus();close();
    }
  };
  control.addEventListener('focusout',event=>{
    if(!control.contains(event.relatedTarget))close();
  });
  choiceMenus.push({control,close});
}
setupChoiceMenu('speed',value=>{
  playbackSpeed=Number(value);playBase=frame;playAt=performance.now();
});
setupChoiceMenu('background',value=>{
  $('background').querySelector('.background-swatch').style.background={black:'#000',gray:'#808080',white:'#fff'}[value];
  epoch++;changed();
});
function resetCamera(){if(meta){pose=defaultCamera();epoch++;changed();}}
function zoom(amount) {
  if(!pose)return;
  const offset=sub(pose.position,pose.target), distance=Math.hypot(...offset);
  const original=Math.hypot(...sub(meta.camera.position,meta.camera.target));
  const next=Math.max(original*.08,Math.min(original*15,distance*Math.exp(amount)));
  pose.position=add(pose.target,mul(offset,next/distance));changed();
}
stage.oncontextmenu=event=>event.preventDefault();
stage.onpointerdown=event=>{
  if(!pose || pointer || event.target.closest('button,a'))return;
  stage.focus({preventScroll:true});pointer={id:event.pointerId,x:event.clientX,y:event.clientY,pan:event.button===2||event.shiftKey};
  stage.setPointerCapture(event.pointerId);
};
stage.onpointermove=event=>{
  if(!pointer || pointer.id!==event.pointerId)return;
  const dx=event.clientX-pointer.x,dy=event.clientY-pointer.y;pointer.x=event.clientX;pointer.y=event.clientY;
  let offset=sub(pose.position,pose.target), up=norm(pose.up), right=norm(cross(mul(offset,-1),up));
  if(pointer.pan || event.shiftKey) {
    const scale=2*Math.hypot(...offset)*Math.tan(pose.fov*Math.PI/360)/(meta.render_mode==='viewport'?stage.clientHeight:Math.min(stage.clientHeight,stage.clientWidth*meta.render_height/meta.render_width));
    const shift=add(mul(right,-dx*scale),mul(norm(cross(right,mul(offset,-1))),dy*scale));
    pose.position=add(pose.position,shift);pose.target=add(pose.target,shift);
  } else {
    offset=rotate(offset,up,-dx*.006);right=norm(cross(mul(offset,-1),up));
    const candidate=rotate(offset,right,-dy*.006);
    if(Math.abs(dot(norm(candidate),up))<.995)offset=candidate;
    pose.position=add(pose.target,offset);
  }
  changed();
};
function release(event){if(pointer?.id===event.pointerId){pointer=null;}}
stage.onpointerup=release;stage.onpointercancel=release;stage.onlostpointercapture=release;
stage.addEventListener('wheel',event=>{event.preventDefault();zoom(Math.max(-.4,Math.min(.4,event.deltaY*.001)));},{passive:false});
document.addEventListener('keydown',event=>{
  if(event.target.closest('input,select,button,summary') || !meta)return;
  if(event.code==='Space'){event.preventDefault();setPlaying(!playing);}
  if(event.code==='ArrowLeft'){event.preventDefault();setPlaying(false);seek(frame-1,!event.repeat);}
  if(event.code==='KeyR' && !event.ctrlKey && !event.metaKey && !event.altKey){event.preventDefault();resetCamera();}
  if(event.code==='ArrowRight'){event.preventDefault();setPlaying(false);seek(frame+1,!event.repeat);}
});
document.addEventListener('pointerdown',event=>{
  if(!event.target.closest('#help-menu'))$('help-menu').open=false;
  choiceMenus.forEach(menu=>{if(!menu.control.contains(event.target))menu.close();});
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape' && $('help-menu').open){
    $('help-menu').open=false;$('help-menu').querySelector('summary').focus();
  }
});
$('help-menu').addEventListener('toggle',()=>{
  if($('help-menu').open)choiceMenus.forEach(menu=>menu.close());
});
document.addEventListener('visibilitychange',()=>{
  if(document.hidden){setPlaying(false);finishPaint?.();}
  else if(ws?.readyState===WebSocket.CLOSED && reconnectOnVisible)connect();
  else request();
});

new ResizeObserver(()=>{if(meta)request();}).observe(stage);
requestAnimationFrame(tick);connect();

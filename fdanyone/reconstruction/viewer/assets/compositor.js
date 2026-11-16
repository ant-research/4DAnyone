// Premultiplied RGB + lossless opacity, composited in the same numeric space
// as the CUDA renderer. The grid always uses the DELIVERED frame's camera.
const vertex = `#version 300 es
void main() {
  vec2 p = vec2((gl_VertexID == 1) ? 3.0 : -1.0, (gl_VertexID == 2) ? 3.0 : -1.0);
  gl_Position = vec4(p, 0.0, 1.0);
}`;
const gridFragment = `#version 300 es
precision highp float;
uniform vec2 size;
uniform vec3 rowU, rowV, rowN, offset;
uniform float extent, spacing, background;
uniform bool enabled;
out vec4 color;
float line(float coordinate, float footprint) {
  float nearest = abs(fract(coordinate + 0.5) - 0.5);
  return clamp(1.0 - nearest / footprint, 0.0, 1.0) * clamp((0.5 - footprint) / 0.35, 0.0, 1.0);
}
float widthAt(vec3 row, float ray, float denominator) {
  vec2 derivative = abs(row.xy * denominator - ray * rowN.xy);
  return max(abs(offset.z) * (derivative.x + derivative.y) / (denominator * denominator) / spacing, 1e-6);
}
void main() {
  float gray = background;
  if (enabled && abs(offset.z) > extent * 1e-5) {
    vec3 pixel = vec3(gl_FragCoord.x, size.y - gl_FragCoord.y, 1.0);
    float ru = dot(rowU, pixel), rv = dot(rowV, pixel), denominator = dot(rowN, pixel);
    if (denominator * sign(offset.z) < -1e-5) {
      float distance = -offset.z / denominator;
      vec2 uv = (offset.xy + distance * vec2(ru, rv)) / spacing;
      vec2 footprint = vec2(widthAt(rowU, ru, denominator), widthAt(rowV, rv, denominator));
      float minor = max(line(uv.x, footprint.x), line(uv.y, footprint.y));
      float major = max(line(uv.x / 5.0, footprint.x / 5.0), line(uv.y / 5.0, footprint.y / 5.0));
      vec3 delta = vec3(distance * ru, distance * rv, offset.z);
      float fade = exp(-dot(delta, delta) / (extent * extent * 400.0));
      gray += max(minor * 0.16, major * 0.28) * fade * (background < 0.5 ? 1.0 : -1.0);
    }
  }
  color = vec4(vec3(clamp(gray, 0.0, 1.0)), 1.0);
}`;
const compositeFragment = `#version 300 es
precision highp float;
uniform sampler2D rgbImage, alphaImage, groundImage;
uniform vec2 size;
uniform vec4 crop;
uniform bool layered, sharpen;
out vec4 color;
// Display-only CAS, using FFmpeg's strength mapping at 0.4 (as in the
// project-page teaser). Work on straight RGB, then restore the original
// opacity. Fade the effect near translucent edges to avoid matte halos.
vec3 sharpenRGB(vec2 uv, vec3 original, float alpha) {
  vec3 samples[9];
  vec2 stepUV = 1.0 / vec2(textureSize(rgbImage, 0));
  float coverage = alpha;
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      vec2 at = uv + vec2(float(x), float(y)) * stepUV;
      float opacity = texture(alphaImage, at).r;
      coverage = min(coverage, opacity);
      samples[(y + 1) * 3 + x + 1] = clamp(texture(rgbImage, at).rgb / max(opacity, 1.0 / 255.0), 0.0, 1.0);
    }
  }
  vec3 lo = samples[4], hi = samples[4];
  for (int k = 1; k < 9; k += 2) {
    lo = min(lo, samples[k]); hi = max(hi, samples[k]);
  }
  vec3 allLo = lo, allHi = hi;
  for (int k = 0; k < 9; k += 2) {
    allLo = min(allLo, samples[k]); allHi = max(allHi, samples[k]);
  }
  lo += allLo; hi += allHi;
  vec3 headroom = min(lo, vec3(511.0 / 255.0) - hi);
  vec3 weight = -sqrt(clamp(headroom / max(hi, vec3(1e-6)), 0.0, 1.0)) / mix(16.0, 4.01, 0.4);
  vec3 neighbors = samples[1] + samples[3] + samples[5] + samples[7];
  vec3 enhanced = clamp((samples[4] + weight * neighbors) / (1.0 + 4.0 * weight), 0.0, 1.0);
  return mix(original, enhanced * alpha, smoothstep(0.8, 1.0, coverage));
}
void main() {
  vec2 screenUV = gl_FragCoord.xy / size;
  vec2 pixel = vec2(gl_FragCoord.x, size.y - gl_FragCoord.y);
  vec2 imageUV = (pixel - crop.xy) / crop.zw;
  bool inside = all(greaterThanEqual(imageUV, vec2(0.0))) && all(lessThan(imageUV, vec2(1.0)));
  vec3 rgb = inside ? texture(rgbImage, imageUV).rgb : vec3(0.0);
  if (layered) {
    float alpha = inside ? texture(alphaImage, imageUV).r : 0.0;
    if (sharpen && inside && alpha > 0.8) rgb = sharpenRGB(imageUV, rgb, alpha);
    // Do not multiply rgb by alpha again: gsplat already did that.
    // Suppress JPEG ringing in fully transparent pixels.
    if (alpha == 0.0) rgb = vec3(0.0);
    rgb += (1.0 - alpha) * texture(groundImage, screenUV).rgb;
  }
  color = vec4(clamp(rgb, 0.0, 1.0), 1.0);
}`;

export class GridCompositor {
  constructor(canvas, {sharpen = true} = {}) {
    this.canvas = canvas;
    this.sharpen = sharpen;
    const gl = this.gl = canvas.getContext('webgl2', {alpha:false, antialias:false, depth:false, stencil:false});
    if (!gl) throw Error('WebGL2 unavailable');
    gl.disable(gl.BLEND); gl.disable(gl.DITHER);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    this.gridProgram = this.program(gridFragment);
    this.compositeProgram = this.program(compositeFragment);
    this.rgbTexture = this.texture(); this.alphaTexture = this.texture(); this.groundTexture = this.texture();
    this.framebuffer = gl.createFramebuffer();
    this.gridKey = null;
    this.gridSize = null; this.textureSizes = [null,null];
    this.maxSize = gl.getParameter(gl.MAX_TEXTURE_SIZE);
  }
  program(fragment) {
    const gl=this.gl, program=gl.createProgram();
    for (const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]) {
      const shader=gl.createShader(type); gl.shaderSource(shader,source); gl.compileShader(shader);
      if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(shader));
      gl.attachShader(program,shader); gl.deleteShader(shader);
    }
    gl.linkProgram(program);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
    return program;
  }
  texture() {
    const gl=this.gl, texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array(4));
    return texture;
  }
  paintGrid(header) {
    const key=JSON.stringify([header.width,header.height,header.grid,header.background]);
    if(key===this.gridKey)return;
    const gl=this.gl,p=this.gridProgram,grid=header.grid;
    gl.activeTexture(gl.TEXTURE2);gl.bindTexture(gl.TEXTURE_2D,this.groundTexture);
    if(this.gridSize!==`${header.width}x${header.height}`){
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,header.width,header.height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
      if(gl.getError()!==gl.NO_ERROR)throw Error('Grid texture allocation failed');
      this.gridSize=`${header.width}x${header.height}`;
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER,this.framebuffer);
    gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,this.groundTexture,0);
    if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('Grid framebuffer unavailable');
    gl.useProgram(p);
    gl.uniform2f(gl.getUniformLocation(p,'size'),header.width,header.height);
    gl.uniform1f(gl.getUniformLocation(p,'background'),header.background);
    gl.uniform1i(gl.getUniformLocation(p,'enabled'),!!grid);
    if(grid){
      for(const [i,name] of ['rowU','rowV','rowN'].entries())gl.uniform3fv(gl.getUniformLocation(p,name),grid.coefficients[i]);
      gl.uniform3fv(gl.getUniformLocation(p,'offset'),grid.offset);
      gl.uniform1f(gl.getUniformLocation(p,'extent'),grid.extent);
      gl.uniform1f(gl.getUniformLocation(p,'spacing'),grid.spacing);
    }
    gl.drawArrays(gl.TRIANGLES,0,3);gl.bindFramebuffer(gl.FRAMEBUFFER,null);
    this.gridKey=key;
  }
  draw(rgb,alpha,header) {
    const gl=this.gl;
    if(header.width>this.maxSize||header.height>this.maxSize)throw Error('Frame exceeds browser texture limit');
    const crop=header.crop||[0,0,header.width,header.height];
    if(crop.length!==4||!crop.every(Number.isSafeInteger)||crop[0]<0||crop[1]<0||crop[2]<1||crop[3]<1||crop[0]+crop[2]>header.width||crop[1]+crop[3]>header.height)throw Error('Invalid frame crop');
    if(rgb.width!==crop[2]||rgb.height!==crop[3]||alpha&&(alpha.width!==rgb.width||alpha.height!==rgb.height))throw Error('Mismatched frame layers');
    if(this.canvas.width!==header.width||this.canvas.height!==header.height){this.canvas.width=header.width;this.canvas.height=header.height;this.gridKey=null;}
    if(gl.drawingBufferWidth!==header.width||gl.drawingBufferHeight!==header.height)throw Error('Browser reduced the drawing buffer');
    gl.viewport(0,0,header.width,header.height);
    if(alpha)this.paintGrid(header);
    let allocated=false;
    for(const [unit,texture,bitmap] of [[0,this.rgbTexture,rgb],[1,this.alphaTexture,alpha]]){
      if(!bitmap)continue;
      gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);
      const size=`${bitmap.width}x${bitmap.height}`;
      if(this.textureSizes[unit]!==size){
        gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,bitmap);
        this.textureSizes[unit]=size;allocated=true;
      } else gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,gl.RGBA,gl.UNSIGNED_BYTE,bitmap);
    }
    if(allocated&&gl.getError()!==gl.NO_ERROR)throw Error('Frame texture allocation failed');
    this.lastHeader=header;this.crop=crop;this.layered=!!alpha;this.redraw();
    if(gl.isContextLost())throw Error('Graphics context lost');
  }
  redraw() {
    const gl=this.gl,p=this.compositeProgram,h=this.lastHeader;
    if(!h)return;
    gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.useProgram(p);
    for(const [unit,name,texture] of [[0,'rgbImage',this.rgbTexture],[1,'alphaImage',this.alphaTexture],[2,'groundImage',this.groundTexture]]){
      gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.uniform1i(gl.getUniformLocation(p,name),unit);
    }
    gl.uniform2f(gl.getUniformLocation(p,'size'),h.width,h.height);
    gl.uniform4fv(gl.getUniformLocation(p,'crop'),this.crop);
    gl.uniform1i(gl.getUniformLocation(p,'layered'),this.layered);
    gl.uniform1i(gl.getUniformLocation(p,'sharpen'),this.sharpen);
    gl.drawArrays(gl.TRIANGLES,0,3);
  }
}

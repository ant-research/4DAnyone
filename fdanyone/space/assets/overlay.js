import {fetchBytes} from './media_cache.js';

export async function createOverlay(content, description, fps, signal) {
    const buffers = await Promise.all(['vertices', 'faces', 'keypoints'].map(key => fetchBytes(description[key], signal)));
    signal.throwIfAborted();
    const vertices = new Float32Array(buffers[0]);
    const faces = new Uint32Array(buffers[1]);
    const points = new Float32Array(buffers[2]);
    const meshCanvas = document.createElement('canvas');
    const skeletonCanvas = document.createElement('canvas');
    meshCanvas.className = skeletonCanvas.className = 'source-overlay';
    meshCanvas.setAttribute('aria-label', 'Recovered SMPL-X Mesh');
    skeletonCanvas.setAttribute('aria-label', 'Recovered Skeleton');
    content.append(meshCanvas, skeletonCanvas);
    const gl = meshCanvas.getContext('webgl2', {alpha: true, antialias: true, premultipliedAlpha: false});
    try {
        if (!gl) throw new Error('Source Overlay Requires WebGL 2');
        const ctx = skeletonCanvas.getContext('2d');
        const shader = (type, code) => {
            const result = gl.createShader(type);
            gl.shaderSource(result, code);
            gl.compileShader(result);
            if (!gl.getShaderParameter(result, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(result));
            return result;
        };
        const vertex = shader(gl.VERTEX_SHADER, `#version 300 es
            in vec3 position;
            uniform vec4 calibration;
            uniform vec2 resolution;
            uniform vec2 fit;
            out vec3 cameraPosition;
            void main() {
                float z = position.z;
                vec2 pixel = position.xy * calibration.xy + calibration.zw * z;
                vec2 clip = (2.0 * pixel / resolution - vec2(z));
                gl_Position = vec4(clip * vec2(1.0, -1.0) * fit, 1.0002 * z - 0.020002, z);
                cameraPosition = position;
            }`);
        const fragment = shader(gl.FRAGMENT_SHADER, `#version 300 es
            precision highp float;
            in vec3 cameraPosition;
            uniform vec3 color;
            out vec4 outputColor;
            void main() {
                vec3 normal = normalize(cross(dFdx(cameraPosition), dFdy(cameraPosition)));
                float light = 0.65 + 0.35 * abs(dot(normal, normalize(vec3(0.2, -0.4, -1.0))));
                outputColor = vec4(color * light, 0.34);
            }`);
        const program = gl.createProgram();
        gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
        const vertexBuffer = gl.createBuffer(), faceBuffer = gl.createBuffer();
        gl.useProgram(program);
        gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, description.vertex_count * 3 * 4, gl.DYNAMIC_DRAW);
        const position = gl.getAttribLocation(program, 'position');
        gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 3, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, faceBuffer); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, faces, gl.STATIC_DRAW);
        const uniforms = Object.fromEntries(['calibration', 'resolution', 'fit', 'color'].map(key => [key, gl.getUniformLocation(program, key)]));
        gl.uniform3fv(uniforms.color, description.color.map(value => value / 255));
        gl.enable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        let previous = -1;
        return {
            draw(time) {
                const frame = Math.max(0, Math.min(description.frames - 1, Math.floor(time * fps + 0.0001)));
                const bounds = content.getBoundingClientRect();
                const width = Math.max(1, Math.round(bounds.width * devicePixelRatio));
                const height = Math.max(1, Math.round(bounds.height * devicePixelRatio));
                if (previous === frame && meshCanvas.width === width && meshCanvas.height === height) return;
                previous = frame;
                if (meshCanvas.width !== width || meshCanvas.height !== height) {
                    meshCanvas.width = skeletonCanvas.width = width;
                    meshCanvas.height = skeletonCanvas.height = height;
                }
                const [sw, sh] = description.source_size;
                const scale = Math.min(width / sw, height / sh), ox = (width - sw * scale) / 2, oy = (height - sh * scale) / 2;
                const k = description.intrinsics[frame];
                gl.viewport(0, 0, width, height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
                gl.useProgram(program); gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
                const start = frame * description.vertex_count * 3;
                gl.bufferSubData(gl.ARRAY_BUFFER, 0, vertices.subarray(start, start + description.vertex_count * 3));
                gl.uniform4f(uniforms.calibration, k[0][0], k[1][1], k[0][2], k[1][2]);
                gl.uniform2f(uniforms.resolution, sw, sh); gl.uniform2f(uniforms.fit, sw * scale / width, sh * scale / height);
                gl.drawElements(gl.TRIANGLES, faces.length, gl.UNSIGNED_INT, 0);
                ctx.clearRect(0, 0, width, height);
                const at = index => {
                    const offset = (frame * description.keypoint_count + index) * 3;
                    const z = points[offset + 2];
                    return z > 0 ? [ox + (points[offset] * k[0][0] / z + k[0][2]) * scale,
                        oy + (points[offset + 1] * k[1][1] / z + k[1][2]) * scale] : null;
                };
                ctx.lineCap = 'round';
                for (const [a, b, color, major] of description.links) {
                    const first = at(a), second = at(b);
                    if (!first || !second) continue;
                    ctx.strokeStyle = `rgb(${color.join(',')})`; ctx.lineWidth = Math.max(1, height / 520) * (major ? 1.8 : 1);
                    ctx.beginPath(); ctx.moveTo(...first); ctx.lineTo(...second); ctx.stroke();
                }
                for (const [index, color] of description.joints) {
                    const point = at(index);
                    if (!point) continue;
                    ctx.fillStyle = `rgb(${color.join(',')})`;
                    ctx.beginPath(); ctx.arc(...point, Math.max(1.3, height / 350), 0, Math.PI * 2); ctx.fill();
                }
            },
            dispose() {
                gl.deleteBuffer(vertexBuffer); gl.deleteBuffer(faceBuffer);
                gl.deleteShader(vertex); gl.deleteShader(fragment); gl.deleteProgram(program);
                gl.getExtension('WEBGL_lose_context')?.loseContext();
                meshCanvas.remove(); skeletonCanvas.remove();
            }
        };
    } catch (error) {
        gl?.getExtension('WEBGL_lose_context')?.loseContext();
        meshCanvas.remove(); skeletonCanvas.remove();
        throw error;
    }
}


export default function(frame_scheduler) {
const exports = { __proto__: null };

    let script_src;
    if (typeof document !== 'undefined' && document.currentScript !== null) {
        script_src = new URL(document.currentScript.src, location.href).toString();
    }

    class IntoUnderlyingByteSource {
        __destroy_into_raw() {
            const ptr = this.__wbg_ptr;
            this.__wbg_ptr = 0;
            IntoUnderlyingByteSourceFinalization.unregister(this);
            return ptr;
        }
        free() {
            const ptr = this.__destroy_into_raw();
            wasm.__wbg_intounderlyingbytesource_free(ptr, 0);
        }
        /**
         * @returns {number}
         */
        get autoAllocateChunkSize() {
            const ret = wasm.intounderlyingbytesource_autoAllocateChunkSize(this.__wbg_ptr);
            return ret >>> 0;
        }
        cancel() {
            const ptr = this.__destroy_into_raw();
            wasm.intounderlyingbytesource_cancel(ptr);
        }
        /**
         * @param {ReadableByteStreamController} controller
         * @returns {Promise<any>}
         */
        pull(controller) {
            const ret = wasm.intounderlyingbytesource_pull(this.__wbg_ptr, controller);
            return ret;
        }
        /**
         * @param {ReadableByteStreamController} controller
         */
        start(controller) {
            wasm.intounderlyingbytesource_start(this.__wbg_ptr, controller);
        }
        /**
         * @returns {ReadableStreamType}
         */
        get type() {
            const ret = wasm.intounderlyingbytesource_type(this.__wbg_ptr);
            return __wbindgen_enum_ReadableStreamType[ret];
        }
    }
    if (Symbol.dispose) IntoUnderlyingByteSource.prototype[Symbol.dispose] = IntoUnderlyingByteSource.prototype.free;
    exports.IntoUnderlyingByteSource = IntoUnderlyingByteSource;

    class IntoUnderlyingSink {
        __destroy_into_raw() {
            const ptr = this.__wbg_ptr;
            this.__wbg_ptr = 0;
            IntoUnderlyingSinkFinalization.unregister(this);
            return ptr;
        }
        free() {
            const ptr = this.__destroy_into_raw();
            wasm.__wbg_intounderlyingsink_free(ptr, 0);
        }
        /**
         * @param {any} reason
         * @returns {Promise<any>}
         */
        abort(reason) {
            const ptr = this.__destroy_into_raw();
            const ret = wasm.intounderlyingsink_abort(ptr, reason);
            return ret;
        }
        /**
         * @returns {Promise<any>}
         */
        close() {
            const ptr = this.__destroy_into_raw();
            const ret = wasm.intounderlyingsink_close(ptr);
            return ret;
        }
        /**
         * @param {any} chunk
         * @returns {Promise<any>}
         */
        write(chunk) {
            const ret = wasm.intounderlyingsink_write(this.__wbg_ptr, chunk);
            return ret;
        }
    }
    if (Symbol.dispose) IntoUnderlyingSink.prototype[Symbol.dispose] = IntoUnderlyingSink.prototype.free;
    exports.IntoUnderlyingSink = IntoUnderlyingSink;

    class IntoUnderlyingSource {
        __destroy_into_raw() {
            const ptr = this.__wbg_ptr;
            this.__wbg_ptr = 0;
            IntoUnderlyingSourceFinalization.unregister(this);
            return ptr;
        }
        free() {
            const ptr = this.__destroy_into_raw();
            wasm.__wbg_intounderlyingsource_free(ptr, 0);
        }
        cancel() {
            const ptr = this.__destroy_into_raw();
            wasm.intounderlyingsource_cancel(ptr);
        }
        /**
         * @param {ReadableStreamDefaultController} controller
         * @returns {Promise<any>}
         */
        pull(controller) {
            const ret = wasm.intounderlyingsource_pull(this.__wbg_ptr, controller);
            return ret;
        }
    }
    if (Symbol.dispose) IntoUnderlyingSource.prototype[Symbol.dispose] = IntoUnderlyingSource.prototype.free;
    exports.IntoUnderlyingSource = IntoUnderlyingSource;

    class WebHandle {
        __destroy_into_raw() {
            const ptr = this.__wbg_ptr;
            this.__wbg_ptr = 0;
            WebHandleFinalization.unregister(this);
            return ptr;
        }
        free() {
            const ptr = this.__destroy_into_raw();
            wasm.__wbg_webhandle_free(ptr, 0);
        }
        /**
         * Add a new receiver streaming data from the given url.
         *
         * Websocket streams are always opened in `Following` mode.
         *
         * It is an error to open a channel twice with the same id.
         * @param {string} url
         */
        add_receiver(url) {
            const ptr0 = passStringToWasm0(url, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            wasm.webhandle_add_receiver(this.__wbg_ptr, ptr0, len0);
        }
        /**
         * Close an existing channel for streaming data.
         *
         * No-op if the channel is already closed.
         * @param {string} id
         */
        close_channel(id) {
            const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            wasm.webhandle_close_channel(this.__wbg_ptr, ptr0, len0);
        }
        destroy() {
            wasm.webhandle_destroy(this.__wbg_ptr);
        }
        /**
         * @returns {string | undefined}
         */
        get_active_recording_id() {
            const ret = wasm.webhandle_get_active_recording_id(this.__wbg_ptr);
            let v1;
            if (ret[0] !== 0) {
                v1 = getStringFromWasm0(ret[0], ret[1]).slice();
                wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
            }
            return v1;
        }
        /**
         * @param {string} recording_id
         * @returns {string | undefined}
         */
        get_active_timeline(recording_id) {
            const ptr0 = passStringToWasm0(recording_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.webhandle_get_active_timeline(this.__wbg_ptr, ptr0, len0);
            let v2;
            if (ret[0] !== 0) {
                v2 = getStringFromWasm0(ret[0], ret[1]).slice();
                wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
            }
            return v2;
        }
        /**
         * @param {string} recording_id
         * @returns {boolean | undefined}
         */
        get_playing(recording_id) {
            const ptr0 = passStringToWasm0(recording_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.webhandle_get_playing(this.__wbg_ptr, ptr0, len0);
            return ret === 0xFFFFFF ? undefined : ret !== 0;
        }
        /**
         * @param {string} recording_id
         * @param {string} timeline_name
         * @returns {number | undefined}
         */
        get_time_for_timeline(recording_id, timeline_name) {
            const ptr0 = passStringToWasm0(recording_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ptr1 = passStringToWasm0(timeline_name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            const ret = wasm.webhandle_get_time_for_timeline(this.__wbg_ptr, ptr0, len0, ptr1, len1);
            return ret[0] === 0 ? undefined : ret[1];
        }
        /**
         * @param {string} recording_id
         * @param {string} timeline_name
         * @returns {any}
         */
        get_timeline_time_range(recording_id, timeline_name) {
            const ptr0 = passStringToWasm0(recording_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ptr1 = passStringToWasm0(timeline_name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            const ret = wasm.webhandle_get_timeline_time_range(this.__wbg_ptr, ptr0, len0, ptr1, len1);
            return ret;
        }
        /**
         * @returns {boolean}
         */
        has_panicked() {
            const ret = wasm.webhandle_has_panicked(this.__wbg_ptr);
            return ret !== 0;
        }
        /**
         * Handle an encoded `egui_inspection` request.
         * @param {Uint8Array} request_bytes
         * @returns {Promise<Uint8Array>}
         */
        inspect(request_bytes) {
            const ptr0 = passArray8ToWasm0(request_bytes, wasm.__wbindgen_malloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.webhandle_inspect(this.__wbg_ptr, ptr0, len0);
            return ret;
        }
        /**
         * @param {any} app_options
         */
        constructor(app_options) {
            const ret = wasm.webhandle_new(app_options);
            if (ret[2]) {
                throw takeFromExternrefTable0(ret[1]);
            }
            this.__wbg_ptr = ret[0];
            WebHandleFinalization.register(this, this.__wbg_ptr, this);
            return this;
        }
        /**
         * Open a new channel for streaming data.
         *
         * It is an error to open a channel twice with the same id.
         * @param {string} id
         * @param {string} channel_name
         */
        open_channel(id, channel_name) {
            const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ptr1 = passStringToWasm0(channel_name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            wasm.webhandle_open_channel(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        }
        /**
         * @param {string} panel
         * @param {string | null} [state]
         */
        override_panel_state(panel, state) {
            const ptr0 = passStringToWasm0(panel, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            var ptr1 = isLikeNone(state) ? 0 : passStringToWasm0(state, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            var len1 = WASM_VECTOR_LEN;
            const ret = wasm.webhandle_override_panel_state(this.__wbg_ptr, ptr0, len0, ptr1, len1);
            if (ret[1]) {
                throw takeFromExternrefTable0(ret[0]);
            }
        }
        /**
         * @returns {string | undefined}
         */
        panic_callstack() {
            const ret = wasm.webhandle_panic_callstack(this.__wbg_ptr);
            let v1;
            if (ret[0] !== 0) {
                v1 = getStringFromWasm0(ret[0], ret[1]).slice();
                wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
            }
            return v1;
        }
        /**
         * @returns {string | undefined}
         */
        panic_message() {
            const ret = wasm.webhandle_panic_message(this.__wbg_ptr);
            let v1;
            if (ret[0] !== 0) {
                v1 = getStringFromWasm0(ret[0], ret[1]).slice();
                wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
            }
            return v1;
        }
        /**
         * @param {string} url
         */
        remove_receiver(url) {
            const ptr0 = passStringToWasm0(url, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            wasm.webhandle_remove_receiver(this.__wbg_ptr, ptr0, len0);
        }
        /**
         * Encode the active blueprint as RRD data.
         * @returns {Uint8Array}
         */
        save_blueprint() {
            const ret = wasm.webhandle_save_blueprint(this.__wbg_ptr);
            if (ret[3]) {
                throw takeFromExternrefTable0(ret[2]);
            }
            var v1 = getArrayU8FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
            return v1;
        }
        /**
         * Encode the active recording as RRD data.
         * @returns {Uint8Array}
         */
        save_recording() {
            const ret = wasm.webhandle_save_recording(this.__wbg_ptr);
            if (ret[3]) {
                throw takeFromExternrefTable0(ret[2]);
            }
            var v1 = getArrayU8FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
            return v1;
        }
        /**
         * Add an rrd to the viewer directly from a byte array.
         * @param {string} id
         * @param {Uint8Array} data
         */
        send_rrd_to_channel(id, data) {
            const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ptr1 = passArray8ToWasm0(data, wasm.__wbindgen_malloc);
            const len1 = WASM_VECTOR_LEN;
            wasm.webhandle_send_rrd_to_channel(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        }
        /**
         * @param {string} id
         * @param {Uint8Array} data
         */
        send_table_to_channel(id, data) {
            const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ptr1 = passArray8ToWasm0(data, wasm.__wbindgen_malloc);
            const len1 = WASM_VECTOR_LEN;
            wasm.webhandle_send_table_to_channel(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        }
        /**
         * @param {string} recording_id
         */
        set_active_recording_id(recording_id) {
            const ptr0 = passStringToWasm0(recording_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            wasm.webhandle_set_active_recording_id(this.__wbg_ptr, ptr0, len0);
        }
        /**
         * Set the active timeline.
         *
         * This does nothing if the timeline can't be found.
         * @param {string} recording_id
         * @param {string} timeline_name
         */
        set_active_timeline(recording_id, timeline_name) {
            const ptr0 = passStringToWasm0(recording_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ptr1 = passStringToWasm0(timeline_name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            wasm.webhandle_set_active_timeline(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        }
        /**
         * @param {string} access_token
         * @param {string} email
         */
        set_credentials(access_token, email) {
            const ptr0 = passStringToWasm0(access_token, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ptr1 = passStringToWasm0(email, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            wasm.webhandle_set_credentials(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        }
        /**
         * @param {string} recording_id
         * @param {boolean} value
         */
        set_playing(recording_id, value) {
            const ptr0 = passStringToWasm0(recording_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            wasm.webhandle_set_playing(this.__wbg_ptr, ptr0, len0, value);
        }
        /**
         * @param {string} recording_id
         * @param {string} timeline_name
         * @param {number} time
         */
        set_time_for_timeline(recording_id, timeline_name, time) {
            const ptr0 = passStringToWasm0(recording_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ptr1 = passStringToWasm0(timeline_name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            wasm.webhandle_set_time_for_timeline(this.__wbg_ptr, ptr0, len0, ptr1, len1, time);
        }
        /**
         * @param {any} canvas
         * @returns {Promise<void>}
         */
        start(canvas) {
            const ret = wasm.webhandle_start(this.__wbg_ptr, canvas);
            return ret;
        }
        /**
         * @param {boolean | null} [value]
         */
        toggle_panel_overrides(value) {
            wasm.webhandle_toggle_panel_overrides(this.__wbg_ptr, isLikeNone(value) ? 0xFFFFFF : value ? 1 : 0);
        }
    }
    if (Symbol.dispose) WebHandle.prototype[Symbol.dispose] = WebHandle.prototype.free;
    exports.WebHandle = WebHandle;
    function __wbg_get_imports() {
        const import0 = {
            __proto__: null,
            __wbg_Error_92b29b0548f8b746: function(arg0, arg1) {
                const ret = Error(getStringFromWasm0(arg0, arg1));
                return ret;
            },
            __wbg_Number_9a4e0ecb0fa16705: function(arg0) {
                const ret = Number(arg0);
                return ret;
            },
            __wbg_Window_afcc911b2f9c92e2: function(arg0) {
                const ret = arg0.Window;
                return ret;
            },
            __wbg_WorkerGlobalScope_5d19ebc889ff397e: function(arg0) {
                const ret = arg0.WorkerGlobalScope;
                return ret;
            },
            __wbg___wbindgen_boolean_get_fa956cfa2d1bd751: function(arg0) {
                const v = arg0;
                const ret = typeof(v) === 'boolean' ? v : undefined;
                return isLikeNone(ret) ? 0xFFFFFF : ret ? 1 : 0;
            },
            __wbg___wbindgen_debug_string_c25d447a39f5578f: function(arg0, arg1) {
                const ret = debugString(arg1);
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg___wbindgen_in_aca499c5de7ff5e5: function(arg0, arg1) {
                const ret = arg0 in arg1;
                return ret;
            },
            __wbg___wbindgen_is_falsy_a6dfe792ff282f10: function(arg0) {
                const ret = !arg0;
                return ret;
            },
            __wbg___wbindgen_is_function_1ff95bcc5517c252: function(arg0) {
                const ret = typeof(arg0) === 'function';
                return ret;
            },
            __wbg___wbindgen_is_null_ea9085d691f535d3: function(arg0) {
                const ret = arg0 === null;
                return ret;
            },
            __wbg___wbindgen_is_object_a27215656b807791: function(arg0) {
                const val = arg0;
                const ret = typeof(val) === 'object' && val !== null;
                return ret;
            },
            __wbg___wbindgen_is_string_ea5e6cc2e4141dfe: function(arg0) {
                const ret = typeof(arg0) === 'string';
                return ret;
            },
            __wbg___wbindgen_is_undefined_c05833b95a3cf397: function(arg0) {
                const ret = arg0 === undefined;
                return ret;
            },
            __wbg___wbindgen_jsval_loose_eq_db4c3b15f63fc170: function(arg0, arg1) {
                const ret = arg0 == arg1;
                return ret;
            },
            __wbg___wbindgen_number_get_394265ed1e1b84ee: function(arg0, arg1) {
                const obj = arg1;
                const ret = typeof(obj) === 'number' ? obj : undefined;
                getDataViewMemory0().setFloat64(arg0 + 8 * 1, isLikeNone(ret) ? 0 : ret, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, !isLikeNone(ret), true);
            },
            __wbg___wbindgen_string_get_b0ca35b86a603356: function(arg0, arg1) {
                const obj = arg1;
                const ret = typeof(obj) === 'string' ? obj : undefined;
                var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                var len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg___wbindgen_throw_344f42d3211c4765: function(arg0, arg1) {
                throw new Error(getStringFromWasm0(arg0, arg1));
            },
            __wbg__wbg_cb_unref_fffb441def202758: function(arg0) {
                arg0._wbg_cb_unref();
            },
            __wbg_abort_807c9d22f53767f5: function(arg0) {
                const ret = arg0.abort();
                return ret;
            },
            __wbg_abort_8bae0f33e7833997: function(arg0) {
                arg0.abort();
            },
            __wbg_abort_eee9248a6d680839: function(arg0, arg1) {
                arg0.abort(arg1);
            },
            __wbg_activeElement_4bc99dc1a7094c27: function(arg0) {
                const ret = arg0.activeElement;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_activeElement_b85d218c5f49326e: function(arg0) {
                const ret = arg0.activeElement;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_activeTexture_92b04d918019d603: function(arg0, arg1) {
                arg0.activeTexture(arg1 >>> 0);
            },
            __wbg_activeTexture_d12958674e97a118: function(arg0, arg1) {
                arg0.activeTexture(arg1 >>> 0);
            },
            __wbg_addEventListener_520e749bbae24529: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
                arg0.addEventListener(getStringFromWasm0(arg1, arg2), arg3, arg4);
            }, arguments); },
            __wbg_addEventListener_d85450ee1320c989: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                arg0.addEventListener(getStringFromWasm0(arg1, arg2), arg3);
            }, arguments); },
            __wbg_altKey_50f830d1793a2eea: function(arg0) {
                const ret = arg0.altKey;
                return ret;
            },
            __wbg_altKey_f3e24c4c9cfcf271: function(arg0) {
                const ret = arg0.altKey;
                return ret;
            },
            __wbg_appendChild_f553e8704c4f14a6: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.appendChild(arg1);
                return ret;
            }, arguments); },
            __wbg_append_01c74e5c6b58aa64: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
                arg0.append(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
            }, arguments); },
            __wbg_append_1e60bd927c609246: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.append(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
            },
            __wbg_arrayBuffer_3b637f0fa65c5351: function() { return handleError(function (arg0) {
                const ret = arg0.arrayBuffer();
                return ret;
            }, arguments); },
            __wbg_arrayBuffer_a158e423a87ee756: function(arg0) {
                const ret = arg0.arrayBuffer();
                return ret;
            },
            __wbg_assign_7e262bdaf75bb707: function() { return handleError(function (arg0, arg1, arg2) {
                arg0.assign(getStringFromWasm0(arg1, arg2));
            }, arguments); },
            __wbg_at_031a0b72e465b17e: function(arg0, arg1) {
                const ret = arg0.at(arg1);
                return ret;
            },
            __wbg_attachShader_5f7f4077e124e23b: function(arg0, arg1, arg2) {
                arg0.attachShader(arg1, arg2);
            },
            __wbg_attachShader_8971266b4c9bc514: function(arg0, arg1, arg2) {
                arg0.attachShader(arg1, arg2);
            },
            __wbg_back_939cbdbdfad8aff7: function() { return handleError(function (arg0) {
                arg0.back();
            }, arguments); },
            __wbg_beginQuery_042a1f99e870066c: function(arg0, arg1, arg2) {
                arg0.beginQuery(arg1 >>> 0, arg2);
            },
            __wbg_beginRenderPass_aa22c432e793359a: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.beginRenderPass(arg1);
                return ret;
            }, arguments); },
            __wbg_bindAttribLocation_0fe5da7e01ac0d15: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.bindAttribLocation(arg1, arg2 >>> 0, getStringFromWasm0(arg3, arg4));
            },
            __wbg_bindAttribLocation_94202d7a59ab7863: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.bindAttribLocation(arg1, arg2 >>> 0, getStringFromWasm0(arg3, arg4));
            },
            __wbg_bindBufferRange_f5c29912db0476e9: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.bindBufferRange(arg1 >>> 0, arg2 >>> 0, arg3, arg4, arg5);
            },
            __wbg_bindBuffer_1e00cfb4321ef9a4: function(arg0, arg1, arg2) {
                arg0.bindBuffer(arg1 >>> 0, arg2);
            },
            __wbg_bindBuffer_a01497b1abdcdd9a: function(arg0, arg1, arg2) {
                arg0.bindBuffer(arg1 >>> 0, arg2);
            },
            __wbg_bindFramebuffer_390311eff3896937: function(arg0, arg1, arg2) {
                arg0.bindFramebuffer(arg1 >>> 0, arg2);
            },
            __wbg_bindFramebuffer_658e4b06f7ee8bb4: function(arg0, arg1, arg2) {
                arg0.bindFramebuffer(arg1 >>> 0, arg2);
            },
            __wbg_bindRenderbuffer_75e8469e930840fa: function(arg0, arg1, arg2) {
                arg0.bindRenderbuffer(arg1 >>> 0, arg2);
            },
            __wbg_bindRenderbuffer_c3d0c4b8cd1c3891: function(arg0, arg1, arg2) {
                arg0.bindRenderbuffer(arg1 >>> 0, arg2);
            },
            __wbg_bindSampler_ce608f0de9d31acf: function(arg0, arg1, arg2) {
                arg0.bindSampler(arg1 >>> 0, arg2);
            },
            __wbg_bindTexture_28eff4bbd8aaab54: function(arg0, arg1, arg2) {
                arg0.bindTexture(arg1 >>> 0, arg2);
            },
            __wbg_bindTexture_9b04b1b7c00d4dd6: function(arg0, arg1, arg2) {
                arg0.bindTexture(arg1 >>> 0, arg2);
            },
            __wbg_bindVertexArrayOES_5cad2205a17e8990: function(arg0, arg1) {
                arg0.bindVertexArrayOES(arg1);
            },
            __wbg_bindVertexArray_427eeac0c1764d8a: function(arg0, arg1) {
                arg0.bindVertexArray(arg1);
            },
            __wbg_blendColor_793b560dc69ddd0b: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.blendColor(arg1, arg2, arg3, arg4);
            },
            __wbg_blendColor_eae0cd578a2c7d15: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.blendColor(arg1, arg2, arg3, arg4);
            },
            __wbg_blendEquationSeparate_043e2f50f6ecb2d3: function(arg0, arg1, arg2) {
                arg0.blendEquationSeparate(arg1 >>> 0, arg2 >>> 0);
            },
            __wbg_blendEquationSeparate_c7e2b2261c94e1c5: function(arg0, arg1, arg2) {
                arg0.blendEquationSeparate(arg1 >>> 0, arg2 >>> 0);
            },
            __wbg_blendEquation_455b8986ededabc0: function(arg0, arg1) {
                arg0.blendEquation(arg1 >>> 0);
            },
            __wbg_blendEquation_f5c5272993f6cb01: function(arg0, arg1) {
                arg0.blendEquation(arg1 >>> 0);
            },
            __wbg_blendFuncSeparate_37156309688f8f88: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.blendFuncSeparate(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4 >>> 0);
            },
            __wbg_blendFuncSeparate_3ee6d939a9f3938b: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.blendFuncSeparate(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4 >>> 0);
            },
            __wbg_blendFunc_114dc7056ccfeb8d: function(arg0, arg1, arg2) {
                arg0.blendFunc(arg1 >>> 0, arg2 >>> 0);
            },
            __wbg_blendFunc_a854d7e4459150ba: function(arg0, arg1, arg2) {
                arg0.blendFunc(arg1 >>> 0, arg2 >>> 0);
            },
            __wbg_blitFramebuffer_a1215976f663b058: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10) {
                arg0.blitFramebuffer(arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0);
            },
            __wbg_blockSize_5af477b962b2b031: function(arg0) {
                const ret = arg0.blockSize;
                return ret;
            },
            __wbg_blur_e902dcc79406e89c: function() { return handleError(function (arg0) {
                arg0.blur();
            }, arguments); },
            __wbg_body_18c9f2ac15ead4b2: function(arg0) {
                const ret = arg0.body;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_body_40ec34e0a2931fe8: function(arg0) {
                const ret = arg0.body;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_bottom_e6ed49b80d965dae: function(arg0) {
                const ret = arg0.bottom;
                return ret;
            },
            __wbg_bufferData_073a7c6abef7a55f: function(arg0, arg1, arg2, arg3) {
                arg0.bufferData(arg1 >>> 0, arg2, arg3 >>> 0);
            },
            __wbg_bufferData_3d4f29bdfb1fa46c: function(arg0, arg1, arg2, arg3) {
                arg0.bufferData(arg1 >>> 0, arg2, arg3 >>> 0);
            },
            __wbg_bufferData_90ef588bac2be2f5: function(arg0, arg1, arg2, arg3) {
                arg0.bufferData(arg1 >>> 0, arg2, arg3 >>> 0);
            },
            __wbg_bufferData_ce4f44d56e9ddab5: function(arg0, arg1, arg2, arg3) {
                arg0.bufferData(arg1 >>> 0, arg2, arg3 >>> 0);
            },
            __wbg_bufferSubData_bae930b21e9c1c48: function(arg0, arg1, arg2, arg3) {
                arg0.bufferSubData(arg1 >>> 0, arg2, arg3);
            },
            __wbg_bufferSubData_ce9854d3d337e2cf: function(arg0, arg1, arg2, arg3) {
                arg0.bufferSubData(arg1 >>> 0, arg2, arg3);
            },
            __wbg_buffer_54b87055582c8a81: function(arg0) {
                const ret = arg0.buffer;
                return ret;
            },
            __wbg_button_f6a9a7b725f1838e: function(arg0) {
                const ret = arg0.button;
                return ret;
            },
            __wbg_byobRequest_06b654bb15590436: function(arg0) {
                const ret = arg0.byobRequest;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_byteLength_41862ca4020b9c43: function(arg0) {
                const ret = arg0.byteLength;
                return ret;
            },
            __wbg_byteOffset_d42e18c4441f628b: function(arg0) {
                const ret = arg0.byteOffset;
                return ret;
            },
            __wbg_call_8a2dd23819f8a60a: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.call(arg1);
                return ret;
            }, arguments); },
            __wbg_call_a6e5c5dce5018821: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.call(arg1, arg2);
                return ret;
            }, arguments); },
            __wbg_cancelAnimationFrame_086d6084925c4e06: function() { return handleError(function (arg0, arg1) {
                frame_scheduler.cancel(arg1);
            }, arguments); },
            __wbg_cancel_3983a93e24cc66b3: function(arg0) {
                const ret = arg0.cancel();
                return ret;
            },
            __wbg_catch_c1a60df4c30d76d3: function(arg0, arg1) {
                const ret = arg0.catch(arg1);
                return ret;
            },
            __wbg_changedTouches_dbf6eeabddd3c2da: function(arg0) {
                const ret = arg0.changedTouches;
                return ret;
            },
            __wbg_clearBufferfv_2e0f1a0ea56de859: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.clearBufferfv(arg1 >>> 0, arg2, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_clearBufferiv_0360269bf6e34c54: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.clearBufferiv(arg1 >>> 0, arg2, getArrayI32FromWasm0(arg3, arg4));
            },
            __wbg_clearBufferuiv_df94a395d4915377: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.clearBufferuiv(arg1 >>> 0, arg2, getArrayU32FromWasm0(arg3, arg4));
            },
            __wbg_clearDepth_8b5d226aae155082: function(arg0, arg1) {
                arg0.clearDepth(arg1);
            },
            __wbg_clearDepth_ca9b22d41551b513: function(arg0, arg1) {
                arg0.clearDepth(arg1);
            },
            __wbg_clearInterval_2e2069e95ad09d4f: function(arg0, arg1) {
                arg0.clearInterval(arg1);
            },
            __wbg_clearStencil_58f2af46612bccae: function(arg0, arg1) {
                arg0.clearStencil(arg1);
            },
            __wbg_clearStencil_a66fe23df6313fc7: function(arg0, arg1) {
                arg0.clearStencil(arg1);
            },
            __wbg_clearTimeout_6b8d9a38b9263d65: function(arg0) {
                const ret = clearTimeout(arg0);
                return ret;
            },
            __wbg_clearTimeout_8f80437be2324e09: function(arg0, arg1) {
                arg0.clearTimeout(arg1);
            },
            __wbg_clearTimeout_ef38e23d3d8f7baf: function(arg0) {
                const ret = clearTimeout(arg0);
                return ret;
            },
            __wbg_clear_53d71d234e14e4c1: function(arg0, arg1) {
                arg0.clear(arg1 >>> 0);
            },
            __wbg_clear_dd06a0da4ce8e13f: function(arg0, arg1) {
                arg0.clear(arg1 >>> 0);
            },
            __wbg_click_22281da934e153f5: function(arg0) {
                arg0.click();
            },
            __wbg_clientWaitSync_cf8e49f8ba228377: function(arg0, arg1, arg2, arg3) {
                const ret = arg0.clientWaitSync(arg1, arg2 >>> 0, arg3 >>> 0);
                return ret;
            },
            __wbg_clientX_c396b0fb11d601d3: function(arg0) {
                const ret = arg0.clientX;
                return ret;
            },
            __wbg_clientX_e8c6c674634344de: function(arg0) {
                const ret = arg0.clientX;
                return ret;
            },
            __wbg_clientY_a4650836fdf58f01: function(arg0) {
                const ret = arg0.clientY;
                return ret;
            },
            __wbg_clientY_ffea953797502d5d: function(arg0) {
                const ret = arg0.clientY;
                return ret;
            },
            __wbg_clipboardData_b99e24e2d915217c: function(arg0) {
                const ret = arg0.clipboardData;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_clipboard_cc7335fcba1a9a80: function(arg0) {
                const ret = arg0.clipboard;
                return ret;
            },
            __wbg_close_1f3dc5faf2043944: function() { return handleError(function (arg0) {
                arg0.close();
            }, arguments); },
            __wbg_close_249a23304523681b: function() { return handleError(function (arg0) {
                arg0.close();
            }, arguments); },
            __wbg_close_72d318d9c16e83ef: function() { return handleError(function (arg0) {
                arg0.close();
            }, arguments); },
            __wbg_close_90cc288ec0e6eb50: function() { return handleError(function (arg0) {
                arg0.close();
            }, arguments); },
            __wbg_close_adb3a7073894d04e: function(arg0) {
                arg0.close();
            },
            __wbg_closed_a9e0ba86bfa233c0: function() { return handleError(function (arg0) {
                const ret = arg0.closed;
                return ret;
            }, arguments); },
            __wbg_code_89c999e407c79eef: function(arg0, arg1) {
                const ret = arg1.code;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_code_cb4327cfc515673b: function(arg0) {
                const ret = arg0.code;
                return ret;
            },
            __wbg_colorMask_44ebb91cad2502f2: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.colorMask(arg1 !== 0, arg2 !== 0, arg3 !== 0, arg4 !== 0);
            },
            __wbg_colorMask_a4d164c2039b5731: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.colorMask(arg1 !== 0, arg2 !== 0, arg3 !== 0, arg4 !== 0);
            },
            __wbg_compileShader_9bdfd792722cf704: function(arg0, arg1) {
                arg0.compileShader(arg1);
            },
            __wbg_compileShader_fc2e4b73240d4fd7: function(arg0, arg1) {
                arg0.compileShader(arg1);
            },
            __wbg_compressedTexSubImage2D_c1362291573c7268: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.compressedTexSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8, arg9);
            },
            __wbg_compressedTexSubImage2D_da01674d2975d1ae: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8) {
                arg0.compressedTexSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8);
            },
            __wbg_compressedTexSubImage2D_dd6dc580749eb5cf: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8) {
                arg0.compressedTexSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8);
            },
            __wbg_compressedTexSubImage3D_04cb8b046c4321fe: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.compressedTexSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10, arg11);
            },
            __wbg_compressedTexSubImage3D_af0228a80ffd5993: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10) {
                arg0.compressedTexSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10);
            },
            __wbg_configure_0e4789c0f6b35c8e: function() { return handleError(function (arg0, arg1) {
                arg0.configure(arg1);
            }, arguments); },
            __wbg_configure_84a31356970a404e: function() { return handleError(function (arg0, arg1) {
                arg0.configure(arg1);
            }, arguments); },
            __wbg_contentBoxSize_74fbbc51859ff90e: function(arg0) {
                const ret = arg0.contentBoxSize;
                return ret;
            },
            __wbg_contentRect_1d6e15e2e0d3e3c3: function(arg0) {
                const ret = arg0.contentRect;
                return ret;
            },
            __wbg_copyBufferSubData_cdf61f74aa6e0902: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.copyBufferSubData(arg1 >>> 0, arg2 >>> 0, arg3, arg4, arg5);
            },
            __wbg_copyBufferToBuffer_5e2cd8f10ae78183: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
                arg0.copyBufferToBuffer(arg1, arg2, arg3, arg4);
            }, arguments); },
            __wbg_copyBufferToBuffer_ca30deb8de65f5d5: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.copyBufferToBuffer(arg1, arg2, arg3, arg4, arg5);
            }, arguments); },
            __wbg_copyBufferToTexture_29b9d26780296819: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                arg0.copyBufferToTexture(arg1, arg2, arg3);
            }, arguments); },
            __wbg_copyExternalImageToTexture_4df105bb39517948: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                arg0.copyExternalImageToTexture(arg1, arg2, arg3);
            }, arguments); },
            __wbg_copyTexSubImage2D_8daea651fc408645: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8) {
                arg0.copyTexSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8);
            },
            __wbg_copyTexSubImage2D_c73f91f1d7022402: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8) {
                arg0.copyTexSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8);
            },
            __wbg_copyTexSubImage3D_bfe7a14dac9ad777: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.copyTexSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9);
            },
            __wbg_copyTextureToBuffer_ed6e67a77ecb768d: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                arg0.copyTextureToBuffer(arg1, arg2, arg3);
            }, arguments); },
            __wbg_createBindGroupLayout_49a7e2b3d076afcf: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.createBindGroupLayout(arg1);
                return ret;
            }, arguments); },
            __wbg_createBindGroup_655c6e6c0258530e: function(arg0, arg1) {
                const ret = arg0.createBindGroup(arg1);
                return ret;
            },
            __wbg_createBuffer_01568a9d930d90dd: function(arg0) {
                const ret = arg0.createBuffer();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createBuffer_0726dd2ab09ea1d2: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.createBuffer(arg1);
                return ret;
            }, arguments); },
            __wbg_createBuffer_2075765bde5035d5: function(arg0) {
                const ret = arg0.createBuffer();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createCommandEncoder_ec1f40f0cb4d09df: function(arg0, arg1) {
                const ret = arg0.createCommandEncoder(arg1);
                return ret;
            },
            __wbg_createElement_fcbc0805de826d62: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.createElement(getStringFromWasm0(arg1, arg2));
                return ret;
            }, arguments); },
            __wbg_createFramebuffer_b24d2c80a8b9e7cc: function(arg0) {
                const ret = arg0.createFramebuffer();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createFramebuffer_de0d521f546e7534: function(arg0) {
                const ret = arg0.createFramebuffer();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createImageBitmap_5dbcdc6d11d377bd: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.createImageBitmap(arg1);
                return ret;
            }, arguments); },
            __wbg_createObjectURL_416e527781e6fd6d: function() { return handleError(function (arg0, arg1) {
                const ret = URL.createObjectURL(arg1);
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_createPipelineLayout_2c8cd4528b06c108: function(arg0, arg1) {
                const ret = arg0.createPipelineLayout(arg1);
                return ret;
            },
            __wbg_createProgram_118becaac3a20318: function(arg0) {
                const ret = arg0.createProgram();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createProgram_538c9777a4ac084f: function(arg0) {
                const ret = arg0.createProgram();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createQuery_047c7c524e4ac4f8: function(arg0) {
                const ret = arg0.createQuery();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createRenderPipeline_cf98d4d699bfb03c: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.createRenderPipeline(arg1);
                return ret;
            }, arguments); },
            __wbg_createRenderbuffer_71af5c0d615e9271: function(arg0) {
                const ret = arg0.createRenderbuffer();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createRenderbuffer_9d801bf44c314f44: function(arg0) {
                const ret = arg0.createRenderbuffer();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createSampler_70c8392d98896235: function(arg0) {
                const ret = arg0.createSampler();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createSampler_c8ffb3c8d565f704: function(arg0, arg1) {
                const ret = arg0.createSampler(arg1);
                return ret;
            },
            __wbg_createShaderModule_2e44fc7677c6288b: function(arg0, arg1) {
                const ret = arg0.createShaderModule(arg1);
                return ret;
            },
            __wbg_createShader_78bc8b7e9a88e1a8: function(arg0, arg1) {
                const ret = arg0.createShader(arg1 >>> 0);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createShader_7d139f2d50f77365: function(arg0, arg1) {
                const ret = arg0.createShader(arg1 >>> 0);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createTexture_0ee0fa5f924f3d14: function(arg0) {
                const ret = arg0.createTexture();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createTexture_1bac74c999b8a48e: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.createTexture(arg1);
                return ret;
            }, arguments); },
            __wbg_createTexture_d13f98e0d3d912f4: function(arg0) {
                const ret = arg0.createTexture();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createVertexArrayOES_2fa3e59eebd5f674: function(arg0) {
                const ret = arg0.createVertexArrayOES();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createVertexArray_baf9eef7ea5a2c7a: function(arg0) {
                const ret = arg0.createVertexArray();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_createView_ceaf2f5881adbd34: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.createView(arg1);
                return ret;
            }, arguments); },
            __wbg_createWritable_659288d5245034d3: function(arg0) {
                const ret = arg0.createWritable();
                return ret;
            },
            __wbg_ctrlKey_2e52816fa7160097: function(arg0) {
                const ret = arg0.ctrlKey;
                return ret;
            },
            __wbg_ctrlKey_50bd8324959ca786: function(arg0) {
                const ret = arg0.ctrlKey;
                return ret;
            },
            __wbg_cullFace_62bbea3bef0e6b99: function(arg0, arg1) {
                arg0.cullFace(arg1 >>> 0);
            },
            __wbg_cullFace_f1c75ae19b07eaf3: function(arg0, arg1) {
                arg0.cullFace(arg1 >>> 0);
            },
            __wbg_dataTransfer_c1c4745cee7e05f1: function(arg0) {
                const ret = arg0.dataTransfer;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_data_328de4280640da92: function(arg0) {
                const ret = arg0.data;
                return ret;
            },
            __wbg_debug_87fd9b1a625b7efb: function(arg0) {
                console.debug(arg0);
            },
            __wbg_debug_cf53e2612c84e4ee: function(arg0, arg1, arg2, arg3) {
                console.debug(arg0, arg1, arg2, arg3);
            },
            __wbg_decode_02f9ccfc83b87859: function() { return handleError(function (arg0, arg1) {
                arg0.decode(arg1);
            }, arguments); },
            __wbg_deleteBuffer_08eb938e35c27967: function(arg0, arg1) {
                arg0.deleteBuffer(arg1);
            },
            __wbg_deleteBuffer_1ca3ffe668a488e7: function(arg0, arg1) {
                arg0.deleteBuffer(arg1);
            },
            __wbg_deleteFramebuffer_963cd69957209d37: function(arg0, arg1) {
                arg0.deleteFramebuffer(arg1);
            },
            __wbg_deleteFramebuffer_d1a36e889b009344: function(arg0, arg1) {
                arg0.deleteFramebuffer(arg1);
            },
            __wbg_deleteProgram_09bd45a51105b2f6: function(arg0, arg1) {
                arg0.deleteProgram(arg1);
            },
            __wbg_deleteProgram_132e191baa9fa84f: function(arg0, arg1) {
                arg0.deleteProgram(arg1);
            },
            __wbg_deleteQuery_0d1dcc4402a86ee1: function(arg0, arg1) {
                arg0.deleteQuery(arg1);
            },
            __wbg_deleteRenderbuffer_52bdbf5ab2cbe62a: function(arg0, arg1) {
                arg0.deleteRenderbuffer(arg1);
            },
            __wbg_deleteRenderbuffer_ca999f7883b777af: function(arg0, arg1) {
                arg0.deleteRenderbuffer(arg1);
            },
            __wbg_deleteSampler_0abb528566c4ab3b: function(arg0, arg1) {
                arg0.deleteSampler(arg1);
            },
            __wbg_deleteShader_3120790d36063afe: function(arg0, arg1) {
                arg0.deleteShader(arg1);
            },
            __wbg_deleteShader_993edb4beb3c4d53: function(arg0, arg1) {
                arg0.deleteShader(arg1);
            },
            __wbg_deleteSync_9b0e43580942a0f6: function(arg0, arg1) {
                arg0.deleteSync(arg1);
            },
            __wbg_deleteTexture_2b163b157ea1be24: function(arg0, arg1) {
                arg0.deleteTexture(arg1);
            },
            __wbg_deleteTexture_bdc2202d7a50dcea: function(arg0, arg1) {
                arg0.deleteTexture(arg1);
            },
            __wbg_deleteVertexArrayOES_7fa59c32cfdfa6fa: function(arg0, arg1) {
                arg0.deleteVertexArrayOES(arg1);
            },
            __wbg_deleteVertexArray_475d4e969aac1dd0: function(arg0, arg1) {
                arg0.deleteVertexArray(arg1);
            },
            __wbg_delete_50c5af3bd629e1bf: function() { return handleError(function (arg0, arg1, arg2) {
                delete arg0[getStringFromWasm0(arg1, arg2)];
            }, arguments); },
            __wbg_deltaMode_d869228efd74f393: function(arg0) {
                const ret = arg0.deltaMode;
                return ret;
            },
            __wbg_deltaX_5d829ffba565ed10: function(arg0) {
                const ret = arg0.deltaX;
                return ret;
            },
            __wbg_deltaY_6cfce8f8da250c23: function(arg0) {
                const ret = arg0.deltaY;
                return ret;
            },
            __wbg_depthFunc_455cfeb8a9d2fb4c: function(arg0, arg1) {
                arg0.depthFunc(arg1 >>> 0);
            },
            __wbg_depthFunc_74a8f8acf8973c86: function(arg0, arg1) {
                arg0.depthFunc(arg1 >>> 0);
            },
            __wbg_depthMask_4bd6c73b1339d257: function(arg0, arg1) {
                arg0.depthMask(arg1 !== 0);
            },
            __wbg_depthMask_a644a67deced3257: function(arg0, arg1) {
                arg0.depthMask(arg1 !== 0);
            },
            __wbg_depthRange_38b2287ffbea14fd: function(arg0, arg1, arg2) {
                arg0.depthRange(arg1, arg2);
            },
            __wbg_depthRange_5e90d4d236280ff5: function(arg0, arg1, arg2) {
                arg0.depthRange(arg1, arg2);
            },
            __wbg_description_02485704e69b1e7f: function(arg0, arg1) {
                const ret = arg1.description;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_destroy_7ae6d79c9c5ca8d9: function(arg0) {
                arg0.destroy();
            },
            __wbg_destroy_fe937f756bf8df37: function(arg0) {
                arg0.destroy();
            },
            __wbg_devicePixelContentBoxSize_dca8701a53307aca: function(arg0) {
                const ret = arg0.devicePixelContentBoxSize;
                return ret;
            },
            __wbg_devicePixelRatio_1c0e0ed7deb19cd8: function(arg0) {
                const ret = arg0.devicePixelRatio;
                return ret;
            },
            __wbg_disableVertexAttribArray_160060fbd7e97de0: function(arg0, arg1) {
                arg0.disableVertexAttribArray(arg1 >>> 0);
            },
            __wbg_disableVertexAttribArray_c7915eb0de6dd8f1: function(arg0, arg1) {
                arg0.disableVertexAttribArray(arg1 >>> 0);
            },
            __wbg_disable_1659d1b7d50c31e7: function(arg0, arg1) {
                arg0.disable(arg1 >>> 0);
            },
            __wbg_disable_40c3975167c1ee07: function(arg0, arg1) {
                arg0.disable(arg1 >>> 0);
            },
            __wbg_disconnect_39bfdcb35b1fc7b9: function(arg0) {
                arg0.disconnect();
            },
            __wbg_displayHeight_f06554969d4d6de8: function(arg0) {
                const ret = arg0.displayHeight;
                return ret;
            },
            __wbg_displayWidth_fdcc0a114d98d13e: function(arg0) {
                const ret = arg0.displayWidth;
                return ret;
            },
            __wbg_document_179650d6cb13c263: function(arg0) {
                const ret = arg0.document;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_done_89b2b13e91a60321: function(arg0) {
                const ret = arg0.done;
                return ret;
            },
            __wbg_drawArraysInstancedANGLE_d58dbd2d38fdebaa: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.drawArraysInstancedANGLE(arg1 >>> 0, arg2, arg3, arg4);
            },
            __wbg_drawArraysInstanced_51b161548a3f10c4: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.drawArraysInstanced(arg1 >>> 0, arg2, arg3, arg4);
            },
            __wbg_drawArrays_676becae0149ed65: function(arg0, arg1, arg2, arg3) {
                arg0.drawArrays(arg1 >>> 0, arg2, arg3);
            },
            __wbg_drawArrays_b0c59a6e158122f2: function(arg0, arg1, arg2, arg3) {
                arg0.drawArrays(arg1 >>> 0, arg2, arg3);
            },
            __wbg_drawBuffersWEBGL_c9b47f7f207125cf: function(arg0, arg1) {
                arg0.drawBuffersWEBGL(arg1);
            },
            __wbg_drawBuffers_1c1ec9b292442a2a: function(arg0, arg1) {
                arg0.drawBuffers(arg1);
            },
            __wbg_drawElementsInstancedANGLE_9b58c4013373b180: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.drawElementsInstancedANGLE(arg1 >>> 0, arg2, arg3 >>> 0, arg4, arg5);
            },
            __wbg_drawElementsInstanced_c7f96ea02e6d5326: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.drawElementsInstanced(arg1 >>> 0, arg2, arg3 >>> 0, arg4, arg5);
            },
            __wbg_drawIndexed_d31913e79d58fbac: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.drawIndexed(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4, arg5 >>> 0);
            },
            __wbg_draw_6877f98847e1e36c: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.draw(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4 >>> 0);
            },
            __wbg_elementFromPoint_082557ad1c446761: function(arg0, arg1, arg2) {
                const ret = arg0.elementFromPoint(arg1, arg2);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_elementFromPoint_49d780c87b3d05b7: function(arg0, arg1, arg2) {
                const ret = arg0.elementFromPoint(arg1, arg2);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_enableVertexAttribArray_4c08219124740f14: function(arg0, arg1) {
                arg0.enableVertexAttribArray(arg1 >>> 0);
            },
            __wbg_enableVertexAttribArray_7470ba2dcf2606e3: function(arg0, arg1) {
                arg0.enableVertexAttribArray(arg1 >>> 0);
            },
            __wbg_enable_28bbeed576131d1f: function(arg0, arg1) {
                arg0.enable(arg1 >>> 0);
            },
            __wbg_enable_611804c0ac1504ce: function(arg0, arg1) {
                arg0.enable(arg1 >>> 0);
            },
            __wbg_endQuery_a50f7fc49cfe56e9: function(arg0, arg1) {
                arg0.endQuery(arg1 >>> 0);
            },
            __wbg_end_f99ebed53d4e198a: function(arg0) {
                arg0.end();
            },
            __wbg_enqueue_6d83b4c6281bafd6: function() { return handleError(function (arg0, arg1) {
                arg0.enqueue(arg1);
            }, arguments); },
            __wbg_entries_015dc610cd81ede0: function(arg0) {
                const ret = Object.entries(arg0);
                return ret;
            },
            __wbg_error_622f41c5c32a13db: function(arg0) {
                const ret = arg0.error;
                return ret;
            },
            __wbg_error_657700d53a73881f: function(arg0, arg1, arg2, arg3) {
                console.error(arg0, arg1, arg2, arg3);
            },
            __wbg_error_744744ff0c9861e6: function(arg0) {
                console.error(arg0);
            },
            __wbg_error_7da16e6957d93dfc: function(arg0, arg1) {
                let deferred0_0;
                let deferred0_1;
                try {
                    deferred0_0 = arg0;
                    deferred0_1 = arg1;
                    console.error(getStringFromWasm0(arg0, arg1));
                } finally {
                    wasm.__wbindgen_free(deferred0_0, deferred0_1, 1);
                }
            },
            __wbg_features_2b07a28fe18ad0ce: function(arg0) {
                const ret = arg0.features;
                return ret;
            },
            __wbg_fenceSync_fe2cdba4a0d73679: function(arg0, arg1, arg2) {
                const ret = arg0.fenceSync(arg1 >>> 0, arg2 >>> 0);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_fetch_737feb0f4e4769cd: function(arg0, arg1) {
                const ret = fetch(arg0, arg1);
                return ret;
            },
            __wbg_fetch_9dad4fe911207b37: function(arg0) {
                const ret = fetch(arg0);
                return ret;
            },
            __wbg_fetch_b371b952a61cca04: function(arg0) {
                const ret = fetch(arg0);
                return ret;
            },
            __wbg_fetch_b5951fc96f52f786: function(arg0, arg1) {
                const ret = arg0.fetch(arg1);
                return ret;
            },
            __wbg_fetch_fadfd227089fdf80: function(arg0, arg1, arg2) {
                const ret = arg0.fetch(arg1, arg2);
                return ret;
            },
            __wbg_files_116196bc012ac3c8: function(arg0) {
                const ret = arg0.files;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_files_a4eb87e5e4343c46: function(arg0) {
                const ret = arg0.files;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_finish_126e6f2ac71e3096: function(arg0) {
                arg0.finish();
            },
            __wbg_finish_4d91de5e927dd13f: function(arg0, arg1) {
                const ret = arg0.finish(arg1);
                return ret;
            },
            __wbg_finish_6e06b68ab68cd9f6: function(arg0) {
                const ret = arg0.finish();
                return ret;
            },
            __wbg_finish_cbe7ec8675dd7705: function(arg0) {
                arg0.finish();
            },
            __wbg_flush_67fbd850838f4562: function(arg0) {
                const ret = arg0.flush();
                return ret;
            },
            __wbg_flush_db77b4a63d6b337d: function(arg0) {
                arg0.flush();
            },
            __wbg_flush_e03c08da6863b5ab: function(arg0) {
                arg0.flush();
            },
            __wbg_focus_5ecef5db03850e25: function() { return handleError(function (arg0, arg1) {
                arg0.focus(arg1);
            }, arguments); },
            __wbg_force_368c1897f399d783: function(arg0) {
                const ret = arg0.force;
                return ret;
            },
            __wbg_forward_4bb54c7f45451c64: function() { return handleError(function (arg0) {
                arg0.forward();
            }, arguments); },
            __wbg_framebufferRenderbuffer_4404cf9f9cb76937: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.framebufferRenderbuffer(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4);
            },
            __wbg_framebufferRenderbuffer_ba8bd5e008ee87eb: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.framebufferRenderbuffer(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4);
            },
            __wbg_framebufferTexture2D_3c2abd606fc53f31: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.framebufferTexture2D(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4, arg5);
            },
            __wbg_framebufferTexture2D_e1fb64212fcda219: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.framebufferTexture2D(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4, arg5);
            },
            __wbg_framebufferTextureLayer_f2d9db097bfbb863: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.framebufferTextureLayer(arg1 >>> 0, arg2 >>> 0, arg3, arg4, arg5);
            },
            __wbg_framebufferTextureMultiviewOVR_28d492b9dc484220: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
                arg0.framebufferTextureMultiviewOVR(arg1 >>> 0, arg2 >>> 0, arg3, arg4, arg5, arg6);
            },
            __wbg_frontFace_29ef7151de8b5ed9: function(arg0, arg1) {
                arg0.frontFace(arg1 >>> 0);
            },
            __wbg_frontFace_fc6d98dafa42de87: function(arg0, arg1) {
                arg0.frontFace(arg1 >>> 0);
            },
            __wbg_getBindGroupLayout_8b86af56ae09c095: function(arg0, arg1) {
                const ret = arg0.getBindGroupLayout(arg1 >>> 0);
                return ret;
            },
            __wbg_getBoundingClientRect_e828e6c31c66dea6: function(arg0) {
                const ret = arg0.getBoundingClientRect();
                return ret;
            },
            __wbg_getBufferSubData_11018928c908ac2c: function(arg0, arg1, arg2, arg3) {
                arg0.getBufferSubData(arg1 >>> 0, arg2, arg3);
            },
            __wbg_getComputedStyle_961681bdf7e518e8: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.getComputedStyle(arg1);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_getContext_7476e39fa008047e: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                const ret = arg0.getContext(getStringFromWasm0(arg1, arg2), arg3);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_getContext_ca12bb65aab778a4: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                const ret = arg0.getContext(getStringFromWasm0(arg1, arg2), arg3);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_getContext_e79ddf6a9cb3cc76: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.getContext(getStringFromWasm0(arg1, arg2));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_getContext_fd298c901058eb31: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.getContext(getStringFromWasm0(arg1, arg2));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_getCurrentTexture_20714d1bd9051cab: function() { return handleError(function (arg0) {
                const ret = arg0.getCurrentTexture();
                return ret;
            }, arguments); },
            __wbg_getData_fcb88fae21d94f1e: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                const ret = arg1.getData(getStringFromWasm0(arg2, arg3));
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_getDirectoryHandle_10036853d1aefa39: function(arg0, arg1, arg2) {
                const ret = arg0.getDirectoryHandle(getStringFromWasm0(arg1, arg2));
                return ret;
            },
            __wbg_getDirectoryHandle_cf175faf1a75a384: function(arg0, arg1, arg2, arg3) {
                const ret = arg0.getDirectoryHandle(getStringFromWasm0(arg1, arg2), arg3);
                return ret;
            },
            __wbg_getDirectory_389283588dfb8117: function(arg0) {
                const ret = arg0.getDirectory();
                return ret;
            },
            __wbg_getElementById_1cbd8f06dbe8eb8e: function(arg0, arg1, arg2) {
                const ret = arg0.getElementById(getStringFromWasm0(arg1, arg2));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_getExtension_101c7e41de3e4d90: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.getExtension(getStringFromWasm0(arg1, arg2));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_getFileHandle_72de55ab3ca9ad57: function(arg0, arg1, arg2, arg3) {
                const ret = arg0.getFileHandle(getStringFromWasm0(arg1, arg2), arg3);
                return ret;
            },
            __wbg_getFileHandle_96903ab38e634823: function(arg0, arg1, arg2) {
                const ret = arg0.getFileHandle(getStringFromWasm0(arg1, arg2));
                return ret;
            },
            __wbg_getFile_bdc0144baa662031: function(arg0) {
                const ret = arg0.getFile();
                return ret;
            },
            __wbg_getIndexedParameter_6d7a5bcccaa0f3e2: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.getIndexedParameter(arg1 >>> 0, arg2 >>> 0);
                return ret;
            }, arguments); },
            __wbg_getItem_b96269ddc16cf24a: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                const ret = arg1.getItem(getStringFromWasm0(arg2, arg3));
                var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                var len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_getMappedRange_d0bf3141224111b6: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.getMappedRange(arg1, arg2);
                return ret;
            }, arguments); },
            __wbg_getParameter_039a5899307fab55: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.getParameter(arg1 >>> 0);
                return ret;
            }, arguments); },
            __wbg_getParameter_d39f59581389af1b: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.getParameter(arg1 >>> 0);
                return ret;
            }, arguments); },
            __wbg_getPreferredCanvasFormat_8b57039d1801a506: function(arg0) {
                const ret = arg0.getPreferredCanvasFormat();
                return (__wbindgen_enum_GpuTextureFormat.indexOf(ret) + 1 || 102) - 1;
            },
            __wbg_getProgramInfoLog_c4762e0513468a26: function(arg0, arg1, arg2) {
                const ret = arg1.getProgramInfoLog(arg2);
                var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                var len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_getProgramInfoLog_d1ce570463a68779: function(arg0, arg1, arg2) {
                const ret = arg1.getProgramInfoLog(arg2);
                var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                var len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_getProgramParameter_b9995b56c258ac86: function(arg0, arg1, arg2) {
                const ret = arg0.getProgramParameter(arg1, arg2 >>> 0);
                return ret;
            },
            __wbg_getProgramParameter_c8d1154fbb3c0890: function(arg0, arg1, arg2) {
                const ret = arg0.getProgramParameter(arg1, arg2 >>> 0);
                return ret;
            },
            __wbg_getPropertyValue_dc6b061239dad6f1: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                const ret = arg1.getPropertyValue(getStringFromWasm0(arg2, arg3));
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_getQueryParameter_919125495ccb17ca: function(arg0, arg1, arg2) {
                const ret = arg0.getQueryParameter(arg1, arg2 >>> 0);
                return ret;
            },
            __wbg_getRandomValues_3f44b700395062e5: function() { return handleError(function (arg0, arg1) {
                globalThis.crypto.getRandomValues(getArrayU8FromWasm0(arg0, arg1));
            }, arguments); },
            __wbg_getRandomValues_ceb34d8ffce7e87f: function() { return handleError(function (arg0, arg1) {
                globalThis.crypto.getRandomValues(getArrayU8FromWasm0(arg0, arg1));
            }, arguments); },
            __wbg_getReader_b4b1868fbca77dbe: function() { return handleError(function (arg0) {
                const ret = arg0.getReader();
                return ret;
            }, arguments); },
            __wbg_getRootNode_f724c3be671a9a57: function(arg0) {
                const ret = arg0.getRootNode();
                return ret;
            },
            __wbg_getShaderInfoLog_5cee2add982c7165: function(arg0, arg1, arg2) {
                const ret = arg1.getShaderInfoLog(arg2);
                var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                var len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_getShaderInfoLog_bc236afe696c1283: function(arg0, arg1, arg2) {
                const ret = arg1.getShaderInfoLog(arg2);
                var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                var len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_getShaderParameter_3394e75dcb97f380: function(arg0, arg1, arg2) {
                const ret = arg0.getShaderParameter(arg1, arg2 >>> 0);
                return ret;
            },
            __wbg_getShaderParameter_cbcc0995e8e16214: function(arg0, arg1, arg2) {
                const ret = arg0.getShaderParameter(arg1, arg2 >>> 0);
                return ret;
            },
            __wbg_getSupportedExtensions_2a7458ec45e82560: function(arg0) {
                const ret = arg0.getSupportedExtensions();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_getSupportedProfiles_90a4f330938d0241: function(arg0) {
                const ret = arg0.getSupportedProfiles();
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_getSyncParameter_d8f6c145657a3550: function(arg0, arg1, arg2) {
                const ret = arg0.getSyncParameter(arg1, arg2 >>> 0);
                return ret;
            },
            __wbg_getTime_d6f070c088c9b5ed: function(arg0) {
                const ret = arg0.getTime();
                return ret;
            },
            __wbg_getUniformBlockIndex_cfee6ff6d323c784: function(arg0, arg1, arg2, arg3) {
                const ret = arg0.getUniformBlockIndex(arg1, getStringFromWasm0(arg2, arg3));
                return ret;
            },
            __wbg_getUniformLocation_24ef46cdda2148ab: function(arg0, arg1, arg2, arg3) {
                const ret = arg0.getUniformLocation(arg1, getStringFromWasm0(arg2, arg3));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_getUniformLocation_788a34295dd6fabe: function(arg0, arg1, arg2, arg3) {
                const ret = arg0.getUniformLocation(arg1, getStringFromWasm0(arg2, arg3));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_get_507a50627bffa49b: function(arg0, arg1) {
                const ret = arg0[arg1 >>> 0];
                return ret;
            },
            __wbg_get_757c867e2520bbc4: function(arg0, arg1) {
                const ret = arg0[arg1 >>> 0];
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_get_78f252d074a84d0b: function() { return handleError(function (arg0, arg1) {
                const ret = Reflect.get(arg0, arg1);
                return ret;
            }, arguments); },
            __wbg_get_b2053e9bfdf3ca8e: function(arg0, arg1) {
                const ret = arg0[arg1 >>> 0];
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_get_c7eb1f358a7654df: function() { return handleError(function (arg0, arg1) {
                const ret = Reflect.get(arg0, arg1);
                return ret;
            }, arguments); },
            __wbg_get_ddcbbb3501c3011e: function(arg0, arg1) {
                const ret = arg0[arg1 >>> 0];
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_get_done_670108eb06ecbe46: function(arg0) {
                const ret = arg0.done;
                return isLikeNone(ret) ? 0xFFFFFF : ret ? 1 : 0;
            },
            __wbg_get_e73985d6689d2245: function(arg0, arg1) {
                const ret = arg0[arg1 >>> 0];
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_get_unchecked_6e0ad6d2a41b06f6: function(arg0, arg1) {
                const ret = arg0[arg1 >>> 0];
                return ret;
            },
            __wbg_get_value_f465f5be30aa0963: function(arg0) {
                const ret = arg0.value;
                return ret;
            },
            __wbg_get_with_ref_key_6412cf3094599694: function(arg0, arg1) {
                const ret = arg0[arg1];
                return ret;
            },
            __wbg_gpu_2ccc250735d24a2a: function(arg0) {
                const ret = arg0.gpu;
                return ret;
            },
            __wbg_hasOwn_f2591afb8975e2fd: function(arg0, arg1) {
                const ret = Object.hasOwn(arg0, arg1);
                return ret;
            },
            __wbg_has_0c97053e877f47cc: function(arg0, arg1, arg2) {
                const ret = arg0.has(getStringFromWasm0(arg1, arg2));
                return ret;
            },
            __wbg_has_8374cf06984d8bfc: function() { return handleError(function (arg0, arg1) {
                const ret = Reflect.has(arg0, arg1);
                return ret;
            }, arguments); },
            __wbg_has_ce7fd01110e4972f: function(arg0, arg1, arg2) {
                const ret = arg0.has(getStringFromWasm0(arg1, arg2));
                return ret;
            },
            __wbg_hash_508149c4291ec8c2: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.hash;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_headers_7b59c5203c8c475d: function(arg0) {
                const ret = arg0.headers;
                return ret;
            },
            __wbg_headers_cf9c80f30e2a4eff: function(arg0) {
                const ret = arg0.headers;
                return ret;
            },
            __wbg_height_1ac64d880e0a71ae: function(arg0) {
                const ret = arg0.height;
                return ret;
            },
            __wbg_height_46f95580d0507f0a: function(arg0) {
                const ret = arg0.height;
                return ret;
            },
            __wbg_height_5b881707f59cdee5: function(arg0) {
                const ret = arg0.height;
                return ret;
            },
            __wbg_height_6eec812c213259a1: function(arg0) {
                const ret = arg0.height;
                return ret;
            },
            __wbg_height_9f27216001e3c804: function(arg0) {
                const ret = arg0.height;
                return ret;
            },
            __wbg_height_f2cc35b336f266f1: function(arg0) {
                const ret = arg0.height;
                return ret;
            },
            __wbg_hidden_c08eb1c29c138ab0: function(arg0) {
                const ret = arg0.hidden;
                return ret;
            },
            __wbg_history_e648b4314d9b256e: function() { return handleError(function (arg0) {
                const ret = arg0.history;
                return ret;
            }, arguments); },
            __wbg_host_21c8d54c9bdcd04a: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.host;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_hostname_6a4adb791d7e7242: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.hostname;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_href_0259f7f614252f13: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.href;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_href_bc4909da4ed58381: function(arg0, arg1) {
                const ret = arg1.href;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_identifier_d30bb260fab6b02a: function(arg0) {
                const ret = arg0.identifier;
                return ret;
            },
            __wbg_includes_78c9a3115b08eddc: function(arg0, arg1, arg2) {
                const ret = arg0.includes(arg1, arg2);
                return ret;
            },
            __wbg_info_79f5309d69d9c70e: function(arg0, arg1, arg2, arg3) {
                console.info(arg0, arg1, arg2, arg3);
            },
            __wbg_info_cf0d9a286850cd24: function(arg0) {
                const ret = arg0.info;
                return ret;
            },
            __wbg_info_eadbe775a8e2e9eb: function(arg0) {
                console.info(arg0);
            },
            __wbg_inlineSize_3c8412828bef21eb: function(arg0) {
                const ret = arg0.inlineSize;
                return ret;
            },
            __wbg_inputType_37c59110203135d8: function(arg0, arg1) {
                const ret = arg1.inputType;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_insertBefore_9121f73148bc4f7c: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.insertBefore(arg1, arg2);
                return ret;
            }, arguments); },
            __wbg_instanceof_ArrayBuffer_4480b9e0068a8adb: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof ArrayBuffer;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_Document_d1955f84f5d0351c: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof Document;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_DomException_952faa8037702c00: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof DOMException;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_Element_beebfaab75d12d9d: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof Element;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_Error_1fdac9f13a8181ba: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof Error;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_FileSystemDirectoryHandle_c9ab7c5cdb7a7c30: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof FileSystemDirectoryHandle;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_FileSystemFileHandle_68e80b30532d5f04: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof FileSystemFileHandle;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_FileSystemWritableFileStream_bbd33ec1789b2714: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof FileSystemWritableFileStream;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_File_ee62de53bca2e697: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof File;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_GpuOutOfMemoryError_6429c750997f1c8d: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof GPUOutOfMemoryError;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_GpuValidationError_75fa3611f065f4df: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof GPUValidationError;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_HtmlAnchorElement_0b37fbaa9075f12c: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof HTMLAnchorElement;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_HtmlButtonElement_2798f3f046c1c446: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof HTMLButtonElement;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_HtmlCanvasElement_ed02ed9136056019: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof HTMLCanvasElement;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_HtmlElement_4493a09212d3586f: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof HTMLElement;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_HtmlInputElement_ad3be04339d0e4df: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof HTMLInputElement;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_ImageBitmap_859f193922076b2b: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof ImageBitmap;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_MessageEvent_7d226bddd45cb41d: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof MessageEvent;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_Promise_4cb210c0b8f8c959: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof Promise;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_ReadableStream_3bdc7d10b03fd402: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof ReadableStream;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_ResizeObserverEntry_5d9f44b2d0d4bd47: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof ResizeObserverEntry;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_ResizeObserverSize_52b48dee6a4ab521: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof ResizeObserverSize;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_Response_c8b64b2256f01bec: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof Response;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_ShadowRoot_8ab3038bc5e14d84: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof ShadowRoot;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_TypeError_aa4c0c0517d53151: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof TypeError;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_Uint8Array_309b927aaf7a3fc7: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof Uint8Array;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_WebGl2RenderingContext_90225152e4e3c799: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof WebGL2RenderingContext;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_instanceof_Window_05ba1ee4f6781663: function(arg0) {
                let result;
                try {
                    result = arg0 instanceof Window;
                } catch (_) {
                    result = false;
                }
                const ret = result;
                return ret;
            },
            __wbg_invalidateFramebuffer_343bbfb15e6835fd: function() { return handleError(function (arg0, arg1, arg2) {
                arg0.invalidateFramebuffer(arg1 >>> 0, arg2);
            }, arguments); },
            __wbg_isActive_9e21f95da89fce93: function(arg0) {
                const ret = arg0.isActive;
                return ret;
            },
            __wbg_isArray_0677c962b281d01a: function(arg0) {
                const ret = Array.isArray(arg0);
                return ret;
            },
            __wbg_isComposing_3022d9ff79b517bd: function(arg0) {
                const ret = arg0.isComposing;
                return ret;
            },
            __wbg_isComposing_919a0fdf6ac030c9: function(arg0) {
                const ret = arg0.isComposing;
                return ret;
            },
            __wbg_isFallbackAdapter_8ccb967428491dcb: function(arg0) {
                const ret = arg0.isFallbackAdapter;
                return ret;
            },
            __wbg_isSafeInteger_04f36e4056f1b851: function(arg0) {
                const ret = Number.isSafeInteger(arg0);
                return ret;
            },
            __wbg_isSecureContext_d2e906a088ea2127: function(arg0) {
                const ret = arg0.isSecureContext;
                return ret;
            },
            __wbg_is_7b9d0b289033c7de: function(arg0, arg1) {
                const ret = Object.is(arg0, arg1);
                return ret;
            },
            __wbg_item_4b2887fd8cb17be5: function(arg0, arg1) {
                const ret = arg0.item(arg1 >>> 0);
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_items_350b6f2d566d3def: function(arg0) {
                const ret = arg0.items;
                return ret;
            },
            __wbg_iterator_6f722e4a93058b71: function() {
                const ret = Symbol.iterator;
                return ret;
            },
            __wbg_keyCode_f9ab89c2dd6c3770: function(arg0) {
                const ret = arg0.keyCode;
                return ret;
            },
            __wbg_key_803dca86cdcfa8dd: function(arg0, arg1) {
                const ret = arg1.key;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_key_c3e1e6137d321e2c: function(arg0, arg1) {
                const ret = arg1.key;
                var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                var len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_label_7ed42f25f841996b: function(arg0, arg1) {
                const ret = arg1.label;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_left_7e76a74d0db1754f: function(arg0) {
                const ret = arg0.left;
                return ret;
            },
            __wbg_length_1f0964f4a5e2c6d8: function(arg0) {
                const ret = arg0.length;
                return ret;
            },
            __wbg_length_370319915dc99107: function(arg0) {
                const ret = arg0.length;
                return ret;
            },
            __wbg_length_e08fc23135c66d6f: function(arg0) {
                const ret = arg0.length;
                return ret;
            },
            __wbg_length_eea4bfa35e75c87c: function(arg0) {
                const ret = arg0.length;
                return ret;
            },
            __wbg_length_ef21514bf74fe712: function(arg0) {
                const ret = arg0.length;
                return ret;
            },
            __wbg_limits_20c6f56636df7d38: function(arg0) {
                const ret = arg0.limits;
                return ret;
            },
            __wbg_limits_328c61cd41512420: function(arg0) {
                const ret = arg0.limits;
                return ret;
            },
            __wbg_linkProgram_4e047fb3197a0348: function(arg0, arg1) {
                arg0.linkProgram(arg1);
            },
            __wbg_linkProgram_d7c71c539c8c6a43: function(arg0, arg1) {
                arg0.linkProgram(arg1);
            },
            __wbg_localStorage_5bf6ce3f8e51412a: function() { return handleError(function (arg0) {
                const ret = arg0.localStorage;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_location_c9a2271428996698: function(arg0) {
                const ret = arg0.location;
                return ret;
            },
            __wbg_mapAsync_52b01fa9e8f765fd: function(arg0, arg1, arg2, arg3) {
                const ret = arg0.mapAsync(arg1 >>> 0, arg2, arg3);
                return ret;
            },
            __wbg_matchMedia_9968278b31706f78: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.matchMedia(getStringFromWasm0(arg1, arg2));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_matches_978994974df1e85b: function(arg0) {
                const ret = arg0.matches;
                return ret;
            },
            __wbg_maxBindGroupsPlusVertexBuffers_33e5006b23e20478: function(arg0) {
                const ret = arg0.maxBindGroupsPlusVertexBuffers;
                return ret;
            },
            __wbg_maxBindGroups_f6d26f3a67826666: function(arg0) {
                const ret = arg0.maxBindGroups;
                return ret;
            },
            __wbg_maxBindingsPerBindGroup_edab2e8dabbf6060: function(arg0) {
                const ret = arg0.maxBindingsPerBindGroup;
                return ret;
            },
            __wbg_maxBufferSize_bbc69284c14aa7da: function(arg0) {
                const ret = arg0.maxBufferSize;
                return ret;
            },
            __wbg_maxColorAttachmentBytesPerSample_63ebe4f81de2f34c: function(arg0) {
                const ret = arg0.maxColorAttachmentBytesPerSample;
                return ret;
            },
            __wbg_maxColorAttachments_aed8c38beabf3a5c: function(arg0) {
                const ret = arg0.maxColorAttachments;
                return ret;
            },
            __wbg_maxComputeInvocationsPerWorkgroup_2d964564c37f1c65: function(arg0) {
                const ret = arg0.maxComputeInvocationsPerWorkgroup;
                return ret;
            },
            __wbg_maxComputeWorkgroupSizeX_a3e3206570da184f: function(arg0) {
                const ret = arg0.maxComputeWorkgroupSizeX;
                return ret;
            },
            __wbg_maxComputeWorkgroupSizeY_dffa4a62244b7563: function(arg0) {
                const ret = arg0.maxComputeWorkgroupSizeY;
                return ret;
            },
            __wbg_maxComputeWorkgroupSizeZ_976ebcb760f6d07d: function(arg0) {
                const ret = arg0.maxComputeWorkgroupSizeZ;
                return ret;
            },
            __wbg_maxComputeWorkgroupStorageSize_2e8dbece6e532e2a: function(arg0) {
                const ret = arg0.maxComputeWorkgroupStorageSize;
                return ret;
            },
            __wbg_maxComputeWorkgroupsPerDimension_bb7d36b4d20c80f4: function(arg0) {
                const ret = arg0.maxComputeWorkgroupsPerDimension;
                return ret;
            },
            __wbg_maxDynamicStorageBuffersPerPipelineLayout_1ca859cb96a414e0: function(arg0) {
                const ret = arg0.maxDynamicStorageBuffersPerPipelineLayout;
                return ret;
            },
            __wbg_maxDynamicUniformBuffersPerPipelineLayout_e968f2c8cd8f4d46: function(arg0) {
                const ret = arg0.maxDynamicUniformBuffersPerPipelineLayout;
                return ret;
            },
            __wbg_maxInterStageShaderVariables_138ac882c4d6a3d3: function(arg0) {
                const ret = arg0.maxInterStageShaderVariables;
                return ret;
            },
            __wbg_maxSampledTexturesPerShaderStage_bb3e6b2698321fa6: function(arg0) {
                const ret = arg0.maxSampledTexturesPerShaderStage;
                return ret;
            },
            __wbg_maxSamplersPerShaderStage_98c00a1829fa414b: function(arg0) {
                const ret = arg0.maxSamplersPerShaderStage;
                return ret;
            },
            __wbg_maxStorageBufferBindingSize_e500e31f479e669e: function(arg0) {
                const ret = arg0.maxStorageBufferBindingSize;
                return ret;
            },
            __wbg_maxStorageBuffersPerShaderStage_eb663f6d7521b6a7: function(arg0) {
                const ret = arg0.maxStorageBuffersPerShaderStage;
                return ret;
            },
            __wbg_maxStorageTexturesPerShaderStage_bb3ad93b53e618c0: function(arg0) {
                const ret = arg0.maxStorageTexturesPerShaderStage;
                return ret;
            },
            __wbg_maxTextureArrayLayers_2a56d05fb261c99a: function(arg0) {
                const ret = arg0.maxTextureArrayLayers;
                return ret;
            },
            __wbg_maxTextureDimension1D_84590c1d4770d319: function(arg0) {
                const ret = arg0.maxTextureDimension1D;
                return ret;
            },
            __wbg_maxTextureDimension2D_7f2b5c8b2727e3fc: function(arg0) {
                const ret = arg0.maxTextureDimension2D;
                return ret;
            },
            __wbg_maxTextureDimension3D_7f3babddf55c32a6: function(arg0) {
                const ret = arg0.maxTextureDimension3D;
                return ret;
            },
            __wbg_maxUniformBufferBindingSize_d80a09e23c0b284c: function(arg0) {
                const ret = arg0.maxUniformBufferBindingSize;
                return ret;
            },
            __wbg_maxUniformBuffersPerShaderStage_0b8b2de676fa740e: function(arg0) {
                const ret = arg0.maxUniformBuffersPerShaderStage;
                return ret;
            },
            __wbg_maxVertexAttributes_a693dd921316649b: function(arg0) {
                const ret = arg0.maxVertexAttributes;
                return ret;
            },
            __wbg_maxVertexBufferArrayStride_f256d91f281076cb: function(arg0) {
                const ret = arg0.maxVertexBufferArrayStride;
                return ret;
            },
            __wbg_maxVertexBuffers_70ab564b25d5ac20: function(arg0) {
                const ret = arg0.maxVertexBuffers;
                return ret;
            },
            __wbg_message_4ada57a3710f1502: function(arg0, arg1) {
                const ret = arg1.message;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_message_fb0e6e7854e6ea7a: function(arg0, arg1) {
                const ret = arg1.message;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_metaKey_d961c7572a9f84f5: function(arg0) {
                const ret = arg0.metaKey;
                return ret;
            },
            __wbg_metaKey_f934f09e37889d70: function(arg0) {
                const ret = arg0.metaKey;
                return ret;
            },
            __wbg_minStorageBufferOffsetAlignment_3248ed00dcdbf79f: function(arg0) {
                const ret = arg0.minStorageBufferOffsetAlignment;
                return ret;
            },
            __wbg_minUniformBufferOffsetAlignment_3b9fa4caae03e903: function(arg0) {
                const ret = arg0.minUniformBufferOffsetAlignment;
                return ret;
            },
            __wbg_name_9d2bcd24d4433cef: function(arg0, arg1) {
                const ret = arg1.name;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_name_d7d79f5466e37447: function(arg0, arg1) {
                const ret = arg1.name;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_navigator_51379c10a84aeec9: function(arg0) {
                const ret = arg0.navigator;
                return ret;
            },
            __wbg_navigator_99621db14b3f1099: function(arg0) {
                const ret = arg0.navigator;
                return ret;
            },
            __wbg_newValue_6d3d665995a61f5e: function(arg0, arg1) {
                const ret = arg1.newValue;
                var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                var len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_new_08cb2fa678b17a48: function() { return handleError(function (arg0, arg1) {
                const ret = new URL(getStringFromWasm0(arg0, arg1));
                return ret;
            }, arguments); },
            __wbg_new_0_3da9e97f24fc69be: function() {
                const ret = new Date();
                return ret;
            },
            __wbg_new_0d809930cd1354c6: function() { return handleError(function () {
                const ret = new Headers();
                return ret;
            }, arguments); },
            __wbg_new_25e75d1f0df4d87a: function() { return handleError(function (arg0, arg1) {
                const ret = new OffscreenCanvas(arg0 >>> 0, arg1 >>> 0);
                return ret;
            }, arguments); },
            __wbg_new_32b398fb48b6d94a: function() {
                const ret = new Array();
                return ret;
            },
            __wbg_new_363c1767d99fa32f: function() {
                const ret = new Error();
                return ret;
            },
            __wbg_new_4339b2a2675a03e3: function() { return handleError(function () {
                const ret = new AbortController();
                return ret;
            }, arguments); },
            __wbg_new_51c73e5617fb3fad: function() { return handleError(function (arg0) {
                const ret = new EncodedVideoChunk(arg0);
                return ret;
            }, arguments); },
            __wbg_new_5394f65338077341: function() { return handleError(function (arg0) {
                const ret = new ResizeObserver((...args) => {
                    arg0(...args);
                    frame_scheduler.invalidate();
                });
                return ret;
            }, arguments); },
            __wbg_new_5e245ef5857d7f33: function(arg0, arg1) {
                const ret = new TypeError(getStringFromWasm0(arg0, arg1));
                return ret;
            },
            __wbg_new_a211ccc53aa68944: function() { return handleError(function (arg0) {
                const ret = new VideoDecoder({...arg0, output(frame) {
                    arg0.output(frame);
                    frame_scheduler.invalidate();
                }});
                return ret;
            }, arguments); },
            __wbg_new_aec3e25493d729fe: function(arg0, arg1) {
                try {
                    var state0 = {a: arg0, b: arg1};
                    var cb0 = (arg0, arg1) => {
                        const a = state0.a;
                        state0.a = 0;
                        try {
                            return wasm_bindgen__convert__closures_____invoke__h10b6862cecdf1332(a, state0.b, arg0, arg1);
                        } finally {
                            state0.a = a;
                        }
                    };
                    const ret = new Promise(cb0);
                    return ret;
                } finally {
                    state0.a = 0;
                }
            },
            __wbg_new_b667d279fd5aa943: function(arg0, arg1) {
                const ret = new Error(getStringFromWasm0(arg0, arg1));
                return ret;
            },
            __wbg_new_c9eb879b62d87c93: function() {
                const ret = new Error();
                return ret;
            },
            __wbg_new_cbb95886ce0eb0cb: function(arg0, arg1) {
                const ret = new Intl.DateTimeFormat(arg0, arg1);
                return ret;
            },
            __wbg_new_cd45aabdf6073e84: function(arg0) {
                const ret = new Uint8Array(arg0);
                return ret;
            },
            __wbg_new_da52cf8fe3429cb2: function() {
                const ret = new Object();
                return ret;
            },
            __wbg_new_f0787df90791d9ba: function() { return handleError(function () {
                const ret = new URLSearchParams();
                return ret;
            }, arguments); },
            __wbg_new_from_slice_77cdfb7977362f3c: function(arg0, arg1) {
                const ret = new Uint8Array(getArrayU8FromWasm0(arg0, arg1));
                return ret;
            },
            __wbg_new_typed_1824d93f294193e5: function(arg0, arg1) {
                try {
                    var state0 = {a: arg0, b: arg1};
                    var cb0 = (arg0, arg1) => {
                        const a = state0.a;
                        state0.a = 0;
                        try {
                            return wasm_bindgen__convert__closures_____invoke__h10b6862cecdf1332(a, state0.b, arg0, arg1);
                        } finally {
                            state0.a = a;
                        }
                    };
                    const ret = new Promise(cb0);
                    return ret;
                } finally {
                    state0.a = 0;
                }
            },
            __wbg_new_typed_4148bd5ae72ab3f0: function() {
                const ret = new Object();
                return ret;
            },
            __wbg_new_with_byte_offset_and_length_54c7724ee3ec7d82: function(arg0, arg1, arg2) {
                const ret = new Uint8Array(arg0, arg1 >>> 0, arg2 >>> 0);
                return ret;
            },
            __wbg_new_with_image_bitmap_and_video_frame_init_0db8a370be656c2c: function() { return handleError(function (arg0, arg1) {
                const ret = new VideoFrame(arg0, arg1);
                return ret;
            }, arguments); },
            __wbg_new_with_length_e6785c33c8e4cce8: function(arg0) {
                const ret = new Uint8Array(arg0 >>> 0);
                return ret;
            },
            __wbg_new_with_record_from_str_to_blob_promise_6112280bc8a0f052: function() { return handleError(function (arg0) {
                const ret = new ClipboardItem(arg0);
                return ret;
            }, arguments); },
            __wbg_new_with_str_454324b233393719: function() { return handleError(function (arg0, arg1) {
                const ret = new URLSearchParams(getStringFromWasm0(arg0, arg1));
                return ret;
            }, arguments); },
            __wbg_new_with_str_and_init_d95cbe11ce28e65e: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = new Request(getStringFromWasm0(arg0, arg1), arg2);
                return ret;
            }, arguments); },
            __wbg_new_with_u8_array_sequence_and_options_2c1900e5a5c93850: function() { return handleError(function (arg0, arg1) {
                const ret = new Blob(arg0, arg1);
                return ret;
            }, arguments); },
            __wbg_nextSibling_0e94ccfa3c22fa3c: function(arg0) {
                const ret = arg0.nextSibling;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_next_6dbf2c0ac8cde20f: function(arg0) {
                const ret = arg0.next;
                return ret;
            },
            __wbg_next_71f2aa1cb3d1e37e: function() { return handleError(function (arg0) {
                const ret = arg0.next();
                return ret;
            }, arguments); },
            __wbg_now_390768da5ee9e776: function(arg0) {
                const ret = arg0.now();
                return ret;
            },
            __wbg_now_86c0d4ba3fa605b8: function() {
                const ret = Date.now();
                return ret;
            },
            __wbg_now_e7c6795a7f81e10f: function(arg0) {
                const ret = arg0.now();
                return ret;
            },
            __wbg_observe_615bef91ee28c925: function(arg0, arg1, arg2) {
                arg0.observe(arg1, arg2);
            },
            __wbg_of_85f52f8b6491a7ca: function(arg0) {
                const ret = Array.of(arg0);
                return ret;
            },
            __wbg_offsetLeft_57573e1411874d68: function(arg0) {
                const ret = arg0.offsetLeft;
                return ret;
            },
            __wbg_offsetTop_eb7a93213506ba96: function(arg0) {
                const ret = arg0.offsetTop;
                return ret;
            },
            __wbg_ok_acc5e3fb89668864: function(arg0) {
                const ret = arg0.ok;
                return ret;
            },
            __wbg_onSubmittedWorkDone_270d6b5a45520e79: function(arg0) {
                const ret = arg0.onSubmittedWorkDone();
                return ret;
            },
            __wbg_open_1a1b29d8bfde6885: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
                const ret = arg0.open(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4), getStringFromWasm0(arg5, arg6));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_open_221b279749ba2e4e: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
                const ret = arg0.open(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_origin_ed66c06e67ad2049: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.origin;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_parentNode_fecbbdea2a930547: function(arg0) {
                const ret = arg0.parentNode;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_performance_3ef602e13d6c3b56: function(arg0) {
                const ret = arg0.performance;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_performance_3fcf6e32a7e1ed0a: function(arg0) {
                const ret = arg0.performance;
                return ret;
            },
            __wbg_persist_5ddcf223b47da9ba: function() { return handleError(function (arg0) {
                const ret = arg0.persist();
                return ret;
            }, arguments); },
            __wbg_pipeTo_3ecb20e17416edd6: function(arg0, arg1) {
                const ret = arg0.pipeTo(arg1);
                return ret;
            },
            __wbg_pixelStorei_2a93b18efde9acf8: function(arg0, arg1, arg2) {
                arg0.pixelStorei(arg1 >>> 0, arg2);
            },
            __wbg_pixelStorei_c844cd0db4f1fde6: function(arg0, arg1, arg2) {
                arg0.pixelStorei(arg1 >>> 0, arg2);
            },
            __wbg_polygonOffset_4eb460adf41db6cd: function(arg0, arg1, arg2) {
                arg0.polygonOffset(arg1, arg2);
            },
            __wbg_polygonOffset_eccb68e40a18f861: function(arg0, arg1, arg2) {
                arg0.polygonOffset(arg1, arg2);
            },
            __wbg_port_e2c291cf8fd5fc40: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.port;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_preventDefault_b64888c857500682: function(arg0) {
                arg0.preventDefault();
            },
            __wbg_protocol_0598aef25eb71eae: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.protocol;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_prototypesetcall_4770620bbe4688a0: function(arg0, arg1, arg2) {
                Uint8Array.prototype.set.call(getArrayU8FromWasm0(arg0, arg1), arg2);
            },
            __wbg_pushState_3d01701623122bc8: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.pushState(arg1, getStringFromWasm0(arg2, arg3), arg4 === 0 ? undefined : getStringFromWasm0(arg4, arg5));
            }, arguments); },
            __wbg_push_d2ae3af0c1217ae6: function(arg0, arg1) {
                const ret = arg0.push(arg1);
                return ret;
            },
            __wbg_queryCounterEXT_b74a4567ddfeecf0: function(arg0, arg1, arg2) {
                arg0.queryCounterEXT(arg1, arg2 >>> 0);
            },
            __wbg_querySelectorAll_7e98cbe256deaadd: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.querySelectorAll(getStringFromWasm0(arg1, arg2));
                return ret;
            }, arguments); },
            __wbg_querySelector_fd7d157ebe17cd16: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.querySelector(getStringFromWasm0(arg1, arg2));
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            }, arguments); },
            __wbg_queueMicrotask_0ab5b2d2393e99b9: function(arg0) {
                const ret = arg0.queueMicrotask;
                return ret;
            },
            __wbg_queueMicrotask_6a09b7bc46549209: function(arg0) {
                queueMicrotask(arg0);
            },
            __wbg_queue_adce34608fd0c893: function(arg0) {
                const ret = arg0.queue;
                return ret;
            },
            __wbg_readBuffer_4271437a70aae481: function(arg0, arg1) {
                arg0.readBuffer(arg1 >>> 0);
            },
            __wbg_readPixels_5f013a7d85b23800: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7) {
                arg0.readPixels(arg1, arg2, arg3, arg4, arg5 >>> 0, arg6 >>> 0, arg7);
            }, arguments); },
            __wbg_readPixels_82c9dee754d58176: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7) {
                arg0.readPixels(arg1, arg2, arg3, arg4, arg5 >>> 0, arg6 >>> 0, arg7);
            }, arguments); },
            __wbg_readPixels_c7861e25836bf57b: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7) {
                arg0.readPixels(arg1, arg2, arg3, arg4, arg5 >>> 0, arg6 >>> 0, arg7);
            }, arguments); },
            __wbg_read_8afa15f12a160ef8: function(arg0) {
                const ret = arg0.read();
                return ret;
            },
            __wbg_releaseLock_5b92874cad775644: function(arg0) {
                arg0.releaseLock();
            },
            __wbg_removeChild_8d9536328d674d54: function() { return handleError(function (arg0, arg1) {
                const ret = arg0.removeChild(arg1);
                return ret;
            }, arguments); },
            __wbg_removeEventListener_a3f23c70077bdcc1: function() { return handleError(function (arg0, arg1, arg2, arg3) {
                arg0.removeEventListener(getStringFromWasm0(arg1, arg2), arg3);
            }, arguments); },
            __wbg_removeItem_78e03a38da96e0ae: function() { return handleError(function (arg0, arg1, arg2) {
                arg0.removeItem(getStringFromWasm0(arg1, arg2));
            }, arguments); },
            __wbg_remove_ce1b54059317fe8a: function(arg0) {
                arg0.remove();
            },
            __wbg_renderbufferStorageMultisample_5c6e5d20c0eaa6ba: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.renderbufferStorageMultisample(arg1 >>> 0, arg2, arg3 >>> 0, arg4, arg5);
            },
            __wbg_renderbufferStorage_0a8de92542893819: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.renderbufferStorage(arg1 >>> 0, arg2 >>> 0, arg3, arg4);
            },
            __wbg_renderbufferStorage_ab5f745ff8efce3d: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.renderbufferStorage(arg1 >>> 0, arg2 >>> 0, arg3, arg4);
            },
            __wbg_replaceState_9a0a4a53d3bf3439: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.replaceState(arg1, getStringFromWasm0(arg2, arg3), arg4 === 0 ? undefined : getStringFromWasm0(arg4, arg5));
            }, arguments); },
            __wbg_requestAdapter_2e6718811c735a57: function(arg0, arg1) {
                const ret = arg0.requestAdapter(arg1);
                return ret;
            },
            __wbg_requestAdapter_fedd76261c649e55: function(arg0) {
                const ret = arg0.requestAdapter();
                return ret;
            },
            __wbg_requestAnimationFrame_1a85deeab66448c2: function() { return handleError(function (arg0, arg1) {
                const ret = frame_scheduler.request(arg1);
                return ret;
            }, arguments); },
            __wbg_requestDevice_ab46d0519ea1cc34: function(arg0, arg1) {
                const ret = arg0.requestDevice(arg1);
                return ret;
            },
            __wbg_reset_5f89fa780634d36d: function() { return handleError(function (arg0) {
                arg0.reset();
            }, arguments); },
            __wbg_resolve_2191a4dfe481c25b: function(arg0) {
                const ret = Promise.resolve(arg0);
                return ret;
            },
            __wbg_resolvedOptions_ce0ede387898d6bd: function(arg0) {
                const ret = arg0.resolvedOptions();
                return ret;
            },
            __wbg_respond_510e32df8aeb6817: function() { return handleError(function (arg0, arg1) {
                arg0.respond(arg1 >>> 0);
            }, arguments); },
            __wbg_right_36c53e00496f4f0a: function(arg0) {
                const ret = arg0.right;
                return ret;
            },
            __wbg_samplerParameterf_0b3308eeb1faa3a1: function(arg0, arg1, arg2, arg3) {
                arg0.samplerParameterf(arg1, arg2 >>> 0, arg3);
            },
            __wbg_samplerParameteri_7b1b4091de49aabb: function(arg0, arg1, arg2, arg3) {
                arg0.samplerParameteri(arg1, arg2 >>> 0, arg3);
            },
            __wbg_scissor_105e756596bc35df: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.scissor(arg1, arg2, arg3, arg4);
            },
            __wbg_scissor_573b844152316b8d: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.scissor(arg1, arg2, arg3, arg4);
            },
            __wbg_searchParams_23a839468a61ef4c: function(arg0) {
                const ret = arg0.searchParams;
                return ret;
            },
            __wbg_search_af2555aa41bd23cc: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.search;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_selectionEnd_bc4cb81b30d7175a: function() { return handleError(function (arg0) {
                const ret = arg0.selectionEnd;
                return isLikeNone(ret) ? Number.MAX_SAFE_INTEGER : (ret) >>> 0;
            }, arguments); },
            __wbg_selectionStart_965d703fd02aafa2: function() { return handleError(function (arg0) {
                const ret = arg0.selectionStart;
                return isLikeNone(ret) ? Number.MAX_SAFE_INTEGER : (ret) >>> 0;
            }, arguments); },
            __wbg_setAttribute_71039043be82d098: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
                arg0.setAttribute(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
            }, arguments); },
            __wbg_setBindGroup_268fd1714fff0ef5: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
                arg0.setBindGroup(arg1 >>> 0, arg2, getArrayU32FromWasm0(arg3, arg4), arg5, arg6 >>> 0);
            }, arguments); },
            __wbg_setBindGroup_f0de6cb2c7dbfc2c: function(arg0, arg1, arg2) {
                arg0.setBindGroup(arg1 >>> 0, arg2);
            },
            __wbg_setIndexBuffer_2531a9103450445e: function(arg0, arg1, arg2, arg3) {
                arg0.setIndexBuffer(arg1, __wbindgen_enum_GpuIndexFormat[arg2], arg3);
            },
            __wbg_setIndexBuffer_7f3cf667b4d71566: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.setIndexBuffer(arg1, __wbindgen_enum_GpuIndexFormat[arg2], arg3, arg4);
            },
            __wbg_setItem_364a11cf21db9039: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
                arg0.setItem(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
            }, arguments); },
            __wbg_setPipeline_c41bf46790f27f9e: function(arg0, arg1) {
                arg0.setPipeline(arg1);
            },
            __wbg_setProperty_e4e51b1b1d681d15: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
                arg0.setProperty(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
            }, arguments); },
            __wbg_setScissorRect_42511fefb18b86ef: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.setScissorRect(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4 >>> 0);
            },
            __wbg_setTimeout_91734b3436ad0e03: function(arg0, arg1) {
                const ret = setTimeout(arg0, arg1);
                return ret;
            },
            __wbg_setTimeout_cfa2cf195c3738db: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.setTimeout(arg1, arg2);
                return ret;
            }, arguments); },
            __wbg_setTimeout_f757f00851f76c42: function(arg0, arg1) {
                const ret = setTimeout(arg0, arg1);
                return ret;
            },
            __wbg_setVertexBuffer_1e448859663dd400: function(arg0, arg1, arg2, arg3) {
                arg0.setVertexBuffer(arg1 >>> 0, arg2, arg3);
            },
            __wbg_setVertexBuffer_7cf533d694e747f3: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.setVertexBuffer(arg1 >>> 0, arg2, arg3, arg4);
            },
            __wbg_setViewport_d9fc3eac343de7d0: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
                arg0.setViewport(arg1, arg2, arg3, arg4, arg5, arg6);
            },
            __wbg_set_0de9c62c23d04ad5: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
                arg0.set(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
            }, arguments); },
            __wbg_set_4d7dd76f3dae2926: function(arg0, arg1, arg2) {
                arg0.set(getArrayU8FromWasm0(arg1, arg2));
            },
            __wbg_set_61e45ae8061eca11: function(arg0, arg1, arg2) {
                arg0.set(arg1, arg2 >>> 0);
            },
            __wbg_set_6be42768c690e380: function(arg0, arg1, arg2) {
                arg0[arg1] = arg2;
            },
            __wbg_set_8535240470bf2500: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = Reflect.set(arg0, arg1, arg2);
                return ret;
            }, arguments); },
            __wbg_set_a_88262a42340d0b1c: function(arg0, arg1) {
                arg0.a = arg1;
            },
            __wbg_set_accept_5906cb0d4eb6ea4d: function(arg0, arg1, arg2) {
                arg0.accept = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_access_9a5092f05dc45fad: function(arg0, arg1) {
                arg0.access = __wbindgen_enum_GpuStorageTextureAccess[arg1];
            },
            __wbg_set_address_mode_u_9e2695575a219e33: function(arg0, arg1) {
                arg0.addressModeU = __wbindgen_enum_GpuAddressMode[arg1];
            },
            __wbg_set_address_mode_v_f479b2e6cccbcac4: function(arg0, arg1) {
                arg0.addressModeV = __wbindgen_enum_GpuAddressMode[arg1];
            },
            __wbg_set_address_mode_w_46273e153230180d: function(arg0, arg1) {
                arg0.addressModeW = __wbindgen_enum_GpuAddressMode[arg1];
            },
            __wbg_set_alpha_bfd2df62e7bc581b: function(arg0, arg1) {
                arg0.alpha = arg1;
            },
            __wbg_set_alpha_mode_df805952892caa9c: function(arg0, arg1) {
                arg0.alphaMode = __wbindgen_enum_GpuCanvasAlphaMode[arg1];
            },
            __wbg_set_alpha_to_coverage_enabled_8b5dc2b0a225b3b2: function(arg0, arg1) {
                arg0.alphaToCoverageEnabled = arg1 !== 0;
            },
            __wbg_set_array_layer_count_7312f0f31af94e7c: function(arg0, arg1) {
                arg0.arrayLayerCount = arg1 >>> 0;
            },
            __wbg_set_array_stride_f64_27ffaf4fffd74e61: function(arg0, arg1) {
                arg0.arrayStride = arg1;
            },
            __wbg_set_aspect_0d453bca3d012f02: function(arg0, arg1) {
                arg0.aspect = __wbindgen_enum_GpuTextureAspect[arg1];
            },
            __wbg_set_aspect_210da747c9d77aba: function(arg0, arg1) {
                arg0.aspect = __wbindgen_enum_GpuTextureAspect[arg1];
            },
            __wbg_set_aspect_4962514fe99e68e6: function(arg0, arg1) {
                arg0.aspect = __wbindgen_enum_GpuTextureAspect[arg1];
            },
            __wbg_set_attributes_7537844a7e6dafdc: function(arg0, arg1, arg2) {
                arg0.attributes = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_b_c47befe0af3261eb: function(arg0, arg1) {
                arg0.b = arg1;
            },
            __wbg_set_base_array_layer_f176bb9f1b37b342: function(arg0, arg1) {
                arg0.baseArrayLayer = arg1 >>> 0;
            },
            __wbg_set_base_mip_level_1df145d9f8db32a9: function(arg0, arg1) {
                arg0.baseMipLevel = arg1 >>> 0;
            },
            __wbg_set_bbfffe9b60e58c38: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.set(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
            },
            __wbg_set_beginning_of_pass_write_index_e9f5d016947893bd: function(arg0, arg1) {
                arg0.beginningOfPassWriteIndex = arg1 >>> 0;
            },
            __wbg_set_bind_group_layouts_5a9cfea401c020ab: function(arg0, arg1, arg2) {
                arg0.bindGroupLayouts = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_binding_155b0440b4307793: function(arg0, arg1) {
                arg0.binding = arg1 >>> 0;
            },
            __wbg_set_binding_f74df3510792aba1: function(arg0, arg1) {
                arg0.binding = arg1 >>> 0;
            },
            __wbg_set_blend_7493c2066c3e9970: function(arg0, arg1) {
                arg0.blend = arg1;
            },
            __wbg_set_body_029f2d171e0a005f: function(arg0, arg1) {
                arg0.body = arg1;
            },
            __wbg_set_box_223b9bc0b7f548f6: function(arg0, arg1) {
                arg0.box = __wbindgen_enum_ResizeObserverBoxOptions[arg1];
            },
            __wbg_set_buffer_9c01e3b6d6765ea2: function(arg0, arg1) {
                arg0.buffer = arg1;
            },
            __wbg_set_buffer_c3410572051920ba: function(arg0, arg1) {
                arg0.buffer = arg1;
            },
            __wbg_set_buffer_ef7f75306cf663ed: function(arg0, arg1) {
                arg0.buffer = arg1;
            },
            __wbg_set_buffers_7d0d8f507699e956: function(arg0, arg1, arg2) {
                arg0.buffers = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_bytes_per_row_c54ca96953f35774: function(arg0, arg1) {
                arg0.bytesPerRow = arg1 >>> 0;
            },
            __wbg_set_bytes_per_row_d69b88eee3929c07: function(arg0, arg1) {
                arg0.bytesPerRow = arg1 >>> 0;
            },
            __wbg_set_cache_b4a740b195c051f4: function(arg0, arg1) {
                arg0.cache = __wbindgen_enum_RequestCache[arg1];
            },
            __wbg_set_className_e0b1e805ac9ecbf4: function(arg0, arg1, arg2) {
                arg0.className = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_clear_value_gpu_color_dict_6211425789c76e59: function(arg0, arg1) {
                arg0.clearValue = arg1;
            },
            __wbg_set_code_b4f37f81f45b5b25: function(arg0, arg1, arg2) {
                arg0.code = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_codec_73803202999ff3ab: function(arg0, arg1, arg2) {
                arg0.codec = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_coded_height_5cf9f82bfb61b098: function(arg0, arg1) {
                arg0.codedHeight = arg1 >>> 0;
            },
            __wbg_set_coded_width_e7ada372e1276c51: function(arg0, arg1) {
                arg0.codedWidth = arg1 >>> 0;
            },
            __wbg_set_color_83aa977526e88cbb: function(arg0, arg1) {
                arg0.color = arg1;
            },
            __wbg_set_color_attachments_581fdb3310e4abfa: function(arg0, arg1, arg2) {
                arg0.colorAttachments = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_compare_cd9b62cdb92eb580: function(arg0, arg1) {
                arg0.compare = __wbindgen_enum_GpuCompareFunction[arg1];
            },
            __wbg_set_compare_f36b34abfaa08ccb: function(arg0, arg1) {
                arg0.compare = __wbindgen_enum_GpuCompareFunction[arg1];
            },
            __wbg_set_count_069a4eac409bac55: function(arg0, arg1) {
                arg0.count = arg1 >>> 0;
            },
            __wbg_set_create_a807a6e9ac628698: function(arg0, arg1) {
                arg0.create = arg1 !== 0;
            },
            __wbg_set_create_fa1dfa475fac91e9: function(arg0, arg1) {
                arg0.create = arg1 !== 0;
            },
            __wbg_set_credentials_bb34a40189e3b43b: function(arg0, arg1) {
                arg0.credentials = __wbindgen_enum_RequestCredentials[arg1];
            },
            __wbg_set_cull_mode_fc649853947a3d0c: function(arg0, arg1) {
                arg0.cullMode = __wbindgen_enum_GpuCullMode[arg1];
            },
            __wbg_set_data_353846afd42a10b1: function(arg0, arg1) {
                arg0.data = arg1;
            },
            __wbg_set_depth_bias_clamp_1c0d695df7f092e5: function(arg0, arg1) {
                arg0.depthBiasClamp = arg1;
            },
            __wbg_set_depth_bias_d7cd16096242a657: function(arg0, arg1) {
                arg0.depthBias = arg1;
            },
            __wbg_set_depth_bias_slope_scale_c4e52ec743ef55ba: function(arg0, arg1) {
                arg0.depthBiasSlopeScale = arg1;
            },
            __wbg_set_depth_clear_value_beda3ec5b1a5c43a: function(arg0, arg1) {
                arg0.depthClearValue = arg1;
            },
            __wbg_set_depth_compare_0c8631eb2eae98e3: function(arg0, arg1) {
                arg0.depthCompare = __wbindgen_enum_GpuCompareFunction[arg1];
            },
            __wbg_set_depth_fail_op_668155ae33d3c06f: function(arg0, arg1) {
                arg0.depthFailOp = __wbindgen_enum_GpuStencilOperation[arg1];
            },
            __wbg_set_depth_load_op_511c513eab4e56a9: function(arg0, arg1) {
                arg0.depthLoadOp = __wbindgen_enum_GpuLoadOp[arg1];
            },
            __wbg_set_depth_or_array_layers_89371305ed0bd962: function(arg0, arg1) {
                arg0.depthOrArrayLayers = arg1 >>> 0;
            },
            __wbg_set_depth_read_only_7f41a74741c144ec: function(arg0, arg1) {
                arg0.depthReadOnly = arg1 !== 0;
            },
            __wbg_set_depth_stencil_97506c7bea4f53da: function(arg0, arg1) {
                arg0.depthStencil = arg1;
            },
            __wbg_set_depth_stencil_attachment_73b79e8b4e948222: function(arg0, arg1) {
                arg0.depthStencilAttachment = arg1;
            },
            __wbg_set_depth_store_op_c89f33b39b43361c: function(arg0, arg1) {
                arg0.depthStoreOp = __wbindgen_enum_GpuStoreOp[arg1];
            },
            __wbg_set_depth_write_enabled_ce89750042940350: function(arg0, arg1) {
                arg0.depthWriteEnabled = arg1 !== 0;
            },
            __wbg_set_description_1ca246c5902e3ff8: function(arg0, arg1) {
                arg0.description = arg1;
            },
            __wbg_set_device_e275d1d4f3c9eb74: function(arg0, arg1) {
                arg0.device = arg1;
            },
            __wbg_set_dimension_868eee80f4b90011: function(arg0, arg1) {
                arg0.dimension = __wbindgen_enum_GpuTextureDimension[arg1];
            },
            __wbg_set_dimension_e325282e613ca0a4: function(arg0, arg1) {
                arg0.dimension = __wbindgen_enum_GpuTextureViewDimension[arg1];
            },
            __wbg_set_download_67c3dbb2b32b18d0: function(arg0, arg1, arg2) {
                arg0.download = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_dst_factor_ec7407f19be1aff9: function(arg0, arg1) {
                arg0.dstFactor = __wbindgen_enum_GpuBlendFactor[arg1];
            },
            __wbg_set_duration_f64_d850447775429a67: function(arg0, arg1) {
                arg0.duration = arg1;
            },
            __wbg_set_end_of_pass_write_index_0d546e46b86ea069: function(arg0, arg1) {
                arg0.endOfPassWriteIndex = arg1 >>> 0;
            },
            __wbg_set_entries_86a29dd6291c95e7: function(arg0, arg1, arg2) {
                arg0.entries = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_entries_a12aca1e458b0456: function(arg0, arg1, arg2) {
                arg0.entries = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_entry_point_207540f042015ce5: function(arg0, arg1, arg2) {
                arg0.entryPoint = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_entry_point_e87e79251dd3144f: function(arg0, arg1, arg2) {
                arg0.entryPoint = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_error_e0fdb5ef69612720: function(arg0, arg1) {
                arg0.error = arg1;
            },
            __wbg_set_external_texture_386483d8dd82ab56: function(arg0, arg1) {
                arg0.externalTexture = arg1;
            },
            __wbg_set_fail_op_92f716dbc88b6973: function(arg0, arg1) {
                arg0.failOp = __wbindgen_enum_GpuStencilOperation[arg1];
            },
            __wbg_set_flip_y_4e1632b36ad0413a: function(arg0, arg1) {
                arg0.flipY = arg1 !== 0;
            },
            __wbg_set_format_1fcaa7d60546b490: function(arg0, arg1) {
                arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
            },
            __wbg_set_format_2c1414a817c213f8: function(arg0, arg1) {
                arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
            },
            __wbg_set_format_533f9ffa7eef563d: function(arg0, arg1) {
                arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
            },
            __wbg_set_format_5d2f25cc93654ecc: function(arg0, arg1) {
                arg0.format = __wbindgen_enum_GpuVertexFormat[arg1];
            },
            __wbg_set_format_5ff53724ed6cedf2: function(arg0, arg1) {
                arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
            },
            __wbg_set_format_815efd4dc4817bbb: function(arg0, arg1) {
                arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
            },
            __wbg_set_format_e52bdcca880d2c8e: function(arg0, arg1) {
                arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
            },
            __wbg_set_fragment_8b780f00a0b0e6f3: function(arg0, arg1) {
                arg0.fragment = arg1;
            },
            __wbg_set_front_face_28ffdf524eedce5b: function(arg0, arg1) {
                arg0.frontFace = __wbindgen_enum_GpuFrontFace[arg1];
            },
            __wbg_set_g_5983abfc46e0cf4e: function(arg0, arg1) {
                arg0.g = arg1;
            },
            __wbg_set_hardware_acceleration_e0184d39413599b8: function(arg0, arg1) {
                arg0.hardwareAcceleration = __wbindgen_enum_HardwareAcceleration[arg1];
            },
            __wbg_set_has_dynamic_offset_62bc230bdb7c54d0: function(arg0, arg1) {
                arg0.hasDynamicOffset = arg1 !== 0;
            },
            __wbg_set_headers_9c61d123c3ee1f10: function(arg0, arg1) {
                arg0.headers = arg1;
            },
            __wbg_set_height_14335c4047cf9c1b: function(arg0, arg1) {
                arg0.height = arg1 >>> 0;
            },
            __wbg_set_height_7d9d8f892e6964c6: function(arg0, arg1) {
                arg0.height = arg1 >>> 0;
            },
            __wbg_set_height_bbeef8f354041577: function(arg0, arg1) {
                arg0.height = arg1 >>> 0;
            },
            __wbg_set_href_25786788ec7ffedd: function(arg0, arg1, arg2) {
                arg0.href = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_id_4beae8b813c092d8: function(arg0, arg1, arg2) {
                arg0.id = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_innerHTML_f78a45a07f97e136: function(arg0, arg1, arg2) {
                arg0.innerHTML = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_innerText_847403b9d4f38f77: function(arg0, arg1, arg2) {
                arg0.innerText = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_integrity_13c390f33acee59c: function(arg0, arg1, arg2) {
                arg0.integrity = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_08d9be3e4719c226: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_17eb9fe3a02f62b0: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_48e6b787d256f621: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_547d0d4aec39fbe9: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_5ee7427342869829: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_60ad96c811e0d109: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_72bb4f41ef0cb893: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_79387decda299036: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_9556af8b5cda3c9d: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_d010f237b26f2c55: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_e16e2dbe51349c7f: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_e3944e54881b8c50: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_label_e922700240417ab5: function(arg0, arg1, arg2) {
                arg0.label = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_layout_50ab727f44b38f26: function(arg0, arg1) {
                arg0.layout = arg1;
            },
            __wbg_set_layout_913d53c17194c989: function(arg0, arg1) {
                arg0.layout = arg1;
            },
            __wbg_set_layout_gpu_auto_layout_mode_aeba193938b47882: function(arg0, arg1) {
                arg0.layout = __wbindgen_enum_GpuAutoLayoutMode[arg1];
            },
            __wbg_set_load_op_99661da6c4eab9b0: function(arg0, arg1) {
                arg0.loadOp = __wbindgen_enum_GpuLoadOp[arg1];
            },
            __wbg_set_lod_max_clamp_dd2d9f9f052f4f44: function(arg0, arg1) {
                arg0.lodMaxClamp = arg1;
            },
            __wbg_set_lod_min_clamp_6d20c97916baeb93: function(arg0, arg1) {
                arg0.lodMinClamp = arg1;
            },
            __wbg_set_mag_filter_b5adebc99cb938e1: function(arg0, arg1) {
                arg0.magFilter = __wbindgen_enum_GpuFilterMode[arg1];
            },
            __wbg_set_mapped_at_creation_81b586dc90a50347: function(arg0, arg1) {
                arg0.mappedAtCreation = arg1 !== 0;
            },
            __wbg_set_mask_70a8a59ce09e5997: function(arg0, arg1) {
                arg0.mask = arg1 >>> 0;
            },
            __wbg_set_max_anisotropy_2beada0e2db62c45: function(arg0, arg1) {
                arg0.maxAnisotropy = arg1;
            },
            __wbg_set_method_5532d59b92d76467: function(arg0, arg1, arg2) {
                arg0.method = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_min_binding_size_f64_5005a6904cdf43da: function(arg0, arg1) {
                arg0.minBindingSize = arg1;
            },
            __wbg_set_min_filter_c72f17375e135f0a: function(arg0, arg1) {
                arg0.minFilter = __wbindgen_enum_GpuFilterMode[arg1];
            },
            __wbg_set_mip_level_13253f3afc7aa58a: function(arg0, arg1) {
                arg0.mipLevel = arg1 >>> 0;
            },
            __wbg_set_mip_level_count_534caaa7e68e68b8: function(arg0, arg1) {
                arg0.mipLevelCount = arg1 >>> 0;
            },
            __wbg_set_mip_level_count_776c8c218b65bc08: function(arg0, arg1) {
                arg0.mipLevelCount = arg1 >>> 0;
            },
            __wbg_set_mip_level_f7ac79e8c54f59ad: function(arg0, arg1) {
                arg0.mipLevel = arg1 >>> 0;
            },
            __wbg_set_mipmap_filter_5bf66195a3639700: function(arg0, arg1) {
                arg0.mipmapFilter = __wbindgen_enum_GpuMipmapFilterMode[arg1];
            },
            __wbg_set_mode_66c79886ad78fc05: function(arg0, arg1) {
                arg0.mode = __wbindgen_enum_RequestMode[arg1];
            },
            __wbg_set_mode_9990b3393ba469ae: function(arg0, arg1) {
                arg0.mode = __wbindgen_enum_GpuCanvasToneMappingMode[arg1];
            },
            __wbg_set_module_d0e2098713606cae: function(arg0, arg1) {
                arg0.module = arg1;
            },
            __wbg_set_module_f02e076ca7e7daf8: function(arg0, arg1) {
                arg0.module = arg1;
            },
            __wbg_set_multiple_682a70d088570168: function(arg0, arg1) {
                arg0.multiple = arg1 !== 0;
            },
            __wbg_set_multisample_37ddafe88b5cd466: function(arg0, arg1) {
                arg0.multisample = arg1;
            },
            __wbg_set_multisampled_7913fd7183272840: function(arg0, arg1) {
                arg0.multisampled = arg1 !== 0;
            },
            __wbg_set_offset_f64_28c24dc15000932e: function(arg0, arg1) {
                arg0.offset = arg1;
            },
            __wbg_set_offset_f64_89f0ce01a689839e: function(arg0, arg1) {
                arg0.offset = arg1;
            },
            __wbg_set_offset_f64_b562d1367e34ef93: function(arg0, arg1) {
                arg0.offset = arg1;
            },
            __wbg_set_offset_f64_fa66068813376ca3: function(arg0, arg1) {
                arg0.offset = arg1;
            },
            __wbg_set_once_51a9fb6b8af8a72b: function(arg0, arg1) {
                arg0.once = arg1 !== 0;
            },
            __wbg_set_onclick_527135192dd54d92: function(arg0, arg1) {
                arg0.onclick = arg1;
            },
            __wbg_set_onuncapturederror_c8a77eb8695205a0: function(arg0, arg1) {
                arg0.onuncapturederror = arg1;
            },
            __wbg_set_operation_62ce44e1728c4047: function(arg0, arg1) {
                arg0.operation = __wbindgen_enum_GpuBlendOperation[arg1];
            },
            __wbg_set_optimize_for_latency_3e3786621aaf6f56: function(arg0, arg1) {
                arg0.optimizeForLatency = arg1 !== 0;
            },
            __wbg_set_origin_gpu_origin_2d_dict_1240202973e56f92: function(arg0, arg1) {
                arg0.origin = arg1;
            },
            __wbg_set_origin_gpu_origin_3d_dict_37222d7b3d238123: function(arg0, arg1) {
                arg0.origin = arg1;
            },
            __wbg_set_origin_gpu_origin_3d_dict_631c04520718091f: function(arg0, arg1) {
                arg0.origin = arg1;
            },
            __wbg_set_output_6401c39ffe15258f: function(arg0, arg1) {
                arg0.output = arg1;
            },
            __wbg_set_pass_op_cf02fa088d6352a7: function(arg0, arg1) {
                arg0.passOp = __wbindgen_enum_GpuStencilOperation[arg1];
            },
            __wbg_set_power_preference_8fdca0b7af640d49: function(arg0, arg1) {
                arg0.powerPreference = __wbindgen_enum_GpuPowerPreference[arg1];
            },
            __wbg_set_premultiplied_alpha_3f27816ad319d5a9: function(arg0, arg1) {
                arg0.premultipliedAlpha = arg1 !== 0;
            },
            __wbg_set_prevent_scroll_82778f333ef22ca8: function(arg0, arg1) {
                arg0.preventScroll = arg1 !== 0;
            },
            __wbg_set_primitive_43c23761a55b4088: function(arg0, arg1) {
                arg0.primitive = arg1;
            },
            __wbg_set_query_set_41de86d2401aee04: function(arg0, arg1) {
                arg0.querySet = arg1;
            },
            __wbg_set_r_c6f4c68f4804d655: function(arg0, arg1) {
                arg0.r = arg1;
            },
            __wbg_set_redirect_badd73a0bcb765e3: function(arg0, arg1) {
                arg0.redirect = __wbindgen_enum_RequestRedirect[arg1];
            },
            __wbg_set_referrer_02890bb2de855af1: function(arg0, arg1, arg2) {
                arg0.referrer = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_referrer_policy_e49a6d0d7473fd16: function(arg0, arg1) {
                arg0.referrerPolicy = __wbindgen_enum_ReferrerPolicy[arg1];
            },
            __wbg_set_required_features_1baf274a8669db60: function(arg0, arg1, arg2) {
                arg0.requiredFeatures = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_required_limits_871ed33c68613dcb: function(arg0, arg1) {
                arg0.requiredLimits = arg1;
            },
            __wbg_set_resolve_target_gpu_texture_view_b19a4f2debf79b96: function(arg0, arg1) {
                arg0.resolveTarget = arg1;
            },
            __wbg_set_resource_5ae7b5e67924f234: function(arg0, arg1) {
                arg0.resource = arg1;
            },
            __wbg_set_resource_gpu_buffer_binding_e5dbca063e7cb67b: function(arg0, arg1) {
                arg0.resource = arg1;
            },
            __wbg_set_resource_gpu_texture_view_eb46c355d51ad7e5: function(arg0, arg1) {
                arg0.resource = arg1;
            },
            __wbg_set_rows_per_image_5011f97318ee71af: function(arg0, arg1) {
                arg0.rowsPerImage = arg1 >>> 0;
            },
            __wbg_set_rows_per_image_59a813ac5006e10e: function(arg0, arg1) {
                arg0.rowsPerImage = arg1 >>> 0;
            },
            __wbg_set_sample_count_eb86a8b18545b54f: function(arg0, arg1) {
                arg0.sampleCount = arg1 >>> 0;
            },
            __wbg_set_sample_type_c32e1dfff94e63eb: function(arg0, arg1) {
                arg0.sampleType = __wbindgen_enum_GpuTextureSampleType[arg1];
            },
            __wbg_set_sampler_c0e1258543a33bce: function(arg0, arg1) {
                arg0.sampler = arg1;
            },
            __wbg_set_shader_location_7e1832a74f912217: function(arg0, arg1) {
                arg0.shaderLocation = arg1 >>> 0;
            },
            __wbg_set_signal_c4ef8faddb4c1446: function(arg0, arg1) {
                arg0.signal = arg1;
            },
            __wbg_set_size_f64_6bcd40704bf4cfdc: function(arg0, arg1) {
                arg0.size = arg1;
            },
            __wbg_set_size_f64_8b8f6bba5d678162: function(arg0, arg1) {
                arg0.size = arg1;
            },
            __wbg_set_size_gpu_extent_3d_dict_7e42e1c98fa36434: function(arg0, arg1) {
                arg0.size = arg1;
            },
            __wbg_set_source_0c40b87cfdd5d704: function(arg0, arg1) {
                arg0.source = arg1;
            },
            __wbg_set_source_html_canvas_element_f657e39507ba2fe5: function(arg0, arg1) {
                arg0.source = arg1;
            },
            __wbg_set_source_html_image_element_fcc7cba0635adac1: function(arg0, arg1) {
                arg0.source = arg1;
            },
            __wbg_set_source_html_video_element_e63a39653665f651: function(arg0, arg1) {
                arg0.source = arg1;
            },
            __wbg_set_source_image_data_68478f1afce208b8: function(arg0, arg1) {
                arg0.source = arg1;
            },
            __wbg_set_source_offscreen_canvas_266a3de949693e62: function(arg0, arg1) {
                arg0.source = arg1;
            },
            __wbg_set_source_video_frame_3083c0ce54b9cb73: function(arg0, arg1) {
                arg0.source = arg1;
            },
            __wbg_set_src_factor_9bfe84af9b7b5cac: function(arg0, arg1) {
                arg0.srcFactor = __wbindgen_enum_GpuBlendFactor[arg1];
            },
            __wbg_set_stencil_back_85b22f1db5b1940a: function(arg0, arg1) {
                arg0.stencilBack = arg1;
            },
            __wbg_set_stencil_clear_value_42be608809151e2a: function(arg0, arg1) {
                arg0.stencilClearValue = arg1 >>> 0;
            },
            __wbg_set_stencil_front_525526164a798a44: function(arg0, arg1) {
                arg0.stencilFront = arg1;
            },
            __wbg_set_stencil_load_op_31838c036993098a: function(arg0, arg1) {
                arg0.stencilLoadOp = __wbindgen_enum_GpuLoadOp[arg1];
            },
            __wbg_set_stencil_read_mask_5cc26495e8b3ae82: function(arg0, arg1) {
                arg0.stencilReadMask = arg1 >>> 0;
            },
            __wbg_set_stencil_read_only_bf1d0c1897e25c62: function(arg0, arg1) {
                arg0.stencilReadOnly = arg1 !== 0;
            },
            __wbg_set_stencil_store_op_e6be1cbc3a8fc210: function(arg0, arg1) {
                arg0.stencilStoreOp = __wbindgen_enum_GpuStoreOp[arg1];
            },
            __wbg_set_stencil_write_mask_d9cb40ec4b4bee5b: function(arg0, arg1) {
                arg0.stencilWriteMask = arg1 >>> 0;
            },
            __wbg_set_step_mode_a97bb24714da41a9: function(arg0, arg1) {
                arg0.stepMode = __wbindgen_enum_GpuVertexStepMode[arg1];
            },
            __wbg_set_storage_texture_939a097db4b18bd4: function(arg0, arg1) {
                arg0.storageTexture = arg1;
            },
            __wbg_set_store_op_b5fdf672436f13f3: function(arg0, arg1) {
                arg0.storeOp = __wbindgen_enum_GpuStoreOp[arg1];
            },
            __wbg_set_strip_index_format_9f787be6c5fc9e87: function(arg0, arg1) {
                arg0.stripIndexFormat = __wbindgen_enum_GpuIndexFormat[arg1];
            },
            __wbg_set_tabIndex_70047c7d062bb928: function(arg0, arg1) {
                arg0.tabIndex = arg1;
            },
            __wbg_set_targets_c38bd200c836d66f: function(arg0, arg1, arg2) {
                arg0.targets = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_texture_016561d5911339e5: function(arg0, arg1) {
                arg0.texture = arg1;
            },
            __wbg_set_texture_1f64653a5d2d7b4d: function(arg0, arg1) {
                arg0.texture = arg1;
            },
            __wbg_set_texture_9dcedde1bb31eda6: function(arg0, arg1) {
                arg0.texture = arg1;
            },
            __wbg_set_timestamp_244da668ac8da67a: function(arg0, arg1) {
                arg0.timestamp = arg1;
            },
            __wbg_set_timestamp_25d4d8d3cdbe80a2: function(arg0, arg1) {
                arg0.timestamp = arg1;
            },
            __wbg_set_timestamp_f64_47419c7ea896d17c: function(arg0, arg1) {
                arg0.timestamp = arg1;
            },
            __wbg_set_timestamp_writes_98bed1a8bbc6682d: function(arg0, arg1) {
                arg0.timestampWrites = arg1;
            },
            __wbg_set_tone_mapping_b3464f1baa4cff92: function(arg0, arg1) {
                arg0.toneMapping = arg1;
            },
            __wbg_set_topology_da25f2cc5af203d2: function(arg0, arg1) {
                arg0.topology = __wbindgen_enum_GpuPrimitiveTopology[arg1];
            },
            __wbg_set_type_57a3257a711da878: function(arg0, arg1) {
                arg0.type = __wbindgen_enum_EncodedVideoChunkType[arg1];
            },
            __wbg_set_type_8ce203e412e28cf6: function(arg0, arg1, arg2) {
                arg0.type = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_type_ccf8472d40abcddf: function(arg0, arg1) {
                arg0.type = __wbindgen_enum_GpuSamplerBindingType[arg1];
            },
            __wbg_set_type_d09829f59932a0fc: function(arg0, arg1) {
                arg0.type = __wbindgen_enum_GpuBufferBindingType[arg1];
            },
            __wbg_set_type_d2a9a3c584ce2f9a: function(arg0, arg1, arg2) {
                arg0.type = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_unclipped_depth_04524a2b44e1e3c1: function(arg0, arg1) {
                arg0.unclippedDepth = arg1 !== 0;
            },
            __wbg_set_usage_a137f82ca163b0a9: function(arg0, arg1) {
                arg0.usage = arg1 >>> 0;
            },
            __wbg_set_usage_b2a2935f37bf3d08: function(arg0, arg1) {
                arg0.usage = arg1 >>> 0;
            },
            __wbg_set_usage_ba5b0f8b333ab325: function(arg0, arg1) {
                arg0.usage = arg1 >>> 0;
            },
            __wbg_set_usage_ddd42599bbba7779: function(arg0, arg1) {
                arg0.usage = arg1 >>> 0;
            },
            __wbg_set_value_e5d078763e63e81e: function(arg0, arg1, arg2) {
                arg0.value = getStringFromWasm0(arg1, arg2);
            },
            __wbg_set_vertex_0be5d146f9ff6f36: function(arg0, arg1) {
                arg0.vertex = arg1;
            },
            __wbg_set_view_dimension_0df554032f1f3a85: function(arg0, arg1) {
                arg0.viewDimension = __wbindgen_enum_GpuTextureViewDimension[arg1];
            },
            __wbg_set_view_dimension_4818d4c18ce5815e: function(arg0, arg1) {
                arg0.viewDimension = __wbindgen_enum_GpuTextureViewDimension[arg1];
            },
            __wbg_set_view_formats_4347dc8363331086: function(arg0, arg1, arg2) {
                arg0.viewFormats = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_view_formats_5797d2fff3c11808: function(arg0, arg1, arg2) {
                arg0.viewFormats = getArrayJsValueViewFromWasm0(arg1, arg2);
            },
            __wbg_set_view_gpu_texture_view_9b2d86b6b99d9fd9: function(arg0, arg1) {
                arg0.view = arg1;
            },
            __wbg_set_view_gpu_texture_view_c0f35f8857c25206: function(arg0, arg1) {
                arg0.view = arg1;
            },
            __wbg_set_visibility_9570b037224c4cc2: function(arg0, arg1) {
                arg0.visibility = arg1 >>> 0;
            },
            __wbg_set_width_49ac9b7d914afc85: function(arg0, arg1) {
                arg0.width = arg1 >>> 0;
            },
            __wbg_set_width_8e30d010cd66830d: function(arg0, arg1) {
                arg0.width = arg1 >>> 0;
            },
            __wbg_set_width_9f685402c2cbee70: function(arg0, arg1) {
                arg0.width = arg1 >>> 0;
            },
            __wbg_set_write_mask_d45279e56abbfcb5: function(arg0, arg1) {
                arg0.writeMask = arg1 >>> 0;
            },
            __wbg_set_x_232d24fdc32d8351: function(arg0, arg1) {
                arg0.x = arg1 >>> 0;
            },
            __wbg_set_x_876d592971db129a: function(arg0, arg1) {
                arg0.x = arg1 >>> 0;
            },
            __wbg_set_y_18fe375093e59dfb: function(arg0, arg1) {
                arg0.y = arg1 >>> 0;
            },
            __wbg_set_y_2b1f5ac0dd5586a5: function(arg0, arg1) {
                arg0.y = arg1 >>> 0;
            },
            __wbg_set_z_ef005d82bc9d24e3: function(arg0, arg1) {
                arg0.z = arg1 >>> 0;
            },
            __wbg_shaderSource_4cf90af97621ff49: function(arg0, arg1, arg2, arg3) {
                arg0.shaderSource(arg1, getStringFromWasm0(arg2, arg3));
            },
            __wbg_shaderSource_c3469dc2221dd528: function(arg0, arg1, arg2, arg3) {
                arg0.shaderSource(arg1, getStringFromWasm0(arg2, arg3));
            },
            __wbg_shiftKey_9bcb8bdd60c2f152: function(arg0) {
                const ret = arg0.shiftKey;
                return ret;
            },
            __wbg_shiftKey_9f797da486b2ade8: function(arg0) {
                const ret = arg0.shiftKey;
                return ret;
            },
            __wbg_signal_dad7cb35193abd31: function(arg0) {
                const ret = arg0.signal;
                return ret;
            },
            __wbg_size_6304a694765921a9: function(arg0) {
                const ret = arg0.size;
                return ret;
            },
            __wbg_size_79acc354d385bbfe: function(arg0) {
                const ret = arg0.size;
                return ret;
            },
            __wbg_slice_2b88ff0ac64039d6: function(arg0, arg1) {
                const ret = arg1.slice();
                const ptr1 = passArrayJsValueToWasm0(ret, wasm.__wbindgen_malloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_slice_7c7553e3b38b0ddb: function() { return handleError(function (arg0, arg1, arg2) {
                const ret = arg0.slice(arg1, arg2);
                return ret;
            }, arguments); },
            __wbg_stack_12be8432da3b35d0: function(arg0, arg1) {
                const ret = arg1.stack;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_stack_9ed1bd1924f4f869: function(arg0, arg1) {
                const ret = arg1.stack;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_state_c83ca713bb9cda98: function(arg0) {
                const ret = arg0.state;
                return ret;
            },
            __wbg_state_d4cb8ed54a665e6e: function(arg0) {
                const ret = arg0.state;
                return (__wbindgen_enum_CodecState.indexOf(ret) + 1 || 4) - 1;
            },
            __wbg_state_edcc5b2da67f07f2: function() { return handleError(function (arg0) {
                const ret = arg0.state;
                return ret;
            }, arguments); },
            __wbg_static_accessor_GLOBAL_4ef717fb391d88b7: function() {
                const ret = typeof global === 'undefined' ? null : global;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_static_accessor_GLOBAL_THIS_8d1badc68b5a74f4: function() {
                const ret = typeof globalThis === 'undefined' ? null : globalThis;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_static_accessor_SELF_146583524fe1469b: function() {
                const ret = typeof self === 'undefined' ? null : self;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_static_accessor_WINDOW_f2829a2234d7819e: function() {
                const ret = typeof window === 'undefined' ? null : window;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_statusText_9f08c32741a99815: function(arg0, arg1) {
                const ret = arg1.statusText;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_status_c45b3b9b3033184a: function(arg0) {
                const ret = arg0.status;
                return ret;
            },
            __wbg_stencilFuncSeparate_35136c4e5153406f: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.stencilFuncSeparate(arg1 >>> 0, arg2 >>> 0, arg3, arg4 >>> 0);
            },
            __wbg_stencilFuncSeparate_814300446c2969ef: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.stencilFuncSeparate(arg1 >>> 0, arg2 >>> 0, arg3, arg4 >>> 0);
            },
            __wbg_stencilMaskSeparate_49367b0b5883a8bd: function(arg0, arg1, arg2) {
                arg0.stencilMaskSeparate(arg1 >>> 0, arg2 >>> 0);
            },
            __wbg_stencilMaskSeparate_63976cc45fb94d84: function(arg0, arg1, arg2) {
                arg0.stencilMaskSeparate(arg1 >>> 0, arg2 >>> 0);
            },
            __wbg_stencilMask_1c99b79b516d12dd: function(arg0, arg1) {
                arg0.stencilMask(arg1 >>> 0);
            },
            __wbg_stencilMask_9a844dc58a89992f: function(arg0, arg1) {
                arg0.stencilMask(arg1 >>> 0);
            },
            __wbg_stencilOpSeparate_b2cb9af05b803e02: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.stencilOpSeparate(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4 >>> 0);
            },
            __wbg_stencilOpSeparate_c77fcb47561d0aee: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.stencilOpSeparate(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4 >>> 0);
            },
            __wbg_stopPropagation_4c4ff88c29f9bc38: function(arg0) {
                arg0.stopPropagation();
            },
            __wbg_storage_756400487605531a: function(arg0) {
                const ret = arg0.storage;
                return ret;
            },
            __wbg_stream_0ea97b74f081f92b: function(arg0) {
                const ret = arg0.stream();
                return ret;
            },
            __wbg_stringify_b54333f60f1e4dad: function() { return handleError(function (arg0) {
                const ret = JSON.stringify(arg0);
                return ret;
            }, arguments); },
            __wbg_structuredClone_93aecf316c984721: function() { return handleError(function (arg0) {
                const ret = window.structuredClone(arg0);
                return ret;
            }, arguments); },
            __wbg_style_6657aed849e5d757: function(arg0) {
                const ret = arg0.style;
                return ret;
            },
            __wbg_subgroupMaxSize_1527c5f7a8fe91bb: function(arg0) {
                const ret = arg0.subgroupMaxSize;
                return ret;
            },
            __wbg_subgroupMinSize_d6c5ad4bddc828e9: function(arg0) {
                const ret = arg0.subgroupMinSize;
                return ret;
            },
            __wbg_submit_ce44115121cd166c: function(arg0, arg1, arg2) {
                arg0.submit(getArrayJsValueViewFromWasm0(arg1, arg2));
            },
            __wbg_texImage2D_3813406af5bf54c8: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texImage2D_5abd8779d1d033c7: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texImage2D_8d168171984f2a40: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texImage3D_bdd9bebe42ed1f52: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10) {
                arg0.texImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8 >>> 0, arg9 >>> 0, arg10);
            }, arguments); },
            __wbg_texImage3D_ef16a1f721b3f908: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10) {
                arg0.texImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8 >>> 0, arg9 >>> 0, arg10);
            }, arguments); },
            __wbg_texParameteri_1fc451e0964fc91c: function(arg0, arg1, arg2, arg3) {
                arg0.texParameteri(arg1 >>> 0, arg2 >>> 0, arg3);
            },
            __wbg_texParameteri_9d0daa263d3a863f: function(arg0, arg1, arg2, arg3) {
                arg0.texParameteri(arg1 >>> 0, arg2 >>> 0, arg3);
            },
            __wbg_texStorage2D_7f947efc63dac273: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.texStorage2D(arg1 >>> 0, arg2, arg3 >>> 0, arg4, arg5);
            },
            __wbg_texStorage3D_f8f2e4b3386736f9: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
                arg0.texStorage3D(arg1 >>> 0, arg2, arg3 >>> 0, arg4, arg5, arg6);
            },
            __wbg_texSubImage2D_047380bb2660e4f9: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage2D_5058af3d30a8e205: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage2D_6a376bfc3a31436b: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage2D_98c43894eb217aa7: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage2D_bed5e7a3cd81d409: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage2D_cccafa6de64f2781: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage2D_d1af697e69f8a9e4: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage2D_d3cd09d0ffcb27be: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage2D_e107b4f88c19b920: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9) {
                arg0.texSubImage2D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7 >>> 0, arg8 >>> 0, arg9);
            }, arguments); },
            __wbg_texSubImage3D_3711a86f03ffceef: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.texSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0, arg11);
            }, arguments); },
            __wbg_texSubImage3D_45e498ae6298998c: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.texSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0, arg11);
            }, arguments); },
            __wbg_texSubImage3D_4fdd4cd95a2925c2: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.texSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0, arg11);
            }, arguments); },
            __wbg_texSubImage3D_6cb6cfd732dad145: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.texSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0, arg11);
            }, arguments); },
            __wbg_texSubImage3D_8077e90ec309c414: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.texSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0, arg11);
            }, arguments); },
            __wbg_texSubImage3D_93b38c69acb735c8: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.texSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0, arg11);
            }, arguments); },
            __wbg_texSubImage3D_c9e5a071796d412f: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.texSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0, arg11);
            }, arguments); },
            __wbg_texSubImage3D_feebaf7f0f4594c6: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, arg11) {
                arg0.texSubImage3D(arg1 >>> 0, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9 >>> 0, arg10 >>> 0, arg11);
            }, arguments); },
            __wbg_then_16d107c451e9905d: function(arg0, arg1, arg2) {
                const ret = arg0.then(arg1, arg2);
                return ret;
            },
            __wbg_then_6ec10ae38b3e92f7: function(arg0, arg1) {
                const ret = arg0.then(arg1);
                return ret;
            },
            __wbg_timestamp_263c471d3598c2cc: function(arg0) {
                const ret = arg0.timestamp;
                return ret;
            },
            __wbg_toString_b201c2690bbe445a: function(arg0) {
                const ret = arg0.toString();
                return ret;
            },
            __wbg_toString_bac9199ff382784d: function(arg0) {
                const ret = arg0.toString();
                return ret;
            },
            __wbg_top_fe120acfa924a430: function(arg0) {
                const ret = arg0.top;
                return ret;
            },
            __wbg_touches_a631c50f1b367753: function(arg0) {
                const ret = arg0.touches;
                return ret;
            },
            __wbg_type_fa708ab6c8b1b8ab: function(arg0, arg1) {
                const ret = arg1.type;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_unconfigure_0a07a0a40de8988d: function(arg0) {
                arg0.unconfigure();
            },
            __wbg_uniform1f_62692c8fa8e7bf1e: function(arg0, arg1, arg2) {
                arg0.uniform1f(arg1, arg2);
            },
            __wbg_uniform1f_b79d0c5667f9fb40: function(arg0, arg1, arg2) {
                arg0.uniform1f(arg1, arg2);
            },
            __wbg_uniform1i_5830de6702add20a: function(arg0, arg1, arg2) {
                arg0.uniform1i(arg1, arg2);
            },
            __wbg_uniform1i_7621f908f78177df: function(arg0, arg1, arg2) {
                arg0.uniform1i(arg1, arg2);
            },
            __wbg_uniform1ui_cd7ad5581093b3df: function(arg0, arg1, arg2) {
                arg0.uniform1ui(arg1, arg2 >>> 0);
            },
            __wbg_uniform2fv_1b43656b33177d21: function(arg0, arg1, arg2, arg3) {
                arg0.uniform2fv(arg1, getArrayF32FromWasm0(arg2, arg3));
            },
            __wbg_uniform2fv_948dab6a82b428ac: function(arg0, arg1, arg2, arg3) {
                arg0.uniform2fv(arg1, getArrayF32FromWasm0(arg2, arg3));
            },
            __wbg_uniform2iv_859048b9d60f46ae: function(arg0, arg1, arg2, arg3) {
                arg0.uniform2iv(arg1, getArrayI32FromWasm0(arg2, arg3));
            },
            __wbg_uniform2iv_f84a24961c0cfcd0: function(arg0, arg1, arg2, arg3) {
                arg0.uniform2iv(arg1, getArrayI32FromWasm0(arg2, arg3));
            },
            __wbg_uniform2uiv_8a9cb3155271213b: function(arg0, arg1, arg2, arg3) {
                arg0.uniform2uiv(arg1, getArrayU32FromWasm0(arg2, arg3));
            },
            __wbg_uniform3fv_8ecb5ebb510b7bce: function(arg0, arg1, arg2, arg3) {
                arg0.uniform3fv(arg1, getArrayF32FromWasm0(arg2, arg3));
            },
            __wbg_uniform3fv_95d1933ea1440725: function(arg0, arg1, arg2, arg3) {
                arg0.uniform3fv(arg1, getArrayF32FromWasm0(arg2, arg3));
            },
            __wbg_uniform3iv_09abae5eabd6b9d6: function(arg0, arg1, arg2, arg3) {
                arg0.uniform3iv(arg1, getArrayI32FromWasm0(arg2, arg3));
            },
            __wbg_uniform3iv_a3a7008990fd84f0: function(arg0, arg1, arg2, arg3) {
                arg0.uniform3iv(arg1, getArrayI32FromWasm0(arg2, arg3));
            },
            __wbg_uniform3uiv_3c0b163732f5b8f0: function(arg0, arg1, arg2, arg3) {
                arg0.uniform3uiv(arg1, getArrayU32FromWasm0(arg2, arg3));
            },
            __wbg_uniform4f_9ff60fc65b0ed726: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.uniform4f(arg1, arg2, arg3, arg4, arg5);
            },
            __wbg_uniform4f_b25e39808b830021: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.uniform4f(arg1, arg2, arg3, arg4, arg5);
            },
            __wbg_uniform4fv_4ca8c114ca3de099: function(arg0, arg1, arg2, arg3) {
                arg0.uniform4fv(arg1, getArrayF32FromWasm0(arg2, arg3));
            },
            __wbg_uniform4fv_674a247aeb15012d: function(arg0, arg1, arg2, arg3) {
                arg0.uniform4fv(arg1, getArrayF32FromWasm0(arg2, arg3));
            },
            __wbg_uniform4iv_45ab52abcb3f882c: function(arg0, arg1, arg2, arg3) {
                arg0.uniform4iv(arg1, getArrayI32FromWasm0(arg2, arg3));
            },
            __wbg_uniform4iv_d02934d7b94df609: function(arg0, arg1, arg2, arg3) {
                arg0.uniform4iv(arg1, getArrayI32FromWasm0(arg2, arg3));
            },
            __wbg_uniform4uiv_0d1a8ed214f10c31: function(arg0, arg1, arg2, arg3) {
                arg0.uniform4uiv(arg1, getArrayU32FromWasm0(arg2, arg3));
            },
            __wbg_uniformBlockBinding_a9ed6b750199e03c: function(arg0, arg1, arg2, arg3) {
                arg0.uniformBlockBinding(arg1, arg2 >>> 0, arg3 >>> 0);
            },
            __wbg_uniformMatrix2fv_769725d64641341f: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix2fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix2fv_9284424cc6aac672: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix2fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix2x3fv_dba00c4fc8eefe47: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix2x3fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix2x4fv_d801a561c3c18169: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix2x4fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix3fv_33e96c7d29dc1e22: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix3fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix3fv_568aa181379c8a75: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix3fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix3x2fv_ce43e8186ea60a1e: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix3x2fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix3x4fv_8abccc5745b0dd90: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix3x4fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix4fv_25115a23e04f6db7: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix4fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix4fv_423b958042692150: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix4fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix4x2fv_1ac2bf986a322e3f: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix4x2fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_uniformMatrix4x3fv_8640fa85b90ea910: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.uniformMatrix4x3fv(arg1, arg2 !== 0, getArrayF32FromWasm0(arg3, arg4));
            },
            __wbg_unmap_adaf93276fdf9aaf: function(arg0) {
                arg0.unmap();
            },
            __wbg_url_abdb8fb08377f8c0: function(arg0, arg1) {
                const ret = arg1.url;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_usage_437399485b209edf: function(arg0) {
                const ret = arg0.usage;
                return ret;
            },
            __wbg_useProgram_182d120fe476921b: function(arg0, arg1) {
                arg0.useProgram(arg1);
            },
            __wbg_useProgram_49495850b446fa56: function(arg0, arg1) {
                arg0.useProgram(arg1);
            },
            __wbg_userActivation_61228a123251b08f: function(arg0) {
                const ret = arg0.userActivation;
                return ret;
            },
            __wbg_userAgent_0558f0ac642f7771: function() { return handleError(function (arg0, arg1) {
                const ret = arg1.userAgent;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            }, arguments); },
            __wbg_valueOf_64f89f12f08671ee: function(arg0) {
                const ret = arg0.valueOf();
                return ret;
            },
            __wbg_value_1f687dfa7d6c3d08: function(arg0, arg1) {
                const ret = arg1.value;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbg_value_a5d5488a9589444a: function(arg0) {
                const ret = arg0.value;
                return ret;
            },
            __wbg_vertexAttribDivisorANGLE_978337b09d11ed84: function(arg0, arg1, arg2) {
                arg0.vertexAttribDivisorANGLE(arg1 >>> 0, arg2 >>> 0);
            },
            __wbg_vertexAttribDivisor_fb31b5ed9bc856da: function(arg0, arg1, arg2) {
                arg0.vertexAttribDivisor(arg1 >>> 0, arg2 >>> 0);
            },
            __wbg_vertexAttribIPointer_de08a8d8b625e253: function(arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.vertexAttribIPointer(arg1 >>> 0, arg2, arg3 >>> 0, arg4, arg5);
            },
            __wbg_vertexAttribPointer_a8f0af57269c2067: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
                arg0.vertexAttribPointer(arg1 >>> 0, arg2, arg3 >>> 0, arg4 !== 0, arg5, arg6);
            },
            __wbg_vertexAttribPointer_b300c8e000cdac93: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
                arg0.vertexAttribPointer(arg1 >>> 0, arg2, arg3 >>> 0, arg4 !== 0, arg5, arg6);
            },
            __wbg_videoHeight_1420ccecd0b8b9a1: function(arg0) {
                const ret = arg0.videoHeight;
                return ret;
            },
            __wbg_videoWidth_3c582f863b387cd5: function(arg0) {
                const ret = arg0.videoWidth;
                return ret;
            },
            __wbg_view_21f1d4a4f175dfa9: function(arg0) {
                const ret = arg0.view;
                return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
            },
            __wbg_viewport_affdf15c559df1e2: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.viewport(arg1, arg2, arg3, arg4);
            },
            __wbg_viewport_e8a16ca4a5085e5f: function(arg0, arg1, arg2, arg3, arg4) {
                arg0.viewport(arg1, arg2, arg3, arg4);
            },
            __wbg_warn_77c4eb4a21e10a21: function(arg0, arg1, arg2, arg3) {
                console.warn(arg0, arg1, arg2, arg3);
            },
            __wbg_warn_b1370d804fa3e259: function(arg0) {
                console.warn(arg0);
            },
            __wbg_width_05a6fecf7eca198d: function(arg0) {
                const ret = arg0.width;
                return ret;
            },
            __wbg_width_20c45c895834b83f: function(arg0) {
                const ret = arg0.width;
                return ret;
            },
            __wbg_width_6d9315ecc7140ff6: function(arg0) {
                const ret = arg0.width;
                return ret;
            },
            __wbg_width_c1e3781335067e0c: function(arg0) {
                const ret = arg0.width;
                return ret;
            },
            __wbg_width_d2f212a0df13e242: function(arg0) {
                const ret = arg0.width;
                return ret;
            },
            __wbg_width_f9b3cbe357a34b85: function(arg0) {
                const ret = arg0.width;
                return ret;
            },
            __wbg_writeBuffer_8b5bd251a89198bc: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
                arg0.writeBuffer(arg1, arg2, getArrayU8FromWasm0(arg3, arg4), arg5, arg6);
            }, arguments); },
            __wbg_writeText_34bfead2ae78e5bb: function(arg0, arg1, arg2) {
                const ret = arg0.writeText(getStringFromWasm0(arg1, arg2));
                return ret;
            },
            __wbg_writeTexture_53ba204c494b042c: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5) {
                arg0.writeTexture(arg1, getArrayU8FromWasm0(arg2, arg3), arg4, arg5);
            }, arguments); },
            __wbg_write_2d484d0dddfacea9: function(arg0, arg1) {
                const ret = arg0.write(arg1);
                return ret;
            },
            __wbindgen_cast_0000000000000001: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [Externref], shim_idx: 30866, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h764f62e2e9f0b28a);
                return ret;
            },
            __wbindgen_cast_0000000000000002: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [Externref], shim_idx: 35570, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__hf5ab2b0e699d4375);
                return ret;
            },
            __wbindgen_cast_0000000000000003: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("Array<any>")], shim_idx: 25362, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h1b8e70bf81932a72);
                return ret;
            },
            __wbindgen_cast_0000000000000004: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("Error")], shim_idx: 28853, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h04afcae3e0839798);
                return ret;
            },
            __wbindgen_cast_0000000000000005: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("Event")], shim_idx: 25362, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h1b8e70bf81932a72_4);
                return ret;
            },
            __wbindgen_cast_0000000000000006: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("GPUDevice")], shim_idx: 25601, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3);
                return ret;
            },
            __wbindgen_cast_0000000000000007: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("GPUUncapturedErrorEvent")], shim_idx: 25602, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h991044b12b207aeb);
                return ret;
            },
            __wbindgen_cast_0000000000000008: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("PopStateEvent")], shim_idx: 8, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h5a4a279089dfc290);
                return ret;
            },
            __wbindgen_cast_0000000000000009: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("StorageEvent")], shim_idx: 4680, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__ha617783b6c8d7033);
                return ret;
            },
            __wbindgen_cast_000000000000000a: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("VideoFrame")], shim_idx: 28853, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h04afcae3e0839798_9);
                return ret;
            },
            __wbindgen_cast_000000000000000b: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("any")], shim_idx: 25601, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3_10);
                return ret;
            },
            __wbindgen_cast_000000000000000c: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("undefined")], shim_idx: 25601, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3_11);
                return ret;
            },
            __wbindgen_cast_000000000000000d: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("undefined")], shim_idx: 28852, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__hb3308f9470298f68);
                return ret;
            },
            __wbindgen_cast_000000000000000e: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [], shim_idx: 2104, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__ha5a90c0ae8ed2257);
                return ret;
            },
            __wbindgen_cast_000000000000000f: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [], shim_idx: 25363, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h5532da4c0e334d68);
                return ret;
            },
            __wbindgen_cast_0000000000000010: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [], shim_idx: 29477, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h5906433b3b84f0a2);
                return ret;
            },
            __wbindgen_cast_0000000000000011: function(arg0, arg1) {
                // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [], shim_idx: 7596, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
                const ret = makeMutClosure(arg0, arg1, wasm_bindgen__convert__closures_____invoke__h10a72af867dc4fc9);
                return ret;
            },
            __wbindgen_cast_0000000000000012: function(arg0) {
                // Cast intrinsic for `F64 -> Externref`.
                const ret = arg0;
                return ret;
            },
            __wbindgen_cast_0000000000000013: function(arg0, arg1) {
                // Cast intrinsic for `Ref(Slice(F32)) -> NamedExternref("Float32Array")`.
                const ret = getArrayF32FromWasm0(arg0, arg1);
                return ret;
            },
            __wbindgen_cast_0000000000000014: function(arg0, arg1) {
                // Cast intrinsic for `Ref(Slice(I16)) -> NamedExternref("Int16Array")`.
                const ret = getArrayI16FromWasm0(arg0, arg1);
                return ret;
            },
            __wbindgen_cast_0000000000000015: function(arg0, arg1) {
                // Cast intrinsic for `Ref(Slice(I32)) -> NamedExternref("Int32Array")`.
                const ret = getArrayI32FromWasm0(arg0, arg1);
                return ret;
            },
            __wbindgen_cast_0000000000000016: function(arg0, arg1) {
                // Cast intrinsic for `Ref(Slice(I8)) -> NamedExternref("Int8Array")`.
                const ret = getArrayI8FromWasm0(arg0, arg1);
                return ret;
            },
            __wbindgen_cast_0000000000000017: function(arg0, arg1) {
                // Cast intrinsic for `Ref(Slice(U16)) -> NamedExternref("Uint16Array")`.
                const ret = getArrayU16FromWasm0(arg0, arg1);
                return ret;
            },
            __wbindgen_cast_0000000000000018: function(arg0, arg1) {
                // Cast intrinsic for `Ref(Slice(U32)) -> NamedExternref("Uint32Array")`.
                const ret = getArrayU32FromWasm0(arg0, arg1);
                return ret;
            },
            __wbindgen_cast_0000000000000019: function(arg0, arg1) {
                // Cast intrinsic for `Ref(Slice(U8)) -> NamedExternref("Uint8Array")`.
                const ret = getArrayU8FromWasm0(arg0, arg1);
                return ret;
            },
            __wbindgen_cast_000000000000001a: function(arg0, arg1) {
                // Cast intrinsic for `Ref(String) -> Externref`.
                const ret = getStringFromWasm0(arg0, arg1);
                return ret;
            },
            __wbindgen_cast_000000000000001b: function(arg0, arg1) {
                var v0 = getArrayU8FromWasm0(arg0, arg1).slice();
                wasm.__wbindgen_free(arg0, arg1 * 1, 1);
                // Cast intrinsic for `Vector(U8) -> Externref`.
                const ret = v0;
                return ret;
            },
            __wbindgen_init_externref_table: function() {
                const table = wasm.__wbindgen_externrefs;
                const offset = table.grow(4);
                table.set(0, undefined);
                table.set(offset + 0, undefined);
                table.set(offset + 1, null);
                table.set(offset + 2, true);
                table.set(offset + 3, false);
            },
        };
        return {
            __proto__: null,
            "./re_viewer_bg.js": import0,
        };
    }

    function wasm_bindgen__convert__closures_____invoke__ha5a90c0ae8ed2257(arg0, arg1) {
        wasm.wasm_bindgen__convert__closures_____invoke__ha5a90c0ae8ed2257(arg0, arg1);
    }

    function wasm_bindgen__convert__closures_____invoke__h5906433b3b84f0a2(arg0, arg1) {
        wasm.wasm_bindgen__convert__closures_____invoke__h5906433b3b84f0a2(arg0, arg1);
    }

    function wasm_bindgen__convert__closures_____invoke__h10a72af867dc4fc9(arg0, arg1) {
        wasm.wasm_bindgen__convert__closures_____invoke__h10a72af867dc4fc9(arg0, arg1);
    }

    function wasm_bindgen__convert__closures_____invoke__h5532da4c0e334d68(arg0, arg1) {
        const ret = wasm.wasm_bindgen__convert__closures_____invoke__h5532da4c0e334d68(arg0, arg1);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }

    function wasm_bindgen__convert__closures_____invoke__h764f62e2e9f0b28a(arg0, arg1, arg2) {
        wasm.wasm_bindgen__convert__closures_____invoke__h764f62e2e9f0b28a(arg0, arg1, arg2);
    }

    function wasm_bindgen__convert__closures_____invoke__h1b8e70bf81932a72(arg0, arg1, arg2) {
        wasm.wasm_bindgen__convert__closures_____invoke__h1b8e70bf81932a72(arg0, arg1, arg2);
    }

    function wasm_bindgen__convert__closures_____invoke__h04afcae3e0839798(arg0, arg1, arg2) {
        wasm.wasm_bindgen__convert__closures_____invoke__h04afcae3e0839798(arg0, arg1, arg2);
    }

    function wasm_bindgen__convert__closures_____invoke__h1b8e70bf81932a72_4(arg0, arg1, arg2) {
        wasm.wasm_bindgen__convert__closures_____invoke__h1b8e70bf81932a72_4(arg0, arg1, arg2);
    }

    function wasm_bindgen__convert__closures_____invoke__h991044b12b207aeb(arg0, arg1, arg2) {
        wasm.wasm_bindgen__convert__closures_____invoke__h991044b12b207aeb(arg0, arg1, arg2);
    }

    function wasm_bindgen__convert__closures_____invoke__ha617783b6c8d7033(arg0, arg1, arg2) {
        wasm.wasm_bindgen__convert__closures_____invoke__ha617783b6c8d7033(arg0, arg1, arg2);
    }

    function wasm_bindgen__convert__closures_____invoke__h04afcae3e0839798_9(arg0, arg1, arg2) {
        wasm.wasm_bindgen__convert__closures_____invoke__h04afcae3e0839798_9(arg0, arg1, arg2);
    }

    function wasm_bindgen__convert__closures_____invoke__hf5ab2b0e699d4375(arg0, arg1, arg2) {
        const ret = wasm.wasm_bindgen__convert__closures_____invoke__hf5ab2b0e699d4375(arg0, arg1, arg2);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }

    function wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3(arg0, arg1, arg2) {
        const ret = wasm.wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3(arg0, arg1, arg2);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }

    function wasm_bindgen__convert__closures_____invoke__h5a4a279089dfc290(arg0, arg1, arg2) {
        const ret = wasm.wasm_bindgen__convert__closures_____invoke__h5a4a279089dfc290(arg0, arg1, arg2);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }

    function wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3_10(arg0, arg1, arg2) {
        const ret = wasm.wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3_10(arg0, arg1, arg2);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }

    function wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3_11(arg0, arg1, arg2) {
        const ret = wasm.wasm_bindgen__convert__closures_____invoke__h52e74acfe7eba3a3_11(arg0, arg1, arg2);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }

    function wasm_bindgen__convert__closures_____invoke__hb3308f9470298f68(arg0, arg1, arg2) {
        const ret = wasm.wasm_bindgen__convert__closures_____invoke__hb3308f9470298f68(arg0, arg1, arg2);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }

    function wasm_bindgen__convert__closures_____invoke__h10b6862cecdf1332(arg0, arg1, arg2, arg3) {
        wasm.wasm_bindgen__convert__closures_____invoke__h10b6862cecdf1332(arg0, arg1, arg2, arg3);
    }


    const __wbindgen_enum_CodecState = ["unconfigured", "configured", "closed"];


    const __wbindgen_enum_EncodedVideoChunkType = ["key", "delta"];


    const __wbindgen_enum_GpuAddressMode = ["clamp-to-edge", "repeat", "mirror-repeat"];


    const __wbindgen_enum_GpuAutoLayoutMode = ["auto"];


    const __wbindgen_enum_GpuBlendFactor = ["zero", "one", "src", "one-minus-src", "src-alpha", "one-minus-src-alpha", "dst", "one-minus-dst", "dst-alpha", "one-minus-dst-alpha", "src-alpha-saturated", "constant", "one-minus-constant", "src1", "one-minus-src1", "src1-alpha", "one-minus-src1-alpha"];


    const __wbindgen_enum_GpuBlendOperation = ["add", "subtract", "reverse-subtract", "min", "max"];


    const __wbindgen_enum_GpuBufferBindingType = ["uniform", "storage", "read-only-storage"];


    const __wbindgen_enum_GpuCanvasAlphaMode = ["opaque", "premultiplied"];


    const __wbindgen_enum_GpuCanvasToneMappingMode = ["standard", "extended"];


    const __wbindgen_enum_GpuCompareFunction = ["never", "less", "equal", "less-equal", "greater", "not-equal", "greater-equal", "always"];


    const __wbindgen_enum_GpuCullMode = ["none", "front", "back"];


    const __wbindgen_enum_GpuFilterMode = ["nearest", "linear"];


    const __wbindgen_enum_GpuFrontFace = ["ccw", "cw"];


    const __wbindgen_enum_GpuIndexFormat = ["uint16", "uint32"];


    const __wbindgen_enum_GpuLoadOp = ["load", "clear"];


    const __wbindgen_enum_GpuMipmapFilterMode = ["nearest", "linear"];


    const __wbindgen_enum_GpuPowerPreference = ["low-power", "high-performance"];


    const __wbindgen_enum_GpuPrimitiveTopology = ["point-list", "line-list", "line-strip", "triangle-list", "triangle-strip"];


    const __wbindgen_enum_GpuSamplerBindingType = ["filtering", "non-filtering", "comparison"];


    const __wbindgen_enum_GpuStencilOperation = ["keep", "zero", "replace", "invert", "increment-clamp", "decrement-clamp", "increment-wrap", "decrement-wrap"];


    const __wbindgen_enum_GpuStorageTextureAccess = ["write-only", "read-only", "read-write"];


    const __wbindgen_enum_GpuStoreOp = ["store", "discard"];


    const __wbindgen_enum_GpuTextureAspect = ["all", "stencil-only", "depth-only"];


    const __wbindgen_enum_GpuTextureDimension = ["1d", "2d", "3d"];


    const __wbindgen_enum_GpuTextureFormat = ["r8unorm", "r8snorm", "r8uint", "r8sint", "r16unorm", "r16snorm", "r16uint", "r16sint", "r16float", "rg8unorm", "rg8snorm", "rg8uint", "rg8sint", "r32uint", "r32sint", "r32float", "rg16unorm", "rg16snorm", "rg16uint", "rg16sint", "rg16float", "rgba8unorm", "rgba8unorm-srgb", "rgba8snorm", "rgba8uint", "rgba8sint", "bgra8unorm", "bgra8unorm-srgb", "rgb9e5ufloat", "rgb10a2uint", "rgb10a2unorm", "rg11b10ufloat", "rg32uint", "rg32sint", "rg32float", "rgba16unorm", "rgba16snorm", "rgba16uint", "rgba16sint", "rgba16float", "rgba32uint", "rgba32sint", "rgba32float", "stencil8", "depth16unorm", "depth24plus", "depth24plus-stencil8", "depth32float", "depth32float-stencil8", "bc1-rgba-unorm", "bc1-rgba-unorm-srgb", "bc2-rgba-unorm", "bc2-rgba-unorm-srgb", "bc3-rgba-unorm", "bc3-rgba-unorm-srgb", "bc4-r-unorm", "bc4-r-snorm", "bc5-rg-unorm", "bc5-rg-snorm", "bc6h-rgb-ufloat", "bc6h-rgb-float", "bc7-rgba-unorm", "bc7-rgba-unorm-srgb", "etc2-rgb8unorm", "etc2-rgb8unorm-srgb", "etc2-rgb8a1unorm", "etc2-rgb8a1unorm-srgb", "etc2-rgba8unorm", "etc2-rgba8unorm-srgb", "eac-r11unorm", "eac-r11snorm", "eac-rg11unorm", "eac-rg11snorm", "astc-4x4-unorm", "astc-4x4-unorm-srgb", "astc-5x4-unorm", "astc-5x4-unorm-srgb", "astc-5x5-unorm", "astc-5x5-unorm-srgb", "astc-6x5-unorm", "astc-6x5-unorm-srgb", "astc-6x6-unorm", "astc-6x6-unorm-srgb", "astc-8x5-unorm", "astc-8x5-unorm-srgb", "astc-8x6-unorm", "astc-8x6-unorm-srgb", "astc-8x8-unorm", "astc-8x8-unorm-srgb", "astc-10x5-unorm", "astc-10x5-unorm-srgb", "astc-10x6-unorm", "astc-10x6-unorm-srgb", "astc-10x8-unorm", "astc-10x8-unorm-srgb", "astc-10x10-unorm", "astc-10x10-unorm-srgb", "astc-12x10-unorm", "astc-12x10-unorm-srgb", "astc-12x12-unorm", "astc-12x12-unorm-srgb"];


    const __wbindgen_enum_GpuTextureSampleType = ["float", "unfilterable-float", "depth", "sint", "uint"];


    const __wbindgen_enum_GpuTextureViewDimension = ["1d", "2d", "2d-array", "cube", "cube-array", "3d"];


    const __wbindgen_enum_GpuVertexFormat = ["uint8", "uint8x2", "uint8x4", "sint8", "sint8x2", "sint8x4", "unorm8", "unorm8x2", "unorm8x4", "snorm8", "snorm8x2", "snorm8x4", "uint16", "uint16x2", "uint16x4", "sint16", "sint16x2", "sint16x4", "unorm16", "unorm16x2", "unorm16x4", "snorm16", "snorm16x2", "snorm16x4", "float16", "float16x2", "float16x4", "float32", "float32x2", "float32x3", "float32x4", "uint32", "uint32x2", "uint32x3", "uint32x4", "sint32", "sint32x2", "sint32x3", "sint32x4", "unorm10-10-10-2", "unorm8x4-bgra"];


    const __wbindgen_enum_GpuVertexStepMode = ["vertex", "instance"];


    const __wbindgen_enum_HardwareAcceleration = ["no-preference", "prefer-hardware", "prefer-software"];


    const __wbindgen_enum_ReadableStreamType = ["bytes"];


    const __wbindgen_enum_ReferrerPolicy = ["", "no-referrer", "no-referrer-when-downgrade", "origin", "origin-when-cross-origin", "unsafe-url", "same-origin", "strict-origin", "strict-origin-when-cross-origin"];


    const __wbindgen_enum_RequestCache = ["default", "no-store", "reload", "no-cache", "force-cache", "only-if-cached"];


    const __wbindgen_enum_RequestCredentials = ["omit", "same-origin", "include"];


    const __wbindgen_enum_RequestMode = ["same-origin", "no-cors", "cors", "navigate"];


    const __wbindgen_enum_RequestRedirect = ["follow", "error", "manual"];


    const __wbindgen_enum_ResizeObserverBoxOptions = ["border-box", "content-box", "device-pixel-content-box"];
    const IntoUnderlyingByteSourceFinalization = (typeof FinalizationRegistry === 'undefined')
        ? { register: () => {}, unregister: () => {} }
        : new FinalizationRegistry(ptr => wasm.__wbg_intounderlyingbytesource_free(ptr, 1));
    const IntoUnderlyingSinkFinalization = (typeof FinalizationRegistry === 'undefined')
        ? { register: () => {}, unregister: () => {} }
        : new FinalizationRegistry(ptr => wasm.__wbg_intounderlyingsink_free(ptr, 1));
    const IntoUnderlyingSourceFinalization = (typeof FinalizationRegistry === 'undefined')
        ? { register: () => {}, unregister: () => {} }
        : new FinalizationRegistry(ptr => wasm.__wbg_intounderlyingsource_free(ptr, 1));
    const WebHandleFinalization = (typeof FinalizationRegistry === 'undefined')
        ? { register: () => {}, unregister: () => {} }
        : new FinalizationRegistry(ptr => wasm.__wbg_webhandle_free(ptr, 1));

    function addToExternrefTable0(obj) {
        const idx = wasm.__externref_table_alloc();
        wasm.__wbindgen_externrefs.set(idx, obj);
        return idx;
    }

    const CLOSURE_DTORS = (typeof FinalizationRegistry === 'undefined')
        ? { register: () => {}, unregister: () => {} }
        : new FinalizationRegistry(state => {
        if (wasm) wasm.__wbindgen_destroy_closure(state.a, state.b);
    });

    function debugString(val) {
        // primitive types
        const type = typeof val;
        if (type == 'number' || type == 'boolean' || val == null) {
            return  `${val}`;
        }
        if (type == 'string') {
            return `"${val}"`;
        }
        if (type == 'symbol') {
            const description = val.description;
            if (description == null) {
                return 'Symbol';
            } else {
                return `Symbol(${description})`;
            }
        }
        if (type == 'function') {
            const name = val.name;
            if (typeof name == 'string' && name.length > 0) {
                return `Function(${name})`;
            } else {
                return 'Function';
            }
        }
        // objects
        if (Array.isArray(val)) {
            const length = val.length;
            let debug = '[';
            if (length > 0) {
                debug += debugString(val[0]);
            }
            for(let i = 1; i < length; i++) {
                debug += ', ' + debugString(val[i]);
            }
            debug += ']';
            return debug;
        }
        // Test for built-in
        const builtInMatches = /\[object ([^\]]+)\]/.exec(toString.call(val));
        let className;
        if (builtInMatches && builtInMatches.length > 1) {
            className = builtInMatches[1];
        } else {
            // Failed to match the standard '[object ClassName]'
            return toString.call(val);
        }
        if (className == 'Object') {
            // we're a user defined class or Object
            // JSON.stringify avoids problems with cycles, and is generally much
            // easier than looping through ownProperties of `val`.
            try {
                return 'Object(' + JSON.stringify(val) + ')';
            } catch (_) {
                return 'Object';
            }
        }
        // errors
        if (val instanceof Error) {
            return `${val.name}: ${val.message}\n${val.stack}`;
        }
        // TODO we could test for more things here, like `Set`s and `Map`s.
        return className;
    }

    function getArrayF32FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getFloat32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
    }

    function getArrayI16FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getInt16ArrayMemory0().subarray(ptr / 2, ptr / 2 + len);
    }

    function getArrayI32FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getInt32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
    }

    function getArrayI8FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getInt8ArrayMemory0().subarray(ptr / 1, ptr / 1 + len);
    }

    function getArrayJsValueViewFromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        const mem = getDataViewMemory0();
        const result = [];
        for (let i = ptr; i < ptr + 4 * len; i += 4) {
            result.push(wasm.__wbindgen_externrefs.get(mem.getUint32(i, true)));
        }
        return result;
    }

    function getArrayU16FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getUint16ArrayMemory0().subarray(ptr / 2, ptr / 2 + len);
    }

    function getArrayU32FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getUint32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
    }

    function getArrayU8FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getUint8ArrayMemory0().subarray(ptr / 1, ptr / 1 + len);
    }

    let cachedDataViewMemory0 = null;
    function getDataViewMemory0() {
        if (cachedDataViewMemory0 === null || cachedDataViewMemory0.buffer.detached === true || (cachedDataViewMemory0.buffer.detached === undefined && cachedDataViewMemory0.buffer !== wasm.memory.buffer)) {
            cachedDataViewMemory0 = new DataView(wasm.memory.buffer);
        }
        return cachedDataViewMemory0;
    }

    let cachedFloat32ArrayMemory0 = null;
    function getFloat32ArrayMemory0() {
        if (cachedFloat32ArrayMemory0 === null || cachedFloat32ArrayMemory0.byteLength === 0) {
            cachedFloat32ArrayMemory0 = new Float32Array(wasm.memory.buffer);
        }
        return cachedFloat32ArrayMemory0;
    }

    let cachedInt16ArrayMemory0 = null;
    function getInt16ArrayMemory0() {
        if (cachedInt16ArrayMemory0 === null || cachedInt16ArrayMemory0.byteLength === 0) {
            cachedInt16ArrayMemory0 = new Int16Array(wasm.memory.buffer);
        }
        return cachedInt16ArrayMemory0;
    }

    let cachedInt32ArrayMemory0 = null;
    function getInt32ArrayMemory0() {
        if (cachedInt32ArrayMemory0 === null || cachedInt32ArrayMemory0.byteLength === 0) {
            cachedInt32ArrayMemory0 = new Int32Array(wasm.memory.buffer);
        }
        return cachedInt32ArrayMemory0;
    }

    let cachedInt8ArrayMemory0 = null;
    function getInt8ArrayMemory0() {
        if (cachedInt8ArrayMemory0 === null || cachedInt8ArrayMemory0.byteLength === 0) {
            cachedInt8ArrayMemory0 = new Int8Array(wasm.memory.buffer);
        }
        return cachedInt8ArrayMemory0;
    }

    function getStringFromWasm0(ptr, len) {
        return decodeText(ptr >>> 0, len);
    }

    let cachedUint16ArrayMemory0 = null;
    function getUint16ArrayMemory0() {
        if (cachedUint16ArrayMemory0 === null || cachedUint16ArrayMemory0.byteLength === 0) {
            cachedUint16ArrayMemory0 = new Uint16Array(wasm.memory.buffer);
        }
        return cachedUint16ArrayMemory0;
    }

    let cachedUint32ArrayMemory0 = null;
    function getUint32ArrayMemory0() {
        if (cachedUint32ArrayMemory0 === null || cachedUint32ArrayMemory0.byteLength === 0) {
            cachedUint32ArrayMemory0 = new Uint32Array(wasm.memory.buffer);
        }
        return cachedUint32ArrayMemory0;
    }

    let cachedUint8ArrayMemory0 = null;
    function getUint8ArrayMemory0() {
        if (cachedUint8ArrayMemory0 === null || cachedUint8ArrayMemory0.byteLength === 0) {
            cachedUint8ArrayMemory0 = new Uint8Array(wasm.memory.buffer);
        }
        return cachedUint8ArrayMemory0;
    }

    function handleError(f, args) {
        try {
            return f.apply(this, args);
        } catch (e) {
            const idx = addToExternrefTable0(e);
            wasm.__wbindgen_exn_store(idx);
        }
    }

    function isLikeNone(x) {
        return x === undefined || x === null;
    }

    function makeMutClosure(arg0, arg1, f) {
        const state = { a: arg0, b: arg1, cnt: 1 };
        const real = (...args) => {
            state.cnt++;
            const a = state.a;
            state.a = 0;
            try {
                if (!wasm) return;
                return f(a, state.b, ...args);
            } finally {
                state.a = a;
                real._wbg_cb_unref();
            }
        };
        real._wbg_cb_unref = () => {
            if (--state.cnt === 0) {
                if (wasm) wasm.__wbindgen_destroy_closure(state.a, state.b);
                state.a = 0;
                CLOSURE_DTORS.unregister(state);
            }
        };
        CLOSURE_DTORS.register(real, state, state);
        return real;
    }

    function passArray8ToWasm0(arg, malloc) {
        const ptr = malloc(arg.length * 1, 1) >>> 0;
        getUint8ArrayMemory0().set(arg, ptr / 1);
        WASM_VECTOR_LEN = arg.length;
        return ptr;
    }

    function passArrayJsValueToWasm0(array, malloc) {
        const ptr = malloc(array.length * 4, 4) >>> 0;
        for (let i = 0; i < array.length; i++) {
            const add = addToExternrefTable0(array[i]);
            getDataViewMemory0().setUint32(ptr + 4 * i, add, true);
        }
        WASM_VECTOR_LEN = array.length;
        return ptr;
    }

    function passStringToWasm0(arg, malloc, realloc) {
        if (realloc === undefined) {
            const buf = cachedTextEncoder.encode(arg);
            const ptr = malloc(buf.length, 1) >>> 0;
            getUint8ArrayMemory0().subarray(ptr, ptr + buf.length).set(buf);
            WASM_VECTOR_LEN = buf.length;
            return ptr;
        }

        let len = arg.length;
        let ptr = malloc(len, 1) >>> 0;

        const mem = getUint8ArrayMemory0();

        let offset = 0;

        for (; offset < len; offset++) {
            const code = arg.charCodeAt(offset);
            if (code > 0x7F) break;
            mem[ptr + offset] = code;
        }
        if (offset !== len) {
            if (offset !== 0) {
                arg = arg.slice(offset);
            }
            ptr = realloc(ptr, len, len = offset + arg.length * 3, 1) >>> 0;
            const view = getUint8ArrayMemory0().subarray(ptr + offset, ptr + len);
            const ret = cachedTextEncoder.encodeInto(arg, view);

            offset += ret.written;
            ptr = realloc(ptr, len, offset, 1) >>> 0;
        }

        WASM_VECTOR_LEN = offset;
        return ptr;
    }

    function takeFromExternrefTable0(idx) {
        const value = wasm.__wbindgen_externrefs.get(idx);
        wasm.__externref_table_dealloc(idx);
        return value;
    }

    let cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
    cachedTextDecoder.decode();
    function decodeText(ptr, len) {
        return cachedTextDecoder.decode(getUint8ArrayMemory0().subarray(ptr, ptr + len));
    }

    const cachedTextEncoder = new TextEncoder();

    if (!('encodeInto' in cachedTextEncoder)) {
        cachedTextEncoder.encodeInto = function (arg, view) {
            const buf = cachedTextEncoder.encode(arg);
            view.set(buf);
            return {
                read: arg.length,
                written: buf.length
            };
        };
    }

    let WASM_VECTOR_LEN = 0;

    let wasmModule, wasmInstance, wasm;
    function __wbg_finalize_init(instance, module) {
        wasmInstance = instance;
        wasm = instance.exports;
        wasmModule = module;
        cachedDataViewMemory0 = null;
        cachedFloat32ArrayMemory0 = null;
        cachedInt16ArrayMemory0 = null;
        cachedInt32ArrayMemory0 = null;
        cachedInt8ArrayMemory0 = null;
        cachedUint16ArrayMemory0 = null;
        cachedUint32ArrayMemory0 = null;
        cachedUint8ArrayMemory0 = null;
        wasm.__wbindgen_start();
        return wasm;
    }

    async function __wbg_load(module, imports) {
        if (typeof Response === 'function' && module instanceof Response) {
            if (typeof WebAssembly.instantiateStreaming === 'function') {
                try {
                    return await WebAssembly.instantiateStreaming(module, imports);
                } catch (e) {
                    const validResponse = module.ok && expectedResponseType(module.type);

                    if (validResponse && module.headers.get('Content-Type') !== 'application/wasm') {
                        console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve Wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);

                    } else { throw e; }
                }
            }

            const bytes = await module.arrayBuffer();
            return await WebAssembly.instantiate(bytes, imports);
        } else {
            const instance = await WebAssembly.instantiate(module, imports);

            if (instance instanceof WebAssembly.Instance) {
                return { instance, module };
            } else {
                return instance;
            }
        }

        function expectedResponseType(type) {
            switch (type) {
                case 'basic': case 'cors': case 'default': return true;
            }
            return false;
        }
    }

    function initSync(module) {
        if (wasm !== undefined) return wasm;


        if (module !== undefined) {
            if (Object.getPrototypeOf(module) === Object.prototype) {
                ({module} = module)
            } else {
                console.warn('using deprecated parameters for `initSync()`; pass a single object instead')
            }
        }

        const imports = __wbg_get_imports();
        if (!(module instanceof WebAssembly.Module)) {
            module = new WebAssembly.Module(module);
        }
        const instance = new WebAssembly.Instance(module, imports);
        return __wbg_finalize_init(instance, module);
    }

    async function __wbg_init(module_or_path) {
        if (wasm !== undefined) return wasm;


        if (module_or_path !== undefined) {
            if (Object.getPrototypeOf(module_or_path) === Object.prototype) {
                ({module_or_path} = module_or_path)
            } else {
                console.warn('using deprecated parameters for the initialization function; pass a single object instead')
            }
        }


        const imports = __wbg_get_imports();

        if (typeof module_or_path === 'string' || (typeof Request === 'function' && module_or_path instanceof Request) || (typeof URL === 'function' && module_or_path instanceof URL)) {
            module_or_path = fetch(module_or_path);
        }

        const { instance, module } = await __wbg_load(await module_or_path, imports);

        return __wbg_finalize_init(instance, module);
    }




function deinit() {
  __wbg_init.__wbindgen_wasm_module = null;
  wasmModule = null;
  wasm = null;
  cachedDataViewMemory0 = null;
  cachedFloat32ArrayMemory0 = null;
  cachedInt16ArrayMemory0 = null;
  cachedInt32ArrayMemory0 = null;
  cachedInt8ArrayMemory0 = null;
  cachedUint16ArrayMemory0 = null;
  cachedUint32ArrayMemory0 = null;
  cachedUint8ArrayMemory0 = null;
}

return Object.assign(__wbg_init, { initSync, deinit }, exports);
}

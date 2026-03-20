// 微信视频号下载助手 - JavaScript 注入脚本
// 参考 nobiyou/wx_channel 和 ltaoo/wx_channels_download 的实现
// 通过页面状态扫描提取视频元数据（标题、decodeKey、封面等）并发送到 VidFlow 后端

(function() {
    'use strict';

    // 防止重复注入
    if (window.__vidflow_injected__) return;
    window.__vidflow_injected__ = true;

    console.log('[VidFlow] 注入脚本已加载');

    const DEFAULT_PROXY_POST_PATH = '/__vidflow/channels/videos/inject';
    const PROXY_POST_PATH = (typeof window.__VIDFLOW_PROXY_POST_PATH__ === 'string' && window.__VIDFLOW_PROXY_POST_PATH__)
        ? window.__VIDFLOW_PROXY_POST_PATH__
        : DEFAULT_PROXY_POST_PATH;
    const PROXY_POST_URL = (window.location && window.location.origin)
        ? window.location.origin + PROXY_POST_PATH
        : ('https://channels.weixin.qq.com' + PROXY_POST_PATH);
    console.log('[VidFlow] PROXY_POST_URL:', PROXY_POST_URL);

    // 已提交的视频集合（避免重复提交）
    const submittedVideos = new Set();
    // 基于稳定视频 ID 的去重（不受 URL query 参数变化影响）
    const submittedVideoIds = {};  // stableId -> { timestamp, payload }
    // 全局节流：限制 bridge 请求频率
    var lastBridgeRequestTime = 0;
    var pendingBridgePayload = null;
    var pendingBridgeTimer = null;
    var BRIDGE_MIN_INTERVAL_MS = 3000;  // 同一视频最少间隔 3 秒
    var BRIDGE_GLOBAL_MIN_MS = 500;     // 全局最少间隔 500ms

    /**
     * 从 URL 中提取稳定的视频标识符
     * 优先使用 encfilekey（CDN 寻址 key），其次用 URL path
     */
    function extractStableVideoId(url) {
        if (!url) return null;
        try {
            // 提取 encfilekey 参数（微信视频 CDN 特征）
            var encMatch = url.match(/[?&]encfilekey=([^&]+)/);
            if (encMatch) return 'enc:' + encMatch[1].substring(0, 40);
            // 提取 URL path 部分作为标识（去掉 query）
            var pathMatch = url.match(/^https?:\/\/[^?#]+/);
            if (pathMatch) return 'path:' + pathMatch[0].substring(0, 120);
        } catch (e) {}
        return null;
    }

    const wrappedWXContainers = new WeakSet();
    const wrappedWXEventBuses = new WeakSet();
    const wrappedWXMethods = new WeakSet();
    const WX_API_METHOD_NAMES = {
        findergetcommentdetail: true,
        findergetrecommend: true,
        finderpcflow: true,
        finderuserpage: true,
        finderliveuserpage: true,
        findersearch: true,
        finderpcsearch: true,
        finderstream: true,
        findergetfeeddetail: true,
        findergetfollowlist: true,
        finderlivepage: true,
        finderliveuserpage: true,
        set_feed: true,
        setfeed: true,
        set_live_feed: true,
        setlivefeed: true,
        format_feed: true,
        formatfeed: true
    };
    const WX_FEED_EVENT_NAMES = {
        feed: true,
        pcflowloaded: true,
        categoryfeedsloaded: true,
        recommendfeedsloaded: true,
        userfeedsloaded: true,
        userlivereplayloaded: true,
        liveuserfeedsloaded: true,
        searchresultloaded: true,
        interactionedfeedsloaded: true,
        onfeedprofileloaded: true,
        feedprofileloaded: true,
        onliveprofileloaded: true,
        liveprofileloaded: true,
        gotonextfeed: true,
        gotoprevfeed: true,
        homefeedchanged: true
    };
    const WX_RUNTIME_EVENT_NAMES = {
        apiloaded: true,
        utilsloaded: true,
        init: true
    };

    // =========================================
    // 工具函数
    // =========================================

    // 显示状态消息
    function showStatus(message, duration) {
        duration = duration || 3000;
        try {
            var statusDiv = document.createElement('div');
            statusDiv.style.cssText = 'position:fixed;top:20px;right:20px;padding:12px 20px;' +
                'background:rgba(0,0,0,0.85);color:white;border-radius:8px;font-size:14px;' +
                'z-index:999999;box-shadow:0 4px 12px rgba(0,0,0,0.3);' +
                'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;';
            statusDiv.textContent = message;
            document.body.appendChild(statusDiv);
            setTimeout(function() { statusDiv.remove(); }, duration);
        } catch (e) {
            // 忽略 UI 错误
        }
    }

    // 判断 URL 是否是微信视频号 API
    function isWeChatAPI(url) {
        if (!url || typeof url !== 'string') return false;
        var lowerUrl = url.toLowerCase();
        var apiPatterns = [
            'finderpcflow',
            'findergetcommentdetail',
            'finderuserpage',
            'finderliveuserpage',
            'findergetrecommend',
            'finderpcsearch',
            'findersearch',
            'finderstream',
            'finderobject',
            'finderdetail',
            'finderassistant',
            'mmfinderassistant',
            'cgi-bin/mmfinderassistant'
        ];
        for (var i = 0; i < apiPatterns.length; i++) {
            if (lowerUrl.indexOf(apiPatterns[i]) !== -1) return true;
        }

        try {
            var parsed = new URL(url, window.location.href);
            var host = (parsed.hostname || '').toLowerCase();
            var path = (parsed.pathname || '').toLowerCase();
            if (/\.(?:css|js|mjs|map|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot)$/.test(path)) {
                return false;
            }
            if (host.indexOf('channels.weixin.qq.com') !== -1) {
                if (
                    path.indexOf('/cgi-bin/') !== -1 ||
                    path.indexOf('/web/') !== -1 ||
                    path.indexOf('/finder') !== -1
                ) {
                    return true;
                }
            }
            if ((host.indexOf('weixin.qq.com') !== -1 || host.indexOf('qq.com') !== -1) && path.indexOf('mmfinderassistant') !== -1) {
                return true;
            }
        } catch (e) {
            // ignore URL parse failures
        }

        return false;
    }

    // 判断 URL 是否是微信域名
    function isWeChatDomain(url) {
        if (!url || typeof url !== 'string') return false;
        return url.indexOf('weixin.qq.com') !== -1 ||
               url.indexOf('wechat.com') !== -1 ||
               url.indexOf('qq.com') !== -1;
    }

    function normalizeUrlValue(value) {
        if (!value) return null;
        if (Array.isArray(value)) {
            for (var i = 0; i < value.length; i++) {
                var nested = normalizeUrlValue(value[i]);
                if (nested) return nested;
            }
            return null;
        }
        if (typeof value === 'object') {
            return normalizeUrlValue(
                value.url || value.src || value.playUrl || value.play_url ||
                value.videoUrl || value.video_url || value.downloadUrl || value.download_url
            );
        }
        if (typeof value !== 'string') return null;
        var text = value
            .replace(/\\u0026/g, '&')
            .replace(/&amp;/gi, '&')
            .replace(/&quot;/gi, '"')
            .replace(/&#34;/gi, '"')
            .replace(/&#39;/gi, "'")
            .replace(/&#x27;/gi, "'")
            .replace(/\\\//g, '/')
            .trim();
        if (!text) return null;
        text = text
            .replace(/^['"(]+/, '')
            .replace(/(?:&quot;|&#34;).*$/i, '')
            .replace(/["')\];\s]+$/, '');
        var matchedUrl = text.match(/(?:(?:https?:)?\/\/)?(?:finder\.video\.qq\.com|findervideodownload\.video\.qq\.com|(?:[\w-]+\.)?tc\.qq\.com)\/[^"'\\\s<>]+/i);
        if (matchedUrl && matchedUrl[0]) {
            text = matchedUrl[0];
        }
        if (/^(?:finder\.video\.qq\.com|findervideodownload\.video\.qq\.com|(?:[\w-]+\.)?tc\.qq\.com)\//i.test(text)) {
            text = 'https://' + text.replace(/^\/+/, '');
        }
        if (text.indexOf('finder.video.qq.com') !== -1 ||
            text.indexOf('findervideodownload.video.qq.com') !== -1 ||
            text.indexOf('tc.qq.com') !== -1 ||
            text.indexOf('/stodownload') !== -1) {
            // 排除缩略图 URL：/20304/ 和 /20350/ 是图片路径，带 picformat 参数也是缩略图
            if (/\/20304\/stodownload|\/20350\/stodownload|[?&]picformat=|[?&]wxampicformat=/.test(text)) {
                return null;
            }
            return text;
        }
        return null;
    }

    function normalizeAssetUrl(value) {
        if (value === null || value === undefined) return null;

        if (Array.isArray(value)) {
            for (var i = 0; i < value.length; i++) {
                var nestedArrayAsset = normalizeAssetUrl(value[i]);
                if (nestedArrayAsset) return nestedArrayAsset;
            }
            return null;
        }

        if (value && typeof value === 'object') {
            var assetKeys = [
                'url', 'src', 'thumbUrl', 'thumb_url', 'thumb', 'cover', 'coverUrl', 'cover_url',
                'coverImage', 'cover_image', 'coverImg', 'cover_img', 'coverImgUrl', 'cover_img_url',
                'poster', 'posterUrl', 'poster_url', 'imageUrl', 'image_url', 'headUrl', 'head_url', 'value'
            ];
            for (var keyIndex = 0; keyIndex < assetKeys.length; keyIndex++) {
                var assetKey = assetKeys[keyIndex];
                if (value[assetKey] !== undefined && value[assetKey] !== null) {
                    var nestedAsset = normalizeAssetUrl(value[assetKey]);
                    if (nestedAsset) return nestedAsset;
                }
            }
            var objectKeys = Object.keys(value);
            for (var objectIndex = 0; objectIndex < objectKeys.length; objectIndex++) {
                var nestedObjectAsset = normalizeAssetUrl(value[objectKeys[objectIndex]]);
                if (nestedObjectAsset) return nestedObjectAsset;
            }
            return null;
        }

        if (typeof value !== 'string') return null;
        var text = value
            .replace(/\\u0026/g, '&')
            .replace(/\\\//g, '/')
            .trim();
        if (!text) return null;
        if (text.indexOf('//') === 0) {
            return 'https:' + text;
        }
        if (text.indexOf('http://') === 0 || text.indexOf('https://') === 0) {
            return text;
        }
        if (
            /^res\.wx\.qq\.com\//i.test(text) ||
            /^(?:[^/]*(?:qpic|wx\.qlogo|wx\.qpic|qlogo)\.[^/]+)\//i.test(text)
        ) {
            return 'https://' + text.replace(/^\/+/, '');
        }
        return null;
    }

    function normalizeTextValue(value, maxDepth) {
        maxDepth = typeof maxDepth === 'number' ? maxDepth : 4;
        if (value === null || value === undefined) return null;

        if (typeof value === 'string') {
            var text = value.replace(/\s+/g, ' ').trim();
            return text || null;
        }

        if (typeof value === 'number') {
            if (!isFinite(value)) return null;
            return String(value);
        }

        if (typeof value === 'bigint') {
            return value.toString();
        }

        if (maxDepth <= 0) return null;

        if (Array.isArray(value)) {
            for (var i = 0; i < value.length; i++) {
                var nestedArrayValue = normalizeTextValue(value[i], maxDepth - 1);
                if (nestedArrayValue) return nestedArrayValue;
            }
            return null;
        }

        if (!value || typeof value !== 'object') return null;

        var preferredKeys = [
            'description', 'desc', 'title', 'content', 'contentDesc',
            'text', 'value', 'name', 'nickName', 'nickname'
        ];
        for (var keyIndex = 0; keyIndex < preferredKeys.length; keyIndex++) {
            var key = preferredKeys[keyIndex];
            if (value[key] !== undefined && value[key] !== null) {
                var nestedValue = normalizeTextValue(value[key], maxDepth - 1);
                if (nestedValue) return nestedValue;
            }
        }

        try {
            if (typeof value.toString === 'function' && value.toString !== Object.prototype.toString) {
                var stringified = String(value).replace(/\s+/g, ' ').trim();
                if (stringified && stringified !== '[object Object]') {
                    return stringified;
                }
            }
        } catch (e) {
            // ignore custom toString failures
        }

        return null;
    }

    function looksLikePlaceholderNonce(value) {
        if (!value || typeof value !== 'string') return false;
        var text = value.replace(/\s+/g, ' ').trim();
        if (!text) return false;
        if (/^pc-\d{8,}$/i.test(text)) return true;
        if (/^[0-9a-f]{16,64}$/i.test(text)) return true;
        return /^[A-Za-z0-9_-]{8,32}$/.test(text) && /\d/.test(text) && !/[\u4e00-\u9fff\s]/.test(text);
    }

    function looksLikeAssetTitle(value) {
        if (!value || typeof value !== 'string') return false;
        var text = value.replace(/\s+/g, ' ').trim();
        if (!text || !/^[\x00-\x7F]+$/.test(text)) return false;

        var matched = text.match(/^(?:(?:https?:)?\/\/)?(?:[\w.-]+\/)*([\w.-]+\.(?:js|css|svg|png|jpe?g|gif|webp|ico))$/i);
        if (!matched) return false;

        var basename = matched[1];
        var lower = basename.toLowerCase();
        if (basename.indexOf(' ') !== -1) return false;
        if (text.indexOf('/') !== -1 || text.indexOf('\\') !== -1) return true;
        if ((basename.match(/\./g) || []).length >= 2) return true;
        if (/(?:^|[._-])(index|main|app|vendor|runtime|bundle|chunk|publish|common|static)(?:[._-]|$)/i.test(lower)) {
            return true;
        }
        if (/[._-][0-9a-f]{6,}(?:[._-]|$)/i.test(lower)) return true;
        return /\d{3,}/.test(basename);
    }

    function looksLikeMetaAssignmentTitle(value) {
        if (!value || typeof value !== 'string') return false;
        var text = value.replace(/\s+/g, ' ').trim();
        if (!text || !/^[\x00-\x7F]+$/.test(text) || text.indexOf('=') === -1) return false;

        var assignmentPattern = /^([A-Za-z][\w-]{0,31})\s*=\s*([^\s,][^,]{0,64})$/;
        var assignments = text.split(/\s*,\s*/);
        if (assignments.length > 1) {
            for (var i = 0; i < assignments.length; i++) {
                if (!assignmentPattern.test(assignments[i])) return false;
            }
            return true;
        }

        var matched = text.match(assignmentPattern);
        if (!matched) return false;

        var lhs = matched[1].toLowerCase();
        var rhs = matched[2].toLowerCase();
        if (
            lhs === 'ie' ||
            lhs === 'charset' ||
            lhs === 'content' ||
            lhs === 'viewport' ||
            lhs === 'width' ||
            lhs === 'height' ||
            lhs === 'initial-scale' ||
            lhs === 'maximum-scale' ||
            lhs === 'minimum-scale' ||
            lhs === 'user-scalable'
        ) {
            return true;
        }
        return (
            (lhs === 'ie' && rhs === 'edge') ||
            (lhs === 'charset' && rhs === 'utf-8') ||
            (lhs === 'width' && rhs === 'device-width')
        );
    }

    function looksLikeJsExpressionTitle(value) {
        if (!value || typeof value !== 'string') return false;
        var text = value.replace(/\s+/g, ' ').trim();
        if (!text) return false;

        var lower = text.toLowerCase();
        var compactAscii = /^[\x00-\x7F]+$/.test(text) && text.indexOf(' ') === -1;
        if (/^(?:document|window|globalThis|self|this)\.[A-Za-z_$][\w$]*$/.test(text)) return true;
        if (compactAscii && /^\.?(?:concat|join|map|filter|slice)\([^)]*\)$/i.test(text)) return true;
        if (compactAscii && /^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+$/.test(text)) {
            var segments = lower.split('.');
            var suspiciousSegments = {
                objectnonceid: true,
                value: true,
                content: true,
                description: true,
                title: true,
                desc: true,
                nickname: true
            };
            if (segments.length >= 3) return true;
            for (var segmentIndex = 1; segmentIndex < segments.length; segmentIndex++) {
                if (suspiciousSegments[segments[segmentIndex]]) return true;
            }
        }
        if (
            compactAscii &&
            (
                lower.indexOf('document.') !== -1 ||
                lower.indexOf('window.') !== -1 ||
                lower.indexOf('queryselector') !== -1 ||
                lower.indexOf('getelementsby') !== -1 ||
                lower.indexOf('function(') !== -1 ||
                lower.indexOf('function ') !== -1 ||
                lower.indexOf('return ') !== -1 ||
                lower.indexOf('=>') !== -1
            )
        ) {
            return true;
        }
        if (compactAscii && /^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+\s*=\s*.+$/.test(text)) return true;
        if (compactAscii && /^[A-Za-z_$][\w$]*\s*=\s*(?:document|window|globalThis|self|this)\..+$/.test(text)) return true;
        return compactAscii && text.indexOf('.') !== -1 && /[()[\]]/.test(text);
    }

    function sanitizeTitleValue(value) {
        var text = normalizeTextValue(value);
        if (!text) return null;

        var normalized = text.replace(/\s+/g, ' ').trim();
        if (!normalized) return null;

        var lower = normalized.toLowerCase();
        if (normalized === '视频号' || normalized === '微信视频号') return null;
        if (/^channels_[A-Za-z0-9_-]{6,}$/i.test(normalized)) return null;
        if (lower === '_' || lower === '-' || lower === 'null' || lower === 'undefined' || lower === 'browser' || lower === 'ui') {
            return null;
        }
        if (/^(?:video\s+player(?:\s+is)?\s+loading|loading(?:\s+video(?:\s+player)?)?|video\s+loading)\.?$/i.test(lower)) return null;
        if (looksLikeMetaAssignmentTitle(normalized)) return null;
        if (/^[\x00-\x7F]+$/.test(normalized) && normalized.indexOf(' ') === -1 && /^[a-zA-Z_$][\w$]*\(.*\)$/.test(normalized)) {
            return null;
        }
        if (looksLikeAssetTitle(normalized)) return null;
        if (normalized.length === 1 && /^[\x00-\x7F]+$/.test(normalized) && !/^[A-Za-z0-9]$/.test(normalized)) return null;
        
        // 过滤对话框/无障碍/accessibility 噪声文本
        if (/^(?:beginning|end) of (?:dialog|modal)/i.test(lower)) return null;
        if (/escape will (?:cancel|close)/i.test(lower)) return null;
        if (/^(?:dialog|modal|overlay|popup|tooltip|menu)\b/i.test(lower)) return null;
        if (/\bmodal\s+window\b/i.test(lower)) return null;
        if (/\baria[_-]?label/i.test(lower)) return null;
        if (/^(?:loading|please wait|close|open|cancel|confirm|submit|ok|yes|no|back|next|previous|retry)\s*\.?$/i.test(lower)) return null;
        if (/^(?:share|copy|download|delete|edit|save|search|sign in|log in|log out|sign up)\s*\.?$/i.test(lower)) return null;
        // 过滤 "this is a ..." 开头的 accessibility 描述
        if (/^this\s+is\s+a\s+/i.test(lower)) return null;
        // 过滤设置/配置界面的英文 UI 指令文本
        if (/(?:restore|reset|revert)\s+(?:all\s+)?(?:settings|preferences|options|defaults)/i.test(lower)) return null;
        if (/(?:default|original)\s+(?:settings|values|configuration)/i.test(lower)) return null;
        if (/^(?:are you sure|do you want|would you like|this (?:action|operation|will))\b/i.test(lower)) return null;
        if (/^(?:click|tap|press|drag|swipe|scroll|select|choose|pick|enter|type)\s+(?:here|to|the|a|an)\b/i.test(lower)) return null;
        if (/^(?:powered by|copyright|all rights reserved|terms of|privacy policy|cookie)\b/i.test(lower)) return null;
        // 过滤纯英文且像 UI 指令的长句（含 "to" + 动词结构）
        if (/^[a-z\s,.'?!]+$/i.test(normalized) && normalized.length > 10 && /\b(?:to (?:the|your|this|all|its)|settings|preferences|options|default|restore|reset|enable|disable|allow|deny|accept|reject|dismiss)\b/i.test(lower)) return null;

        // 过滤纯 UI 词汇组合标题（如 "Close Modal Dialog"）
        var _uiWords = {
            'dialog':1, 'modal':1, 'overlay':1, 'popup':1, 'tooltip':1, 'menu':1,
            'loading':1, 'close':1, 'open':1, 'cancel':1, 'confirm':1, 'submit':1,
            'ok':1, 'yes':1, 'no':1, 'back':1, 'next':1, 'previous':1, 'retry':1,
            'share':1, 'copy':1, 'download':1, 'delete':1, 'edit':1, 'save':1,
            'search':1, 'button':1, 'icon':1, 'header':1, 'footer':1, 'sidebar':1,
            'navigation':1, 'content':1, 'wrapper':1, 'container':1, 'panel':1,
            'video':1, 'player':1, 'audio':1, 'media':1, 'controls':1, 'progress':1,
            'seekbar':1, 'volume':1, 'fullscreen':1, 'play':1, 'pause':1, 'mute':1,
            'unmute':1, 'settings':1, 'subtitles':1, 'captions':1, 'quality':1
        };
        var titleWords = lower.replace(/\./g, '').split(/\s+/).filter(function(w) { return w; });
        if (titleWords.length > 0 && titleWords.every(function(w) { return _uiWords.hasOwnProperty(w); })) return null;

        // 过滤常见的播放器 UI 控制文本
        if (/\d+:\d+\s*\/\s*\d+:\d+/.test(normalized)) return null;
        if (/(?:自动续播|小窗模式|全屏|倍速|清晰度|弹幕|网页全屏)/.test(normalized)) return null;
        if (/^(?:播放|暂停|停止|上一个|下一个|静音|取消静音|音量|分享|转发|收藏|点赞|评论|关注|已关注)\s*$/.test(normalized)) return null;

        if (looksLikePlaceholderNonce(normalized)) return null;
        if (looksLikeJsExpressionTitle(normalized)) return null;
        if (/[{};]/.test(normalized)) return null;

        // 过滤纯 ASCII 无空格的 CamelCase 拼接词（CSS 属性值被误提取为标题）
        // 例如 "TransparencyOpaqueSemi-TransparentTransparent"
        if (/^[\x00-\x7F]+$/.test(normalized) && normalized.indexOf(' ') === -1 && normalized.length > 15) {
            var camelParts = normalized.match(/[A-Z][a-z]+/g);
            if (camelParts && camelParts.length >= 3) {
                var cssWords = ['transparent','opaque','transparency','semi','visible','hidden','inherit','initial','none','auto','normal','bold','italic','block','inline','absolute','relative','fixed','static','sticky'];
                var cssMatches = 0;
                for (var ci = 0; ci < camelParts.length; ci++) {
                    if (cssWords.indexOf(camelParts[ci].toLowerCase()) !== -1) cssMatches++;
                }
                if (cssMatches >= 2) return null;
            }
        }

        return normalized;
    }

    function scoreTitleCandidate(value) {
        var normalized = sanitizeTitleValue(value);
        if (!normalized) return 0;

        var compact = normalized.replace(/\s+/g, ' ').trim();
        var score = 10;
        if (compact.length >= 4 && compact.length <= 80) score += 2;
        if (/\s/.test(compact)) score += 2;
        if (/[\u4e00-\u9fff]/.test(compact)) score += 2;
        score += Math.floor(Math.min(compact.length, 48) / 12);
        return score;
    }

    function pickBetterTitle(current, incoming) {
        var normalizedCurrent = sanitizeTitleValue(current);
        var normalizedIncoming = sanitizeTitleValue(incoming);
        if (!normalizedCurrent) return normalizedIncoming;
        if (!normalizedIncoming) return normalizedCurrent;

        var currentScore = scoreTitleCandidate(normalizedCurrent);
        var incomingScore = scoreTitleCandidate(normalizedIncoming);
        if (incomingScore > currentScore) return normalizedIncoming;
        if (incomingScore === currentScore) {
            var incomingHasAsciiWord = /[A-Za-z0-9]/.test(normalizedIncoming);
            var currentHasAsciiWord = /[A-Za-z0-9]/.test(normalizedCurrent);
            if (incomingHasAsciiWord && !currentHasAsciiWord) return normalizedIncoming;
            if (normalizedIncoming.length > normalizedCurrent.length + 4) return normalizedIncoming;
        }
        return normalizedCurrent;
    }

    function normalizeDecodeKeyValue(value, maxDepth) {
        maxDepth = typeof maxDepth === 'number' ? maxDepth : 5;
        if (value === null || value === undefined) return null;

        if (typeof value === 'string') {
            var text = value.trim();
            if (!text) return null;
            var matched = text.match(/^([1-9]\d{0,127})(?:n)?$/);
            return matched ? matched[1] : null;
        }

        if (typeof value === 'number') {
            if (!isFinite(value) || value <= 0 || Math.floor(value) !== value) return null;
            return String(value);
        }

        if (typeof value === 'bigint') {
            return value > 0 ? value.toString() : null;
        }

        if (maxDepth <= 0) return null;

        if (Array.isArray(value)) {
            for (var i = 0; i < value.length; i++) {
                var nestedArrayDecodeKey = normalizeDecodeKeyValue(value[i], maxDepth - 1);
                if (nestedArrayDecodeKey) return nestedArrayDecodeKey;
            }
            return null;
        }

        if (!value || typeof value !== 'object') return null;

        if (typeof value.low === 'number' && typeof value.high === 'number' && typeof BigInt === 'function') {
            try {
                var low = BigInt(value.low >>> 0);
                var high = BigInt(value.high >>> 0);
                var combined = (high << 32n) | low;
                if (combined > 0) {
                    return combined.toString();
                }
            } catch (e) {
                // ignore BigInt conversion failures
            }
        }

        var nestedKeys = [
            'decodeKey', 'decode_key', 'decodeKey64', 'decode_key64',
            'decryptKey', 'decrypt_key', 'decryptionKey', 'decryption_key',
            'decryptSeed', 'decrypt_seed', 'seed', 'seedValue', 'seed_value',
            'mediaKey', 'media_key', 'videoKey', 'video_key',
            'dk', '$numberLong', 'value'
        ];
        for (var keyIndex = 0; keyIndex < nestedKeys.length; keyIndex++) {
            var key = nestedKeys[keyIndex];
            if (value[key] !== undefined && value[key] !== null) {
                var nestedDecodeKey = normalizeDecodeKeyValue(value[key], maxDepth - 1);
                if (nestedDecodeKey) return nestedDecodeKey;
            }
        }

        try {
            if (typeof value.toJSON === 'function') {
                var jsonValue = value.toJSON();
                var normalizedJsonValue = normalizeDecodeKeyValue(jsonValue, maxDepth - 1);
                if (normalizedJsonValue) return normalizedJsonValue;
            }
        } catch (e) {
            // ignore custom toJSON failures
        }

        try {
            if (typeof value.toString === 'function' && value.toString !== Object.prototype.toString) {
                var normalizedString = normalizeDecodeKeyValue(String(value), maxDepth - 1);
                if (normalizedString) return normalizedString;
            }
        } catch (e) {
            // ignore custom toString failures
        }

        return null;
    }

    function addUniqueString(list, value) {
        if (value === null || value === undefined) return;
        var text = String(value).trim();
        if (!text) return;
        if (list.indexOf(text) === -1) {
            list.push(text);
        }
    }

    function extractCacheKeys(item, url) {
        var cacheKeys = [];
        var keyNames = [
            'encfilekey', 'm', 'taskid', 'taskId',
            'objectid', 'feedid', 'objectId', 'feedId',
            'filekey', 'videoId', 'video_id', 'mediaId', 'mediaid'
        ];

        for (var i = 0; i < keyNames.length; i++) {
            var keyName = keyNames[i];
            addUniqueString(cacheKeys, findNestedValue(item, [keyName]));
            addUniqueString(cacheKeys, findDeepValue(item, [keyName], 6, []));
        }

        if (url && typeof url === 'string') {
            var queryMatch;
            var queryPattern = /(?:[?&])(encfilekey|m|taskid|taskId|objectid|feedid|objectId|feedId|filekey|videoId|video_id|mediaId|mediaid)=([^&#]+)/ig;
            while ((queryMatch = queryPattern.exec(url)) !== null) {
                var cacheKeyValue = queryMatch[2];
                try {
                    cacheKeyValue = decodeURIComponent(cacheKeyValue);
                } catch (e) {
                    // ignore malformed escape sequences
                }
                addUniqueString(cacheKeys, cacheKeyValue);
            }
        }

        // 对长 encfilekey 类型的值添加截断前缀版本，用于跨清晰度模糊匹配
        // 同一视频不同 spec 共享 encfilekey 前缀（约 36 字符）
        var enriched = cacheKeys.slice();
        for (var pfxIdx = 0; pfxIdx < cacheKeys.length; pfxIdx++) {
            if (cacheKeys[pfxIdx].length > 40) {
                addUniqueString(enriched, 'pfx:' + cacheKeys[pfxIdx].substring(0, 36));
            }
        }

        return enriched;
    }

    function extractCacheKeysFromText(text) {
        var cacheKeys = [];
        if (!text || typeof text !== 'string') return cacheKeys;

        var normalized = text
            .replace(/\\u0026/g, '&')
            .replace(/\\\//g, '/');
        var keyPattern = /(?:["']?(encfilekey|m|taskid|taskId|objectid|feedid|objectId|feedId|filekey|videoId|video_id|mediaId|mediaid)["']\s*[:=]\s*["']([^"'\\\s<>]{1,256})["'])|(?:[?&](encfilekey|m|taskid|taskId|objectid|feedid|objectId|feedId|filekey|videoId|video_id|mediaId|mediaid)=([^&#"'\\\s<>]{1,256}))/ig;
        var match;
        while ((match = keyPattern.exec(normalized)) !== null) {
            var value = match[2] || match[4];
            if (!value) continue;
            try {
                value = decodeURIComponent(value);
            } catch (e) {
                // ignore malformed escape sequences
            }
            addUniqueString(cacheKeys, value);
        }
        return cacheKeys;
    }

    function findDeepValue(obj, keyNames, maxDepth, seen) {
        if (!obj || typeof obj !== 'object' || maxDepth < 0) return null;
        seen = seen || [];
        if (seen.indexOf(obj) !== -1) return null;
        seen.push(obj);

        var normalizedKeys = {};
        for (var i = 0; i < keyNames.length; i++) {
            normalizedKeys[String(keyNames[i]).toLowerCase()] = true;
        }

        if (Array.isArray(obj)) {
            for (var arrIndex = 0; arrIndex < obj.length; arrIndex++) {
                var arrValue = obj[arrIndex];
                if (typeof arrValue === 'object') {
                    var foundInArray = findDeepValue(arrValue, keyNames, maxDepth - 1, seen);
                    if (foundInArray !== null && foundInArray !== undefined && foundInArray !== '') {
                        return foundInArray;
                    }
                }
            }
            return null;
        }

        var keys = Object.keys(obj);
        for (var keyIndex = 0; keyIndex < keys.length; keyIndex++) {
            var key = keys[keyIndex];
            if (normalizedKeys[key.toLowerCase()]) {
                var directValue = obj[key];
                if (directValue !== null && directValue !== undefined && directValue !== '') {
                    return directValue;
                }
            }
        }

        for (var childIndex = 0; childIndex < keys.length; childIndex++) {
            var childValue = obj[keys[childIndex]];
            if (childValue && typeof childValue === 'object') {
                var nestedValue = findDeepValue(childValue, keyNames, maxDepth - 1, seen);
                if (nestedValue !== null && nestedValue !== undefined && nestedValue !== '') {
                    return nestedValue;
                }
            }
        }

        return null;
    }

    // =========================================
    // Feed 数据提取
    // =========================================

    // 从 API 响应中递归提取视频 feed 数据
    function extractFeedData(data) {
        var feeds = [];
        if (!data || typeof data !== 'object') return feeds;

        // 直接查找 feed 列表
        var feedLists = findNestedKey(data, ['feedList', 'objectList', 'objects', 'object_list']);
        if (feedLists && Array.isArray(feedLists)) {
            for (var i = 0; i < feedLists.length; i++) {
                var feed = parseFeedItem(feedLists[i]);
                if (feed) feeds.push(feed);
            }
        }

        // 查找单个 feed 对象（详情页）
        if (feeds.length === 0) {
            var singleFeed = parseFeedItem(data);
            if (singleFeed) feeds.push(singleFeed);
        }

        // 递归搜索嵌套结构
        if (feeds.length === 0) {
            searchFeeds(data, feeds, 0);
        }

        return feeds;
    }

    // 递归搜索 feed 数据
    function searchFeeds(obj, feeds, depth) {
        if (depth > 7 || !obj || typeof obj !== 'object') return;
        if (Array.isArray(obj)) {
            for (var i = 0; i < obj.length; i++) {
                var feed = parseFeedItem(obj[i]);
                if (feed) {
                    feeds.push(feed);
                } else {
                    searchFeeds(obj[i], feeds, depth + 1);
                }
            }
        } else {
            var keys = Object.keys(obj);
            for (var j = 0; j < keys.length; j++) {
                searchFeeds(obj[keys[j]], feeds, depth + 1);
            }
        }
    }

    // 解析单个 feed 项
    function parseFeedItem(item) {
        if (!item || typeof item !== 'object') return null;
        var decodeKeyFields = [
            'decodeKey', 'decode_key', 'decodeKey64', 'decode_key64',
            'decryptKey', 'decrypt_key', 'decryptionKey', 'decryption_key',
            'decryptSeed', 'decrypt_seed', 'seed', 'seedValue', 'seed_value',
            'mediaKey', 'media_key', 'videoKey', 'video_key', 'dk', 'key'
        ];
        var thumbFields = [
            'thumbUrl', 'thumb_url', 'thumb', 'coverUrl', 'cover_url',
            'coverImage', 'cover_image', 'coverImg', 'cover_img',
            'coverImgUrl', 'cover_img_url', 'cover', 'poster',
            'posterUrl', 'poster_url', 'imageUrl', 'image_url'
        ];
        var specGroups = findNestedKey(item, ['spec', 'specs', 'mediaSpec', 'media_spec', 'specList']);
        var specCandidates = [];
        if (Array.isArray(specGroups)) {
            specCandidates = specGroups;
        } else if (specGroups && typeof specGroups === 'object') {
            specCandidates = [specGroups];
        }

        // 提取视频 URL
        var urlKeys = [
            'url', 'videoUrl', 'video_url', 'mediaUrl', 'media_url',
            'playUrl', 'play_url', 'downloadUrl', 'download_url',
            'videoPlayUrl', 'video_play_url', 'src', 'videoSrc', 'video_src'
        ];
        var url = normalizeUrlValue(findNestedValue(item, urlKeys));
        if (!url) {
            // 从 media/spec 结构中提取
            var media = item.media || item.objectDesc || item.object;
            if (media) {
                url = normalizeUrlValue(findNestedValue(media, urlKeys));
                if (!url) {
                    url = normalizeUrlValue(findDeepValue(media, urlKeys, 6, []));
                }
            }
        }
        if (!url) {
            url = normalizeUrlValue(findDeepValue(item, urlKeys, 6, []));
        }
        if (!url) {
            var mediaCandidates = [
                item.media, item.objectDesc, item.object, item.feedObject,
                item.feed_object, item.video, item.videoInfo, item.mediaInfo
            ];
            for (var mediaIndex = 0; mediaIndex < mediaCandidates.length; mediaIndex++) {
                var mediaCandidate = mediaCandidates[mediaIndex];
                if (!mediaCandidate) continue;
                url = normalizeUrlValue(findDeepValue(mediaCandidate, urlKeys, 6, []));
                if (url) break;
            }
        }

        // 提取 decodeKey
        var decodeKey = normalizeDecodeKeyValue(findNestedValue(item, decodeKeyFields));
        if (!decodeKey) {
            // 从 spec/media 嵌套结构搜索
            if (specCandidates.length > 0) {
                for (var i = 0; i < specCandidates.length; i++) {
                    decodeKey = normalizeDecodeKeyValue(findNestedValue(specCandidates[i], decodeKeyFields));
                    if (!decodeKey) {
                        decodeKey = normalizeDecodeKeyValue(findDeepValue(specCandidates[i], decodeKeyFields, 4, []));
                    }
                    if (decodeKey) break;
                    if (!url) {
                        url = normalizeUrlValue(findNestedValue(specCandidates[i], urlKeys));
                        if (!url) {
                            url = normalizeUrlValue(findDeepValue(specCandidates[i], urlKeys, 4, []));
                        }
                    }
                }
            }
        }
        if (!decodeKey) {
            var extraSpecCandidates = [item.media, item.objectDesc, item.object, item.video, item.videoInfo];
            for (var extraSpecIndex = 0; extraSpecIndex < extraSpecCandidates.length; extraSpecIndex++) {
                var extraSpec = extraSpecCandidates[extraSpecIndex];
                if (!extraSpec) continue;
                decodeKey = normalizeDecodeKeyValue(findDeepValue(extraSpec, decodeKeyFields, 6, []));
                if (decodeKey) break;
            }
        }
        if (!decodeKey) {
            decodeKey = normalizeDecodeKeyValue(findDeepValue(item, decodeKeyFields, 6, []));
        }
        // 提取标题
        var title = sanitizeTitleValue(findNestedValue(item, [
            'title', 'desc', 'description', 'feedDesc', 'feedTitle', 'feed_title',
            'content', 'contentDesc', 'caption', 'headline', 'videoTitle',
            'shareTitle', 'share_title', 'shareDesc', 'share_desc',
            'finderTitle', 'finder_title', 'finderDesc', 'finder_desc',
            'descriptionText', 'contentText',
            'objectDesc.description', 'objectDesc.desc', 'objectDesc.title',
            'objectDesc.content', 'objectDesc.contentDesc', 'media.title',
            'media.description', 'media.desc'
        ]));
        if (!title) {
            title = sanitizeTitleValue(findDeepValue(item, [
                'title', 'desc', 'description', 'feedDesc', 'feedTitle', 'feed_title',
                'content', 'contentDesc', 'caption', 'headline', 'videoTitle',
                'shareTitle', 'share_title', 'shareDesc', 'share_desc',
                'finderTitle', 'finder_title', 'finderDesc', 'finder_desc',
                'descriptionText', 'contentText'
            ], 6, []));
        }
        if (!title) {
            title = sanitizeTitleValue(findNestedValue(item, ['objectNonceId']));
        }

        // 提取作者信息
        var author = null;
        var contact = item.contact || item.author || item.userInfo || item.user_info;
        if (contact) {
            author = normalizeTextValue(contact.nickname || contact.name || contact.userName || contact.nickName || null);
        }
        if (!author) {
            author = normalizeTextValue(findNestedValue(item, ['nickname', 'nickName', 'authorName', 'author_name']));
        }
        if (!author) {
            author = normalizeTextValue(findDeepValue(item, ['nickname', 'authorName', 'author_name', 'nickName'], 6, []));
        }
        // 提取封面
        var thumbUrl = findNestedValue(item, thumbFields);
        if (!thumbUrl) {
            thumbUrl = findDeepValue(item, thumbFields, 6, []);
        }
        if (!thumbUrl && specCandidates.length > 0) {
            for (var specThumbIndex = 0; specThumbIndex < specCandidates.length; specThumbIndex++) {
                thumbUrl = findNestedValue(specCandidates[specThumbIndex], thumbFields);
                if (!thumbUrl) {
                    thumbUrl = findDeepValue(specCandidates[specThumbIndex], thumbFields, 4, []);
                }
                if (thumbUrl) break;
            }
        }
        thumbUrl = normalizeAssetUrl(thumbUrl);

        // 提取时长（添加合理性校验，避免 findDeepValue 找到错误的同名字段）
        var duration = findNestedValue(item, ['duration', 'videoDuration', 'video_duration',
                                              'playDuration', 'play_duration']);
        if (!duration) {
            duration = findDeepValue(item, ['duration', 'videoDuration', 'video_duration', 'playDuration', 'play_duration'], 6, []);
        }
        if (!duration) {
            duration = findNestedValue(item, ['durationMs', 'duration_ms', 'videoPlayLen', 'video_play_len', 'playLen', 'play_len']);
            if (!duration) {
                duration = findDeepValue(item, ['durationMs', 'duration_ms', 'videoPlayLen', 'video_play_len', 'playLen', 'play_len'], 6, []);
            }
            duration = (parseInt(duration, 10) || 0) > 0 ? Math.round((parseInt(duration, 10) || 0) / 1000) : 0;
        } else {
            duration = parseInt(duration, 10) || 0;
        }
        // 合理性校验：时长 <= 1 秒几乎不可能是真实视频时长，丢弃
        if (duration <= 1) duration = 0;

        // 提取分辨率
        var width = findNestedValue(item, ['width', 'videoWidth', 'video_width']);
        var height = findNestedValue(item, ['height', 'videoHeight', 'video_height']);
        if (!width) width = findDeepValue(item, ['width', 'videoWidth', 'video_width'], 6, []);
        if (!height) height = findDeepValue(item, ['height', 'videoHeight', 'video_height'], 6, []);
        if ((!width || !height) && specCandidates.length > 0) {
            for (var specMetricIndex = 0; specMetricIndex < specCandidates.length; specMetricIndex++) {
                if (!width) {
                    width = findNestedValue(specCandidates[specMetricIndex], ['width', 'videoWidth', 'video_width']);
                    if (!width) {
                        width = findDeepValue(specCandidates[specMetricIndex], ['width', 'videoWidth', 'video_width'], 4, []);
                    }
                }
                if (!height) {
                    height = findNestedValue(specCandidates[specMetricIndex], ['height', 'videoHeight', 'video_height']);
                    if (!height) {
                        height = findDeepValue(specCandidates[specMetricIndex], ['height', 'videoHeight', 'video_height'], 4, []);
                    }
                }
                if (width && height) break;
            }
        }

        // 提取文件大小（不搜索 'size'，太通用容易匹配到数组长度等无关值）
        var fileSize = findNestedValue(item, ['fileSize', 'file_size', 'videoSize', 'video_size']);
        if (!fileSize) {
            fileSize = findDeepValue(item, ['fileSize', 'file_size', 'videoSize', 'video_size'], 6, []);
        }
        if (!fileSize && specCandidates.length > 0) {
            for (var specSizeIndex = 0; specSizeIndex < specCandidates.length; specSizeIndex++) {
                fileSize = findNestedValue(specCandidates[specSizeIndex], ['fileSize', 'file_size', 'videoSize', 'video_size']);
                if (!fileSize) {
                    fileSize = findDeepValue(specCandidates[specSizeIndex], ['fileSize', 'file_size', 'videoSize', 'video_size'], 4, []);
                }
                if (fileSize) break;
            }
        }
        // 合理性校验：文件大小 < 10KB 不可能是真实视频
        if ((parseInt(fileSize) || 0) < 10240) fileSize = 0;

        var cacheKeys = extractCacheKeys(item, url);
        var hasRichMetadata = !!(title || author || thumbUrl || duration || width || height || fileSize);

        // 允许只有 cacheKeys 的卡片元数据回填到已抓到的原始视频记录
        if (!url && !decodeKey && (!cacheKeys.length || !hasRichMetadata)) return null;

        return {
            url: url || null,
            title: title || null,
            author: author || null,
            decodeKey: decodeKey || null,
            thumbUrl: thumbUrl || null,
            duration: duration || 0,
            width: parseInt(width) || 0,
            height: parseInt(height) || 0,
            fileSize: parseInt(fileSize) || 0,
            cacheKeys: cacheKeys,
            pageUrl: window.location.href
        };
    }

    // 在对象中查找嵌套键的值
    function findNestedKey(obj, keyNames) {
        if (!obj || typeof obj !== 'object') return null;
        for (var i = 0; i < keyNames.length; i++) {
            if (obj[keyNames[i]] !== undefined && obj[keyNames[i]] !== null) {
                return obj[keyNames[i]];
            }
        }
        // 递归搜索一层
        var keys = Object.keys(obj);
        for (var j = 0; j < keys.length; j++) {
            var val = obj[keys[j]];
            if (val && typeof val === 'object' && !Array.isArray(val)) {
                for (var k = 0; k < keyNames.length; k++) {
                    if (val[keyNames[k]] !== undefined && val[keyNames[k]] !== null) {
                        return val[keyNames[k]];
                    }
                }
            }
        }
        return null;
    }

    // 在对象中查找嵌套值
    function findNestedValue(obj, keyNames) {
        if (!obj || typeof obj !== 'object') return null;
        for (var i = 0; i < keyNames.length; i++) {
            var key = keyNames[i];
            // 支持 dotted path（如 "objectDesc.description"）
            if (key.indexOf('.') !== -1) {
                var parts = key.split('.');
                var current = obj;
                var found = true;
                for (var p = 0; p < parts.length; p++) {
                    if (current && typeof current === 'object' && current[parts[p]] !== undefined) {
                        current = current[parts[p]];
                    } else {
                        found = false;
                        break;
                    }
                }
                if (found && current !== null && current !== undefined && current !== '') {
                    return current;
                }
            } else if (obj[key] !== undefined && obj[key] !== null && obj[key] !== '') {
                return obj[key];
            }
        }
        return null;
    }

    // =========================================
    // 提交视频数据到后端
    // =========================================

    function submitFeedToBackend(feed) {
        var safeTitle = sanitizeTitleValue(feed && feed.title);
        var safeFeed = {
            url: feed && feed.url ? feed.url : null,
            title: safeTitle,
            author: feed && feed.author ? feed.author : null,
            decodeKey: feed && feed.decodeKey ? feed.decodeKey : null,
            thumbUrl: feed && feed.thumbUrl ? feed.thumbUrl : null,
            duration: feed && feed.duration ? feed.duration : 0,
            width: feed && feed.width ? feed.width : 0,
            height: feed && feed.height ? feed.height : 0,
            fileSize: feed && feed.fileSize ? feed.fileSize : 0,
            cacheKeys: feed && feed.cacheKeys ? feed.cacheKeys : [],
            pageUrl: feed && feed.pageUrl ? feed.pageUrl : window.location.href
        };
        if (!safeFeed.url && !safeFeed.decodeKey && (!safeFeed.cacheKeys || safeFeed.cacheKeys.length === 0)) {
            return;
        }

        // 生成稳定的视频标识（不受 URL query 参数变化影响）
        var stableId = null;
        // 优先用 cacheKeys（最稳定的视频标识）
        if (safeFeed.cacheKeys && safeFeed.cacheKeys.length > 0) {
            stableId = 'cache:' + safeFeed.cacheKeys.sort().join(',');
        }
        // 其次用 URL 中的 encfilekey 或 path
        if (!stableId) {
            stableId = extractStableVideoId(safeFeed.url);
        }
        // 最后用 decodeKey + title 组合
        if (!stableId) {
            stableId = 'dk:' + (safeFeed.decodeKey || '') + '|' + (safeFeed.title || '');
        }

        var now = Date.now();

        // 基于稳定 ID 的时间窗口去重
        var existing = submittedVideoIds[stableId];
        if (existing) {
            // 检查是否有新的有价值信息（title、decodeKey 等之前没有的）
            var hasNewInfo = false;
            if (safeFeed.title && !existing.payload.title) hasNewInfo = true;
            if (safeFeed.decodeKey && !existing.payload.decodeKey) hasNewInfo = true;
            if (safeFeed.url && !existing.payload.url) hasNewInfo = true;
            if (safeFeed.thumbUrl && !existing.payload.thumbnail) hasNewInfo = true;
            if (safeFeed.duration > 0 && !existing.payload.duration) hasNewInfo = true;

            if (!hasNewInfo) {
                // 无新信息，在时间窗口内直接跳过
                if ((now - existing.timestamp) < BRIDGE_MIN_INTERVAL_MS) {
                    return;
                }
            }
            // 有新信息或超过窗口，合并元数据后允许重新提交
        }

        // 旧的精确去重也保留（作为最后一道防线）
        var feedId = (safeFeed.url || '') + '|' + (safeFeed.decodeKey || '') + '|' + (safeFeed.title || '') + '|' + ((safeFeed.cacheKeys || []).join(','));
        if (submittedVideos.has(feedId)) return;
        submittedVideos.add(feedId);

        var payload = {
            url: safeFeed.url,
            title: safeFeed.title,
            author: safeFeed.author,
            decodeKey: safeFeed.decodeKey,
            thumbnail: safeFeed.thumbUrl,
            duration: safeFeed.duration,
            videoWidth: safeFeed.width,
            videoHeight: safeFeed.height,
            fileSize: safeFeed.fileSize,
            cacheKeys: safeFeed.cacheKeys || [],
            pageUrl: safeFeed.pageUrl,
            source: 'js_inject'
        };

        // 更新稳定 ID 记录
        submittedVideoIds[stableId] = { timestamp: now, payload: payload };

        // 全局节流：如果距离上次发送不足 500ms，延迟合并发送
        var timeSinceLast = now - lastBridgeRequestTime;
        if (timeSinceLast < BRIDGE_GLOBAL_MIN_MS) {
            // 替换待发送的 payload（保留最新的）
            pendingBridgePayload = payload;
            if (!pendingBridgeTimer) {
                pendingBridgeTimer = setTimeout(function() {
                    pendingBridgeTimer = null;
                    if (pendingBridgePayload) {
                        doSendBridgeRequest(pendingBridgePayload);
                        pendingBridgePayload = null;
                    }
                }, BRIDGE_GLOBAL_MIN_MS - timeSinceLast);
            }
            return;
        }

        doSendBridgeRequest(payload);
    }

    /**
     * 实际发送 bridge 请求到后端
     */
    function doSendBridgeRequest(payload) {
        lastBridgeRequestTime = Date.now();
        console.log('[VidFlow] 提交视频数据:', payload.title || payload.url);

        try {
            var xhr = new XMLHttpRequest();
            xhr.open('POST', PROXY_POST_URL, true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.onload = function() {
                if (xhr.status === 200) {
                    console.log('[VidFlow] 视频数据提交成功:', payload.title);
                } else {
                    console.warn('[VidFlow] 视频数据提交失败:', xhr.status);
                }
            };
            xhr.onerror = function() {
                console.warn('[VidFlow] 视频数据提交网络错误');
            };
            xhr.send(JSON.stringify(payload));
        } catch (e) {
            console.error('[VidFlow] 提交视频数据异常:', e);
        }
    }

    function submitFeedsToBackend(feeds, sourceLabel) {
        if (!feeds || !feeds.length) return;
        console.log('[VidFlow] 从 ' + sourceLabel + ' 提取到 ' + feeds.length + ' 个视频');
        for (var i = 0; i < feeds.length; i++) {
            submitFeedToBackend(feeds[i]);
        }
    }

    // 处理 API 响应数据
    function processAPIResponse(url, responseText) {
        try {
            var data = JSON.parse(responseText);
            var feeds = extractFeedData(data);
            submitFeedsToBackend(feeds, 'API ' + url.substring(0, 80));
        } catch (e) {
            // JSON 解析失败，忽略
        }
    }

    function processStructuredResponse(url, data, sourceLabel) {
        try {
            var feeds = extractFeedData(data);
            submitFeedsToBackend(feeds, sourceLabel + ' ' + String(url || '').substring(0, 80));
        } catch (e) {
            console.warn('[VidFlow] 处理结构化响应失败:', e);
        }
    }

    function getObjectKeysSafe(value) {
        if (!value || (typeof value !== 'object' && typeof value !== 'function')) return [];
        try {
            return Object.keys(value);
        } catch (e) {
            // ignore Object.keys failures
        }
        try {
            return Object.getOwnPropertyNames(value);
        } catch (e2) {
            // ignore property enumeration failures
        }
        return [];
    }

    function safeGetPropertyValue(obj, key) {
        if (!obj || key === null || key === undefined) return null;
        try {
            return obj[key];
        } catch (e) {
            return null;
        }
    }

    function isPromiseLike(value) {
        return !!value &&
            (typeof value === 'object' || typeof value === 'function') &&
            typeof value.then === 'function';
    }

    function normalizeWXRuntimeName(name) {
        return String(name || '').replace(/[^a-z0-9]+/ig, '').toLowerCase();
    }

    function isInterestingWXAPIMethodName(name) {
        var normalizedName = normalizeWXRuntimeName(name);
        if (!normalizedName) return false;
        if (WX_API_METHOD_NAMES[normalizedName]) return true;
        return normalizedName.indexOf('finder') === 0 ||
            normalizedName.indexOf('feedprofile') !== -1 ||
            normalizedName.indexOf('userfeed') !== -1 ||
            normalizedName.indexOf('recommendfeed') !== -1 ||
            normalizedName.indexOf('liveprofile') !== -1;
    }

    function isInterestingWXRuntimeKey(name) {
        var normalizedName = normalizeWXRuntimeName(name);
        if (!normalizedName) return false;
        return normalizedName === 'wxu' ||
            normalizedName === 'wxe' ||
            normalizedName === 'api' ||
            normalizedName === 'api2' ||
            normalizedName === 'api3' ||
            normalizedName === 'api4' ||
            normalizedName === 'utils' ||
            normalizedName === 'events' ||
            normalizedName === 'eventbus' ||
            normalizedName === 'store' ||
            normalizedName.indexOf('finder') !== -1 ||
            normalizedName.indexOf('feed') !== -1 ||
            normalizedName.indexOf('profile') !== -1 ||
            normalizedName.indexOf('live') !== -1 ||
            normalizedName.indexOf('channel') !== -1 ||
            normalizedName.indexOf('recommend') !== -1 ||
            normalizedName.indexOf('search') !== -1 ||
            normalizedName.indexOf('event') !== -1;
    }

    function looksLikeWXEventBus(value) {
        if (!value || typeof value !== 'object') return false;
        if (typeof safeGetPropertyValue(value, 'emit') !== 'function') return false;
        if (safeGetPropertyValue(value, 'Events') && typeof safeGetPropertyValue(value, 'Events') === 'object') {
            return true;
        }

        var keys = getObjectKeysSafe(value);
        var matches = 0;
        for (var i = 0; i < keys.length; i++) {
            var lowerName = normalizeWXRuntimeName(keys[i]);
            if (!lowerName) continue;
            if (lowerName === 'events' || lowerName === 'callbacks' || lowerName === 'handlers') {
                matches += 1;
            }
            if (
                lowerName.indexOf('on') === 0 &&
                (
                    lowerName.indexOf('feed') !== -1 ||
                    lowerName.indexOf('api') !== -1 ||
                    lowerName.indexOf('loaded') !== -1 ||
                    lowerName.indexOf('profile') !== -1
                )
            ) {
                matches += 1;
            }
            if (matches >= 2) return true;
        }
        return matches > 0;
    }

    function isLikelyWXAPIContainer(value) {
        if (!value || (typeof value !== 'object' && typeof value !== 'function')) return false;

        if (
            safeGetPropertyValue(value, 'API') ||
            safeGetPropertyValue(value, 'API2') ||
            safeGetPropertyValue(value, 'API3') ||
            safeGetPropertyValue(value, 'API4')
        ) {
            return true;
        }

        var keys = getObjectKeysSafe(value);
        var matches = 0;
        for (var i = 0; i < keys.length; i++) {
            var methodName = keys[i];
            if (typeof safeGetPropertyValue(value, methodName) !== 'function') continue;
            if (isInterestingWXAPIMethodName(methodName)) {
                matches += 1;
                if (matches >= 1) return true;
            }
        }
        return false;
    }

    function inspectWXStructuredPayload(value, sourceLabel) {
        if (!value || (typeof value !== 'object' && typeof value !== 'function')) return;
        if (looksLikeWXEventBus(value)) return;
        if (isLikelyWXAPIContainer(value)) return;
        processStructuredResponse(window.location.href, value, sourceLabel);
    }

    function wrapWXMethod(container, methodName, label) {
        var originalMethod = safeGetPropertyValue(container, methodName);
        if (typeof originalMethod !== 'function') return;
        if (wrappedWXMethods.has(originalMethod) || originalMethod.__vidflowWXWrapped__) return;

        var wrappedMethod = function() {
            var args = Array.prototype.slice.call(arguments);
            for (var argIndex = 0; argIndex < args.length && argIndex < 6; argIndex++) {
                var arg = args[argIndex];
                if (arg && (typeof arg === 'object' || typeof arg === 'function')) {
                    try {
                        inspectWXStructuredPayload(arg, 'wx_api_arg:' + label + '.' + methodName + '#' + argIndex);
                        discoverAndHookWXRuntimeValue(arg, label + '.' + methodName + '.arg' + argIndex, 0, []);
                    } catch (argError) {
                        console.warn('[VidFlow] Failed to inspect WX API arg:', methodName, argError);
                    }
                }
            }

            var result = originalMethod.apply(this, arguments);

            try {
                if (isPromiseLike(result)) {
                    result.then(function(resolved) {
                        if (resolved && (typeof resolved === 'object' || typeof resolved === 'function')) {
                            inspectWXStructuredPayload(resolved, 'wx_api_result:' + label + '.' + methodName);
                            discoverAndHookWXRuntimeValue(resolved, label + '.' + methodName + '.result', 0, []);
                        }
                        return resolved;
                    }).catch(function() {
                        // ignore promise inspection failures
                    });
                } else if (result && (typeof result === 'object' || typeof result === 'function')) {
                    inspectWXStructuredPayload(result, 'wx_api_result:' + label + '.' + methodName);
                    discoverAndHookWXRuntimeValue(result, label + '.' + methodName + '.result', 0, []);
                }
            } catch (resultError) {
                console.warn('[VidFlow] Failed to inspect WX API result:', methodName, resultError);
            }

            return result;
        };

        wrappedMethod.__vidflowWXWrapped__ = true;
        wrappedWXMethods.add(originalMethod);
        wrappedWXMethods.add(wrappedMethod);

        try {
            container[methodName] = wrappedMethod;
        } catch (e) {
            // ignore read-only method slots
        }
    }

    function registerWXAPIContainer(container, label) {
        if (!container || (typeof container !== 'object' && typeof container !== 'function')) return;
        if (wrappedWXContainers.has(container)) return;
        wrappedWXContainers.add(container);

        var keys = getObjectKeysSafe(container);
        for (var i = 0; i < keys.length; i++) {
            var methodName = keys[i];
            if (typeof safeGetPropertyValue(container, methodName) !== 'function') continue;
            if (!isInterestingWXAPIMethodName(methodName)) continue;
            wrapWXMethod(container, methodName, label);
        }
    }

    function hookWXEventBus(eventBus, label) {
        if (!eventBus || typeof eventBus !== 'object') return;
        if (wrappedWXEventBuses.has(eventBus)) return;

        var originalEmit = safeGetPropertyValue(eventBus, 'emit');
        if (typeof originalEmit !== 'function') return;
        wrappedWXEventBuses.add(eventBus);

        var wrappedEmit = function(eventName) {
            var normalizedEventName = normalizeWXRuntimeName(eventName);
            var args = Array.prototype.slice.call(arguments, 1);

            try {
                for (var i = 0; i < args.length && i < 6; i++) {
                    var payload = args[i];
                    if (!payload || (typeof payload !== 'object' && typeof payload !== 'function')) continue;

                    if (WX_FEED_EVENT_NAMES[normalizedEventName]) {
                        inspectWXStructuredPayload(payload, 'wx_event:' + label + ':' + normalizedEventName + '#' + i);
                    }

                    if (
                        WX_RUNTIME_EVENT_NAMES[normalizedEventName] ||
                        looksLikeWXEventBus(payload) ||
                        isLikelyWXAPIContainer(payload)
                    ) {
                        discoverAndHookWXRuntimeValue(payload, label + '.event.' + normalizedEventName + '.arg' + i, 0, []);
                    }
                }
            } catch (emitError) {
                console.warn('[VidFlow] Failed to inspect WX event payload:', emitError);
            }

            return originalEmit.apply(this, arguments);
        };

        wrappedEmit.__vidflowWXWrapped__ = true;
        try {
            eventBus.emit = wrappedEmit;
        } catch (e) {
            // ignore read-only event bus
        }
    }

    function discoverAndHookWXRuntimeValue(value, label, depth, seen) {
        depth = typeof depth === 'number' ? depth : 0;
        if (!value || depth > 4) return;
        if (typeof value !== 'object' && typeof value !== 'function') return;

        seen = seen || [];
        if (seen.indexOf(value) !== -1) return;
        seen.push(value);

        if (looksLikeWXEventBus(value)) {
            hookWXEventBus(value, label);
        }
        if (isLikelyWXAPIContainer(value)) {
            registerWXAPIContainer(value, label);
        }

        var directKeys = ['WXU', 'WXE', 'API', 'API2', 'API3', 'API4', 'api', 'api2', 'api3', 'api4', 'Utils', 'utils', 'Events', 'events', 'EventBus', 'eventBus'];
        for (var directIndex = 0; directIndex < directKeys.length; directIndex++) {
            var directKey = directKeys[directIndex];
            var directValue = safeGetPropertyValue(value, directKey);
            if (!directValue || directValue === value) continue;
            discoverAndHookWXRuntimeValue(directValue, label + '.' + directKey, depth + 1, seen);
        }

        var keys = getObjectKeysSafe(value);
        var childCount = 0;
        for (var i = 0; i < keys.length; i++) {
            var key = keys[i];
            if (!isInterestingWXRuntimeKey(key)) continue;
            var childValue = safeGetPropertyValue(value, key);
            if (!childValue || childValue === value) continue;
            if (typeof childValue !== 'object' && typeof childValue !== 'function') continue;
            childCount += 1;
            discoverAndHookWXRuntimeValue(childValue, label + '.' + key, depth + 1, seen);
            if (childCount >= 24) break;
        }
    }

    function discoverAndHookWXRuntime(reason) {
        var rootCandidates = [
            { label: 'window.WXU', value: safeGetPropertyValue(window, 'WXU') },
            { label: 'window.WXE', value: safeGetPropertyValue(window, 'WXE') },
            { label: 'window.__wx_channels_store__', value: safeGetPropertyValue(window, '__wx_channels_store__') },
            { label: 'window.__wx_channels_live_store__', value: safeGetPropertyValue(window, '__wx_channels_live_store__') },
            { label: 'window.__wx_channels_state__', value: safeGetPropertyValue(window, '__wx_channels_state__') },
            { label: 'window.__WX_CHANNELS_STATE__', value: safeGetPropertyValue(window, '__WX_CHANNELS_STATE__') }
        ];

        var foundRoots = [];
        for (var i = 0; i < rootCandidates.length; i++) {
            if (!rootCandidates[i].value) continue;
            foundRoots.push(rootCandidates[i].label);
            discoverAndHookWXRuntimeValue(rootCandidates[i].value, reason + '.' + rootCandidates[i].label, 0, []);
        }
        if (foundRoots.length > 0) {
            console.log('[VidFlow] 发现 WX 运行时对象:', foundRoots.join(', '), '来源:', reason);
        }

        try {
            var names = Object.getOwnPropertyNames(window || {});
            var inspected = 0;
            for (var nameIndex = 0; nameIndex < names.length; nameIndex++) {
                var name = names[nameIndex];
                if (!isInterestingWXRuntimeKey(name)) continue;
                var value = safeGetPropertyValue(window, name);
                if (!value || (typeof value !== 'object' && typeof value !== 'function')) continue;
                inspected += 1;
                discoverAndHookWXRuntimeValue(value, reason + '.window.' + name, 0, []);
                if (inspected >= 24) break;
            }
        } catch (e) {
            // ignore window enumeration failures
        }
    }

    function extractFeedsFromHtmlText(htmlText) {
        var discovered = [];
        if (!htmlText || typeof htmlText !== 'string') return discovered;

        var scriptPattern = /<script\b[^>]*>([\s\S]*?)<\/script>/ig;
        var match;
        while ((match = scriptPattern.exec(htmlText)) !== null) {
            var scriptText = match[1];
            if (!scriptText) continue;

            var inferredFeed = extractFeedFromInlineText(scriptText);
            if (inferredFeed) {
                discovered.push(inferredFeed);
            }

            try {
                var trimmed = scriptText.trim();
                if (!trimmed) continue;
                if (trimmed.indexOf('{') === 0 || trimmed.indexOf('[') === 0) {
                    var parsed = JSON.parse(trimmed);
                    var parsedFeeds = extractFeedData(parsed);
                    for (var i = 0; i < parsedFeeds.length; i++) {
                        discovered.push(parsedFeeds[i]);
                    }
                }
            } catch (e) {
                // ignore malformed inline payloads
            }
        }

        return discovered;
    }

    function shouldInspectResponse(url, contentType) {
        if (!url || typeof url !== 'string') return false;
        if (url.indexOf(PROXY_POST_PATH) !== -1) return false;
        if (!isWeChatDomain(url) && !isWeChatAPI(url)) return false;

        var type = String(contentType || '').toLowerCase();
        if (!type) {
            return isWeChatAPI(url) || url.indexOf('channels.weixin.qq.com') !== -1;
        }
        if (type.indexOf('json') !== -1) return true;
        if (type.indexOf('html') !== -1) return true;
        if (type.indexOf('css') !== -1) return false;
        if (type.indexOf('javascript') !== -1 || type.indexOf('ecmascript') !== -1) return false;
        if (type.indexOf('text') !== -1) {
            return isWeChatAPI(url) || url.indexOf('channels.weixin.qq.com') !== -1;
        }
        if (type.indexOf('octet-stream') !== -1) return isWeChatAPI(url);
        return isWeChatAPI(url);
    }

    function processTextPayload(url, responseText, sourceLabel) {
        if (!responseText || typeof responseText !== 'string') return;
        if (responseText.length > 1500000) return;

        console.log('[VidFlow] 拦截到响应:', sourceLabel, 'url=' + (url || '').substring(0, 80), 'len=' + responseText.length);

        var discovered = [];

        try {
            var parsed = JSON.parse(responseText);
            processStructuredResponse(url, parsed, sourceLabel);
        } catch (e) {
            // Not JSON, continue with text inference.
        }

        var inferredFeed = extractFeedFromInlineText(responseText);
        if (inferredFeed) {
            discovered.push(inferredFeed);
        }

        if (responseText.indexOf('<script') !== -1) {
            var htmlFeeds = extractFeedsFromHtmlText(responseText);
            for (var i = 0; i < htmlFeeds.length; i++) {
                discovered.push(htmlFeeds[i]);
            }
        }

        submitFeedsToBackend(discovered, sourceLabel + ' text');
    }

    function scheduleDeferredScan(reason, delay) {
        setTimeout(function() {
            scanGlobalState(reason);
        }, delay || 0);
    }

    function hookFetch() {
        if (!window.fetch || window.fetch.__vidflowWrapped__) return;

        var originalFetch = window.fetch;
        var wrappedFetch = function(input, init) {
            var requestUrl = null;
            try {
                if (typeof input === 'string') {
                    requestUrl = input;
                } else if (input && typeof input.url === 'string') {
                    requestUrl = input.url;
                }
            } catch (e) {
                // ignore
            }

            return originalFetch.apply(this, arguments).then(function(response) {
                try {
                    var responseUrl = (response && response.url) || requestUrl || '';
                    var contentType = '';
                    if (response && response.headers && typeof response.headers.get === 'function') {
                        contentType = response.headers.get('content-type') || '';
                    }

                    if (response && response.clone && shouldInspectResponse(responseUrl, contentType)) {
                        response.clone().text().then(function(text) {
                            processTextPayload(responseUrl, text, 'fetch');
                        }).catch(function() {
                            // ignore unreadable responses
                        });
                    }
                } catch (e) {
                    console.warn('[VidFlow] fetch 拦截处理失败:', e);
                }
                return response;
            });
        };

        wrappedFetch.__vidflowWrapped__ = true;
        window.fetch = wrappedFetch;
    }

    function inspectXHRResponse(xhr) {
        if (!xhr) return;

        var url = '';
        try {
            url = xhr.responseURL || xhr.__vidflow_url__ || '';
        } catch (e) {
            url = xhr.__vidflow_url__ || '';
        }

        var contentType = '';
        try {
            if (typeof xhr.getResponseHeader === 'function') {
                contentType = xhr.getResponseHeader('content-type') || '';
            }
        } catch (e) {
            // ignore
        }

        if (!shouldInspectResponse(url, contentType)) return;

        try {
            if (xhr.responseType === 'json' && xhr.response) {
                processStructuredResponse(url, xhr.response, 'xhr_json');
                return;
            }
        } catch (e) {
            // ignore
        }

        var responseText = '';
        try {
            if (!xhr.responseType || xhr.responseType === 'text' || xhr.responseType === '') {
                responseText = xhr.responseText || '';
            } else if (typeof xhr.response === 'string') {
                responseText = xhr.response;
            }
        } catch (e) {
            responseText = '';
        }

        if (responseText) {
            processTextPayload(url, responseText, 'xhr');
        }
    }

    function hookXHR() {
        if (!window.XMLHttpRequest || !window.XMLHttpRequest.prototype) return;
        var proto = window.XMLHttpRequest.prototype;
        if (proto.__vidflowWrapped__) return;

        var originalOpen = proto.open;
        var originalSend = proto.send;

        proto.open = function(method, url) {
            try {
                this.__vidflow_url__ = url;
            } catch (e) {
                // ignore
            }
            return originalOpen.apply(this, arguments);
        };

        proto.send = function() {
            try {
                if (!this.__vidflowListenerAttached__) {
                    var xhr = this;
                    var handleResponse = function() {
                        if (xhr.readyState !== 4 || xhr.__vidflowProcessed__) return;
                        xhr.__vidflowProcessed__ = true;
                        inspectXHRResponse(xhr);
                    };

                    if (typeof xhr.addEventListener === 'function') {
                        xhr.addEventListener('load', handleResponse);
                        xhr.addEventListener('readystatechange', handleResponse);
                    }
                    this.__vidflowListenerAttached__ = true;
                }
            } catch (e) {
                console.warn('[VidFlow] XHR 拦截安装失败:', e);
            }

            return originalSend.apply(this, arguments);
        };

        proto.__vidflowWrapped__ = true;
    }

    function hookHistoryNavigation() {
        if (window.__vidflowHistoryHooked__) return;
        window.__vidflowHistoryHooked__ = true;

        function rescan(reason) {
            scheduleDeferredScan(reason + '_fast', 300);
            scheduleDeferredScan(reason + '_late', 1200);
        }

        if (window.history && typeof window.history.pushState === 'function') {
            var originalPushState = window.history.pushState;
            window.history.pushState = function() {
                var result = originalPushState.apply(this, arguments);
                rescan('history_pushstate');
                return result;
            };
        }

        if (window.history && typeof window.history.replaceState === 'function') {
            var originalReplaceState = window.history.replaceState;
            window.history.replaceState = function() {
                var result = originalReplaceState.apply(this, arguments);
                rescan('history_replacestate');
                return result;
            };
        }

        window.addEventListener('popstate', function() {
            rescan('history_popstate');
        });
    }

    // =========================================
    // 消息通道 Hook（捕获原生进程传递的数据）
    // =========================================

    function inspectMessagePayload(data, sourceLabel) {
        if (!data) return;
        // 字符串载荷：尝试 JSON 解析
        if (typeof data === 'string') {
            if (data.length < 16 || data.length > 2000000) return;
            var lowerData = data.toLowerCase();
            // 仅处理包含视频相关关键词的载荷
            if (
                lowerData.indexOf('decodekey') === -1 &&
                lowerData.indexOf('decode_key') === -1 &&
                lowerData.indexOf('decryptkey') === -1 &&
                lowerData.indexOf('encfilekey') === -1 &&
                lowerData.indexOf('finder.video') === -1 &&
                lowerData.indexOf('feedid') === -1 &&
                lowerData.indexOf('objectid') === -1 &&
                lowerData.indexOf('thumburl') === -1 &&
                lowerData.indexOf('finderpcflow') === -1 &&
                lowerData.indexOf('stodownload') === -1
            ) {
                return;
            }
            console.log('[VidFlow] 消息通道发现视频关键词:', sourceLabel, 'len=' + data.length);
            try {
                var parsed = JSON.parse(data);
                processStructuredResponse(window.location.href, parsed, sourceLabel + '_json');
            } catch (e) {
                // 非 JSON，用文本推断
                var inferredFeed = extractFeedFromInlineText(data);
                if (inferredFeed) {
                    submitFeedToBackend(inferredFeed);
                }
            }
            return;
        }
        // 对象载荷：直接解析
        if (typeof data === 'object') {
            try {
                processStructuredResponse(window.location.href, data, sourceLabel + '_obj');
            } catch (e) {
                // 忽略解析失败
            }
        }
    }

    function hookPostMessage() {
        if (window.__vidflowPostMessageHooked__) return;
        window.__vidflowPostMessageHooked__ = true;

        // Hook window.addEventListener('message') 捕获所有 postMessage 事件
        var originalAddEventListener = window.addEventListener;
        window.addEventListener = function(type, listener, options) {
            if (type === 'message' && typeof listener === 'function' && !listener.__vidflowWrapped__) {
                var originalListener = listener;
                var wrappedListener = function(event) {
                    try {
                        inspectMessagePayload(event.data, 'postMessage');
                    } catch (e) {
                        // 忽略检查失败
                    }
                    return originalListener.apply(this, arguments);
                };
                wrappedListener.__vidflowWrapped__ = true;
                return originalAddEventListener.call(this, type, wrappedListener, options);
            }
            return originalAddEventListener.apply(this, arguments);
        };

        // 也直接监听 message 事件
        window.addEventListener('message', function(event) {
            try {
                inspectMessagePayload(event.data, 'postMessage_direct');
            } catch (e) {
                // 忽略
            }
        });

        console.log('[VidFlow] postMessage hook 已启用');
    }

    function hookWebView2Bridge() {
        // WebView2 (Edge/Chromium 内嵌浏览器) 消息通道
        if (window.chrome && window.chrome.webview) {
            try {
                window.chrome.webview.addEventListener('message', function(event) {
                    try {
                        inspectMessagePayload(event.data, 'webview2');
                    } catch (e) {
                        // 忽略
                    }
                });
                console.log('[VidFlow] WebView2 bridge hook 已启用');
            } catch (e) {
                // 忽略
            }
        }

        // CEF (Chromium Embedded Framework) 消息通道
        if (window.external && typeof window.external.invoke === 'function') {
            var originalExternalInvoke = window.external.invoke;
            window.external.invoke = function(message) {
                try {
                    inspectMessagePayload(message, 'cef_external');
                } catch (e) {
                    // 忽略
                }
                return originalExternalInvoke.apply(this, arguments);
            };
            console.log('[VidFlow] CEF external.invoke hook 已启用');
        }
    }

    function hookWeixinJSBridge() {
        // 直接 Hook WeixinJSBridge（微信原生 JS 桥接）
        function wrapBridge(bridge, label) {
            if (!bridge || bridge.__vidflowBridgeWrapped__) return;
            bridge.__vidflowBridgeWrapped__ = true;

            var methodsToWrap = ['invoke', 'call', 'on', 'subscribe', 'publish', 'emit'];
            for (var i = 0; i < methodsToWrap.length; i++) {
                (function(methodName) {
                    var original = bridge[methodName];
                    if (typeof original !== 'function') return;

                    bridge[methodName] = function() {
                        var args = Array.prototype.slice.call(arguments);
                        try {
                            // 检查所有参数
                            for (var argIdx = 0; argIdx < args.length && argIdx < 6; argIdx++) {
                                var arg = args[argIdx];
                                if (arg && typeof arg === 'object') {
                                    inspectMessagePayload(arg, label + '.' + methodName + '#' + argIdx);
                                } else if (typeof arg === 'string' && arg.length > 16) {
                                    inspectMessagePayload(arg, label + '.' + methodName + '#' + argIdx);
                                }
                            }
                            // 包装回调参数
                            for (var cbIdx = 0; cbIdx < args.length; cbIdx++) {
                                if (typeof args[cbIdx] === 'function') {
                                    args[cbIdx] = (function(originalCb) {
                                        return function() {
                                            try {
                                                for (var ri = 0; ri < arguments.length && ri < 4; ri++) {
                                                    inspectMessagePayload(arguments[ri], label + '.' + methodName + '_cb');
                                                }
                                            } catch (e) {
                                                // 忽略
                                            }
                                            return originalCb.apply(this, arguments);
                                        };
                                    })(args[cbIdx]);
                                }
                            }
                        } catch (e) {
                            // 忽略检查失败
                        }
                        return original.apply(this, args);
                    };
                    bridge[methodName].__vidflowBridgeMethodWrapped__ = true;
                })(methodsToWrap[i]);
            }
            console.log('[VidFlow] ' + label + ' hook 已启用');
        }

        // 立即检查
        if (window.WeixinJSBridge) {
            wrapBridge(window.WeixinJSBridge, 'WeixinJSBridge');
        }
        if (window.wx) {
            wrapBridge(window.wx, 'wx');
        }
        if (window.__wxjs_environment) {
            try {
                inspectMessagePayload(window.__wxjs_environment, 'wxjs_env');
            } catch (e) {
                // 忽略
            }
        }

        // 通过 Object.defineProperty 监听 WeixinJSBridge 出现
        var bridgeNames = ['WeixinJSBridge', 'wx', 'WeixinJSBridgeReady'];
        for (var i = 0; i < bridgeNames.length; i++) {
            (function(name) {
                if (window[name]) return; // 已存在，上面已处理
                var currentValue = undefined;
                try {
                    Object.defineProperty(window, name, {
                        configurable: true,
                        enumerable: true,
                        get: function() { return currentValue; },
                        set: function(newValue) {
                            currentValue = newValue;
                            if (newValue && typeof newValue === 'object') {
                                console.log('[VidFlow] 检测到 ' + name + ' 赋值');
                                wrapBridge(newValue, name);
                                // 赋值后恢复普通属性，避免干扰后续操作
                                try {
                                    Object.defineProperty(window, name, {
                                        configurable: true,
                                        enumerable: true,
                                        writable: true,
                                        value: newValue
                                    });
                                } catch (e) {
                                    // 忽略
                                }
                            }
                        }
                    });
                } catch (e) {
                    // 忽略 defineProperty 失败
                }
            })(bridgeNames[i]);
        }

        // 监听 WeixinJSBridgeReady 事件
        document.addEventListener('WeixinJSBridgeReady', function() {
            if (window.WeixinJSBridge) {
                wrapBridge(window.WeixinJSBridge, 'WeixinJSBridge_ready');
            }
        });
    }

    function hookMessageChannels() {
        // Hook BroadcastChannel
        if (typeof BroadcastChannel === 'function') {
            var OriginalBroadcastChannel = BroadcastChannel;
            window.BroadcastChannel = function(name) {
                var channel = new OriginalBroadcastChannel(name);
                channel.addEventListener('message', function(event) {
                    try {
                        inspectMessagePayload(event.data, 'broadcast:' + name);
                    } catch (e) {
                        // 忽略
                    }
                });
                return channel;
            };
            // 保持原型链
            try {
                window.BroadcastChannel.prototype = OriginalBroadcastChannel.prototype;
            } catch (e) {
                // 忽略
            }
        }

        // Hook MessageChannel
        if (typeof MessageChannel === 'function') {
            var OriginalMessageChannel = MessageChannel;
            window.MessageChannel = function() {
                var channel = new OriginalMessageChannel();
                var originalPort1 = channel.port1;
                var originalPort2 = channel.port2;

                // 包装 port 的 onmessage
                function wrapPort(port, label) {
                    var descriptor = Object.getOwnPropertyDescriptor(port, 'onmessage') ||
                                     Object.getOwnPropertyDescriptor(Object.getPrototypeOf(port), 'onmessage');
                    if (descriptor && descriptor.set) {
                        var originalSet = descriptor.set;
                        try {
                            Object.defineProperty(port, 'onmessage', {
                                configurable: true,
                                enumerable: true,
                                get: descriptor.get,
                                set: function(handler) {
                                    if (typeof handler === 'function') {
                                        var wrapped = function(event) {
                                            try {
                                                inspectMessagePayload(event.data, label);
                                            } catch (e) {
                                                // 忽略
                                            }
                                            return handler.apply(this, arguments);
                                        };
                                        return originalSet.call(this, wrapped);
                                    }
                                    return originalSet.call(this, handler);
                                }
                            });
                        } catch (e) {
                            // 忽略
                        }
                    }
                }

                wrapPort(originalPort1, 'msgchannel_port1');
                wrapPort(originalPort2, 'msgchannel_port2');
                return channel;
            };
            try {
                window.MessageChannel.prototype = OriginalMessageChannel.prototype;
            } catch (e) {
                // 忽略
            }
        }
    }

    function hookNativeBridges() {
        hookPostMessage();
        hookWebView2Bridge();
        hookWeixinJSBridge();
        hookMessageChannels();
    }

    // =========================================
    // 属性赋值拦截器（检测 decodeKey 被设置到任何对象）
    // =========================================

    function hookPropertyAssignment() {
        if (window.__vidflowPropertyHookActive__) return;
        window.__vidflowPropertyHookActive__ = true;

        // 监听 video 元素的 src 属性变化，当 src 设置时触发深度扫描
        if (typeof MutationObserver === 'function') {
            var videoSrcObserver = new MutationObserver(function(mutations) {
                for (var i = 0; i < mutations.length; i++) {
                    var mutation = mutations[i];
                    if (mutation.type === 'attributes' && mutation.target && mutation.target.tagName === 'VIDEO') {
                        var attrName = mutation.attributeName;
                        if (attrName === 'src' || attrName === 'data-src' || attrName === 'data-decode-key' || attrName === 'data-decrypt-key') {
                            var value = mutation.target.getAttribute(attrName);
                            if (attrName === 'data-decode-key' || attrName === 'data-decrypt-key') {
                                var dk = normalizeDecodeKeyValue(value);
                                if (dk) {
                                    console.log('[VidFlow] 从 video 属性检测到 decodeKey:', attrName);
                                    scheduleDeferredScan('video_attr_dk', 100);
                                }
                            } else if (value && (value.indexOf('finder.video') !== -1 || value.indexOf('stodownload') !== -1)) {
                                console.log('[VidFlow] 检测到 video src 变化，触发深度扫描');
                                scheduleDeferredScan('video_src_change', 200);
                                scheduleDeferredScan('video_src_settle', 1500);
                            }
                        }
                    }
                }
            });
            // 对 document 全局观察 video 属性变化
            videoSrcObserver.observe(document.documentElement, {
                attributes: true,
                attributeFilter: ['src', 'data-src', 'data-decode-key', 'data-decrypt-key'],
                subtree: true
            });
        }

        // 监控常见的微信状态对象名出现在 window 上
        var watchNames = [
            '__wx_feed_data__', '__WX_FEED_DATA__',
            '__finder_data__', '__FINDER_DATA__',
            '__video_data__', '__VIDEO_DATA__',
            '__wx_video_info__', '__WX_VIDEO_INFO__',
            '__finderVideoData__', '__finderFeedData__',
            'finderVideoInfo', 'finderFeedInfo'
        ];
        for (var i = 0; i < watchNames.length; i++) {
            (function(name) {
                if (window[name] !== undefined) {
                    // 已存在，直接检查
                    try {
                        inspectMessagePayload(window[name], 'window_watched:' + name);
                    } catch (e) {
                        // 忽略
                    }
                    return;
                }
                var storedValue = undefined;
                try {
                    Object.defineProperty(window, name, {
                        configurable: true,
                        enumerable: true,
                        get: function() { return storedValue; },
                        set: function(newValue) {
                            storedValue = newValue;
                            console.log('[VidFlow] 检测到 window.' + name + ' 赋值');
                            try {
                                inspectMessagePayload(newValue, 'window_set:' + name);
                            } catch (e) {
                                // 忽略
                            }
                            // 恢复普通属性
                            try {
                                Object.defineProperty(window, name, {
                                    configurable: true,
                                    enumerable: true,
                                    writable: true,
                                    value: newValue
                                });
                            } catch (e) {
                                // 忽略
                            }
                        }
                    });
                } catch (e) {
                    // 忽略 defineProperty 失败（属性可能已存在且不可配置）
                }
            })(watchNames[i]);
        }

        console.log('[VidFlow] 属性赋值拦截器已启用');
    }

    function collectKnownStateRoots() {
        var roots = [];
        var stateKeys = [
            '__INITIAL_STATE__',
            '__INITIAL_DATA__',
            '__NEXT_DATA__',
            '__NUXT__',
            '__PRELOADED_STATE__',
            '__APOLLO_STATE__',
            '__wx_channels_state__',
            '__WX_CHANNELS_STATE__',
            '__wx_channels_store__',
            '__wx_channels_live_store__',
            '__PINIA__',
            'WXU',
            'WXE'
        ];

        for (var i = 0; i < stateKeys.length; i++) {
            var value = window[stateKeys[i]];
            if (value) roots.push(value);
        }

        try {
            if (window.__STORE__ && typeof window.__STORE__.getState === 'function') {
                roots.push(window.__STORE__.getState());
            }
        } catch (e) {
            // ignore
        }

        try {
            if (window.__pinia && window.__pinia.state && window.__pinia.state.value) {
                roots.push(window.__pinia.state.value);
            }
        } catch (e) {
            // ignore
        }

        return roots;
    }

    function getDocumentHtmlSnapshot() {
        try {
            if (!document.documentElement) return '';
            var html = document.documentElement.outerHTML || '';
            if (!html) return '';
            if (html.length > 1200000) {
                return html.slice(0, 1200000);
            }
            return html;
        } catch (e) {
            return '';
        }
    }

    function firstNonEmpty(values) {
        if (!values || !values.length) return null;
        for (var i = 0; i < values.length; i++) {
            var value = values[i];
            if (value === null || value === undefined) continue;
            if (typeof value === 'string') {
                var trimmed = value.trim();
                if (trimmed) return trimmed;
                continue;
            }
            return value;
        }
        return null;
    }

    function getMetaContent(selector) {
        try {
            var node = document.querySelector(selector);
            if (!node) return null;
            return node.getAttribute('content') || null;
        } catch (e) {
            return null;
        }
    }

    function getNodeAttributeTitle(node) {
        if (!node) return null;

        var best = null;
        var attributes = [
            'data-title',
            'data-desc',
            'data-description',
            'data-content',
            'data-caption',
            'data-text',
            'data-name',
            'data-summary',
            'title',
            'aria-label',
            'alt'
        ];

        if (typeof node.getAttribute === 'function') {
            for (var i = 0; i < attributes.length; i++) {
                best = pickBetterTitle(best, node.getAttribute(attributes[i]));
            }
        }

        try {
            if (node.dataset) {
                var datasetKeys = ['title', 'desc', 'description', 'content', 'caption', 'text', 'name', 'summary'];
                for (var j = 0; j < datasetKeys.length; j++) {
                    best = pickBetterTitle(best, node.dataset[datasetKeys[j]]);
                }
            }
        } catch (e) {
            // ignore dataset access failures
        }

        return best;
    }

    function getOwnTextValue(node) {
        if (!node) return null;
        try {
            if (node.childNodes && node.childNodes.length) {
                var parts = [];
                for (var i = 0; i < node.childNodes.length; i++) {
                    var child = node.childNodes[i];
                    if (child && child.nodeType === 3 && child.textContent) {
                        parts.push(child.textContent);
                    }
                }
                var ownText = sanitizeTitleValue(parts.join(' ').replace(/\s+/g, ' ').trim());
                if (ownText) return ownText;
            }
        } catch (e) {
            // ignore child node access failures
        }

        return sanitizeTitleValue((node.textContent || node.innerText || '').replace(/\s+/g, ' ').trim());
    }

    function getTextFromRoot(root, selectors, maxNodes) {
        if (!root || !selectors || !selectors.length) return null;
        maxNodes = typeof maxNodes === 'number' ? maxNodes : 12;
        var best = null;

        for (var i = 0; i < selectors.length; i++) {
            try {
                var nodes = root.querySelectorAll ? root.querySelectorAll(selectors[i]) : [];
                if (!nodes || !nodes.length) continue;
                for (var j = 0; j < nodes.length && j < maxNodes; j++) {
                    var node = nodes[j];
                    best = pickBetterTitle(best, getNodeAttributeTitle(node));
                    best = pickBetterTitle(best, getOwnTextValue(node));
                }
            } catch (e) {
                // ignore selector errors
            }
        }
        return best;
    }

    function getTextFromSelectors(selectors) {
        return getTextFromRoot(document, selectors, 16);
    }

    function pushUniqueNode(list, node) {
        if (!node) return;
        if (list.indexOf(node) === -1) {
            list.push(node);
        }
    }

    function getNearbyVideoTitle(video) {
        if (!video) return null;

        var selectors = [
            '[data-title]',
            '[data-desc]',
            '[data-description]',
            '[data-content]',
            '[data-caption]',
            '[data-text]',
            '[data-name]',
            '[data-summary]',
            '[title]',
            '[aria-label]',
            '[alt]',
            '[role="heading"]',
            '[role="img"][aria-label]',
            '[class*="title"]',
            '[class*="desc"]',
            '[class*="caption"]',
            '[class*="content"]',
            '[class*="summary"]',
            '[class*="name"]',
            '[class*="text"]',
            'figcaption',
            'h1',
            'h2',
            'h3',
            'a',
            'p',
            'span'
        ];
        var best = null;
        var roots = [];
        var current = video;

        for (var depth = 0; current && depth < 3; depth++) {
            pushUniqueNode(roots, current);
            current = current.parentElement;
        }

        for (var rootIndex = 0; rootIndex < roots.length; rootIndex++) {
            var root = roots[rootIndex];
            if (!root) continue;

            best = pickBetterTitle(best, getNodeAttributeTitle(root));
            best = pickBetterTitle(best, getOwnTextValue(root));
            best = pickBetterTitle(best, getTextFromRoot(root, selectors, 8));
        }

        return best;
    }

    function mergeCacheKeySets() {
        var merged = [];
        for (var i = 0; i < arguments.length; i++) {
            var values = arguments[i];
            if (!values) continue;
            for (var j = 0; j < values.length; j++) {
                addUniqueString(merged, values[j]);
            }
        }
        return merged;
    }

    function buildDomFallbackFeed(baseFeed, htmlSnapshot) {
        // 优先使用 meta 标签和 data-* 属性（可靠性较高）
        var metaTitle = firstNonEmpty([
            getMetaContent('meta[property="og:title"]'),
            getMetaContent('meta[name="description"]')
        ]);
        // DOM 扫描标题（可靠性较低，容易采集到 UI 文本）
        var domScanTitle = getTextFromSelectors([
                '[data-desc]',
                '[data-title]',
                '[data-description]',
                '[data-content]',
                '[data-caption]',
                '.desc',
                '.title',
                '.wx-title',
                '.wx-desc',
                '[class*="title"]',
                '[class*="desc"]',
                'h1',
                'h2',
                'h3'
        ]);
        // 对 DOM 扫描标题进行额外验证：纯 ASCII 长句通常是 UI 文本不是视频标题
        var sanitizedDomScan = sanitizeTitleValue(domScanTitle);
        if (sanitizedDomScan && /^[\x00-\x7F]+$/.test(sanitizedDomScan) && sanitizedDomScan.length > 15 && (sanitizedDomScan.split(/\s+/).length > 4)) {
            // 纯英文且超过 4 个单词的长句，在微信视频号场景下极不可能是视频标题
            sanitizedDomScan = null;
        }
        var domTitle = metaTitle || sanitizedDomScan || (baseFeed && baseFeed.title) || null;
        var domThumb = firstNonEmpty([
            normalizeAssetUrl(getMetaContent('meta[property="og:image"]')),
            normalizeAssetUrl(getMetaContent('meta[name="twitter:image"]')),
            normalizeAssetUrl(
                (function() {
                    try {
                        var posterNode = document.querySelector('video[poster], img[src*="qpic"], img[src*="qlogo"]');
                        if (!posterNode) return null;
                        return posterNode.getAttribute('poster') || posterNode.getAttribute('src');
                    } catch (e) {
                        return null;
                    }
                })()
            ),
            baseFeed && baseFeed.thumbUrl
        ]);
        var cacheKeys = mergeCacheKeySets(
            baseFeed && baseFeed.cacheKeys ? baseFeed.cacheKeys : [],
            extractCacheKeysFromText(htmlSnapshot || ''),
            extractCacheKeysFromText(window.location.href || '')
        );

        return {
            url: baseFeed && baseFeed.url ? baseFeed.url : null,
            title: sanitizeTitleValue(domTitle),
            author: baseFeed && baseFeed.author ? baseFeed.author : null,
            decodeKey: baseFeed && baseFeed.decodeKey ? normalizeDecodeKeyValue(baseFeed.decodeKey) : null,
            thumbUrl: domThumb || null,
            duration: baseFeed && baseFeed.duration ? baseFeed.duration : 0,
            width: baseFeed && baseFeed.width ? baseFeed.width : 0,
            height: baseFeed && baseFeed.height ? baseFeed.height : 0,
            fileSize: baseFeed && baseFeed.fileSize ? baseFeed.fileSize : 0,
            cacheKeys: cacheKeys,
            pageUrl: window.location.href
        };
    }

    function extractFeedsFromDom(reason) {
        try {
            var htmlSnapshot = getDocumentHtmlSnapshot();
            var baseFeed = htmlSnapshot ? extractFeedFromInlineText(htmlSnapshot) : null;
            var domFallbackFeed = buildDomFallbackFeed(baseFeed, htmlSnapshot);
            var discovered = [];
            var videos = document.querySelectorAll('video');

            for (var i = 0; i < videos.length; i++) {
                var video = videos[i];
                var sourceNode = null;
                try {
                    sourceNode = video.querySelector('source[src]');
                } catch (e) {
                    sourceNode = null;
                }

                var feed = {
                    url: normalizeUrlValue(
                        firstNonEmpty([
                            video.currentSrc,
                            video.src,
                            video.getAttribute('src'),
                            video.getAttribute('data-src'),
                            sourceNode ? sourceNode.getAttribute('src') : null,
                            domFallbackFeed.url
                        ])
                    ),
                    title: sanitizeTitleValue(firstNonEmpty([
                        getNearbyVideoTitle(video),
                        domFallbackFeed.title
                    ])),
                    author: domFallbackFeed.author,
                    decodeKey: normalizeDecodeKeyValue(firstNonEmpty([
                        video.getAttribute('data-decode-key'),
                        video.getAttribute('data-decrypt-key'),
                        video.dataset ? (video.dataset.decodeKey || video.dataset.decryptKey) : null,
                        domFallbackFeed.decodeKey
                    ])),
                    thumbUrl: firstNonEmpty([
                        normalizeAssetUrl(video.getAttribute('poster')),
                        domFallbackFeed.thumbUrl
                    ]),
                    duration: Math.round(parseFloat(video.duration || 0)) || domFallbackFeed.duration || 0,
                    width: parseInt(video.videoWidth || 0, 10) || domFallbackFeed.width || 0,
                    height: parseInt(video.videoHeight || 0, 10) || domFallbackFeed.height || 0,
                    fileSize: domFallbackFeed.fileSize || 0,
                    cacheKeys: mergeCacheKeySets(
                        domFallbackFeed.cacheKeys,
                        extractCacheKeysFromText(video.outerHTML || '')
                    ),
                    pageUrl: window.location.href
                };

                if (feed.url || feed.decodeKey || (feed.cacheKeys && feed.cacheKeys.length > 0)) {
                    discovered.push(feed);
                }
            }

            if (discovered.length === 0) {
                if (
                    domFallbackFeed.url ||
                    domFallbackFeed.decodeKey ||
                    (domFallbackFeed.cacheKeys && domFallbackFeed.cacheKeys.length > 0)
                ) {
                    discovered.push(domFallbackFeed);
                }
            }

            if (discovered.length > 0) {
                console.log('[VidFlow] DOM 扫描发现', discovered.length, '个 feed, 来源:', reason,
                    'videos=' + videos.length,
                    '首个: url=' + (discovered[0].url ? 'yes' : 'no'),
                    'title=' + (discovered[0].title || 'no'),
                    'dk=' + (discovered[0].decodeKey ? 'yes' : 'no'),
                    'thumb=' + (discovered[0].thumbUrl ? 'yes' : 'no'),
                    'keys=' + (discovered[0].cacheKeys || []).length
                );
            }

            submitFeedsToBackend(discovered, reason + ' dom');
        } catch (e) {
            console.warn('[VidFlow] Failed to scan DOM state:', e);
        }
    }

    function extractFeedFromInlineText(text) {
        if (!text || typeof text !== 'string') return null;
        var normalized = text
            .replace(/\\u0026/g, '&')
            .replace(/\\\//g, '/');

        var urlMatch = normalized.match(/(?:(?:https?:)?\/\/)?(?:finder\.video\.qq\.com|findervideodownload\.video\.qq\.com|(?:[\w-]+\.)?tc\.qq\.com)\/[^"'\\\s<>]+/i);
        var decodeMatch = normalized.match(/(?:["'](?:decodeKey|decode_key|decodeKey64|decode_key64|decryptKey|decrypt_key|decryptionKey|decryption_key|decryptSeed|decrypt_seed|seed|seedValue|seed_value|mediaKey|media_key|videoKey|video_key|dk|\$numberLong)["']|\b(?:decodeKey|decode_key|decodeKey64|decode_key64|decryptKey|decrypt_key|decryptionKey|decryption_key|decryptSeed|decrypt_seed|seed|seedValue|seed_value|mediaKey|media_key|videoKey|video_key|dk|\$numberLong)\b)\s*[:=]\s*["']?([1-9]\d{0,127})(?:n)?["']?/i);
        var titleMatch = normalized.match(/(?:["'](?:title|desc|description|feedDesc|videoTitle|content|contentDesc|objectDesc)["']|\b(?:title|desc|description|feedDesc|videoTitle|content|contentDesc|objectDesc)\b)\s*[:=]\s*["']([^"'\n]{1,160})["']/i);
        var thumbMatch = normalized.match(/(?:(?:https?:)?\/\/)?(?:[^"'\\\s<>]*(?:qpic|wx\.qlogo|wx\.qpic|qlogo)\.[^"'\\\s<>]+|res\.wx\.qq\.com\/[^"'\\\s<>]+)/i);
        var cacheKeys = extractCacheKeysFromText(normalized);

        if (!urlMatch && !decodeMatch && cacheKeys.length === 0) return null;
        if (!urlMatch && !decodeMatch && !titleMatch && !thumbMatch) return null;

        return {
            url: urlMatch ? normalizeUrlValue(urlMatch[0]) : null,
            title: titleMatch ? sanitizeTitleValue(titleMatch[1]) : null,
            author: null,
            decodeKey: decodeMatch ? normalizeDecodeKeyValue(decodeMatch[1]) : null,
            thumbUrl: thumbMatch ? normalizeAssetUrl(thumbMatch[0]) : null,
            duration: 0,
            width: 0,
            height: 0,
            fileSize: 0,
            cacheKeys: cacheKeys,
            pageUrl: window.location.href
        };
    }

    function scanInlineScripts(reason) {
        try {
            var scripts = document.querySelectorAll('script');
            var discovered = [];

            for (var i = 0; i < scripts.length; i++) {
                var script = scripts[i];
                var text = script.textContent || '';
                if (!text) continue;
                if (text.length > 800000) continue;
                if (
                    text.indexOf('decodeKey') === -1 &&
                    text.indexOf('decryptionKey') === -1 &&
                    text.indexOf('seedValue') === -1 &&
                    text.indexOf('mediaKey') === -1 &&
                    text.indexOf('videoKey') === -1 &&
                    text.indexOf('decryptKey') === -1 &&
                    text.indexOf('finder.video.qq.com') === -1 &&
                    text.indexOf('encfilekey') === -1 &&
                    text.indexOf('taskid') === -1 &&
                    text.indexOf('feedid') === -1 &&
                    text.indexOf('objectid') === -1 &&
                    text.indexOf('res.wx.qq.com') === -1
                ) {
                    continue;
                }

                try {
                    var trimmed = text.trim();
                    if (
                        (script.type && script.type.indexOf('json') !== -1) ||
                        trimmed.indexOf('{') === 0 ||
                        trimmed.indexOf('[') === 0
                    ) {
                        var parsed = JSON.parse(trimmed);
                        var parsedFeeds = extractFeedData(parsed);
                        for (var parsedIndex = 0; parsedIndex < parsedFeeds.length; parsedIndex++) {
                            discovered.push(parsedFeeds[parsedIndex]);
                        }
                    }
                } catch (parseError) {
                    var inferredFeed = extractFeedFromInlineText(text);
                    if (inferredFeed) {
                        discovered.push(inferredFeed);
                    }
                }
            }

            submitFeedsToBackend(discovered, reason + ' inline_script');
        } catch (e) {
            console.warn('[VidFlow] 扫描内联脚本失败:', e);
        }
    }

    function isScannableWindowObject(value) {
        if (!value || typeof value !== 'object') return false;
        if (value === window || value === document) return false;
        try {
            if (typeof Window !== 'undefined' && value instanceof Window) return false;
        } catch (e) {}
        try {
            if (typeof Node !== 'undefined' && value instanceof Node) return false;
        } catch (e) {}
        return true;
    }

    function scanWindowProperties(reason) {
        try {
            var names = Object.getOwnPropertyNames(window || {});
            var stringCandidates = [];
            var objectCount = 0;
            var stringCount = 0;

            for (var i = 0; i < names.length; i++) {
                var name = names[i];
                if (!name || name === '__vidflow_injected__') continue;

                var lowerName = String(name).toLowerCase();
                var looksRelevant =
                    lowerName.indexOf('state') !== -1 ||
                    lowerName.indexOf('store') !== -1 ||
                    lowerName.indexOf('data') !== -1 ||
                    lowerName.indexOf('finder') !== -1 ||
                    lowerName.indexOf('channel') !== -1 ||
                    lowerName.indexOf('feed') !== -1 ||
                    lowerName.indexOf('video') !== -1 ||
                    lowerName.indexOf('cache') !== -1 ||
                    lowerName.indexOf('pinia') !== -1 ||
                    lowerName.indexOf('redux') !== -1 ||
                    lowerName.indexOf('apollo') !== -1 ||
                    lowerName.indexOf('wxu') !== -1 ||
                    lowerName.indexOf('wxe') !== -1 ||
                    (
                        lowerName.indexOf('api') !== -1 &&
                        (
                            lowerName.indexOf('finder') !== -1 ||
                            lowerName.indexOf('channel') !== -1 ||
                            lowerName.indexOf('wechat') !== -1 ||
                            lowerName.indexOf('wx') !== -1
                        )
                    ) ||
                    (
                        lowerName.indexOf('event') !== -1 &&
                        (
                            lowerName.indexOf('finder') !== -1 ||
                            lowerName.indexOf('channel') !== -1 ||
                            lowerName.indexOf('wx') !== -1
                        )
                    ) ||
                    lowerName.indexOf('preload') !== -1 ||
                    lowerName.indexOf('initial') !== -1 ||
                    lowerName.indexOf('__') === 0;
                if (!looksRelevant) continue;

                var value;
                try {
                    value = window[name];
                } catch (e) {
                    continue;
                }

                if (typeof value === 'string') {
                    if (stringCount >= 24) continue;
                    if (value.length < 32 || value.length > 800000) continue;
                    if (
                        value.indexOf('decodeKey') === -1 &&
                        value.indexOf('decryptionKey') === -1 &&
                        value.indexOf('seedValue') === -1 &&
                        value.indexOf('mediaKey') === -1 &&
                        value.indexOf('videoKey') === -1 &&
                        value.indexOf('decryptKey') === -1 &&
                        value.indexOf('finder.video.qq.com') === -1 &&
                        value.indexOf('encfilekey') === -1 &&
                        value.indexOf('taskid') === -1 &&
                        value.indexOf('feedid') === -1 &&
                        value.indexOf('objectid') === -1
                    ) {
                        continue;
                    }
                    stringCount += 1;
                    var inferredFeed = extractFeedFromInlineText(value);
                    if (inferredFeed) {
                        stringCandidates.push(inferredFeed);
                    }
                    continue;
                }

                if (!isScannableWindowObject(value)) continue;
                if (objectCount >= 48) continue;
                objectCount += 1;
                discoverAndHookWXRuntimeValue(value, reason + ' window_runtime:' + name, 0, []);
                submitFeedsToBackend(extractFeedData(value), reason + ' window_prop:' + name);
            }

            submitFeedsToBackend(stringCandidates, reason + ' window_string');
        } catch (e) {
            console.warn('[VidFlow] Failed to scan window properties:', e);
        }
    }

    function collectReactPayloadsFromNode(node) {
        var payloads = [];
        if (!node || typeof node !== 'object') return payloads;

        var names = [];
        try {
            names = Object.getOwnPropertyNames(node);
        } catch (e) {
            return payloads;
        }

        function addPayload(value) {
            if (!value || typeof value !== 'object') return;
            if (payloads.indexOf(value) === -1) {
                payloads.push(value);
            }
        }

        function collectFiberPayloads(fiber) {
            // 向上遍历 parent 链（增加到 20 层）
            var cursor = fiber;
            var depth = 0;
            while (cursor && typeof cursor === 'object' && depth < 20) {
                addPayload(cursor.memoizedProps);
                addPayload(cursor.pendingProps);
                addPayload(cursor.memoizedState);
                addPayload(cursor.dependencies);
                addPayload(cursor.updateQueue);
                // 检查 stateNode 的状态
                if (cursor.stateNode && typeof cursor.stateNode === 'object') {
                    addPayload(cursor.stateNode.memoizedProps);
                    addPayload(cursor.stateNode.pendingProps);
                    addPayload(cursor.stateNode.memoizedState);
                    addPayload(cursor.stateNode.props);
                    addPayload(cursor.stateNode.state);
                    // Vue 3 组件实例
                    if (cursor.stateNode.$ && typeof cursor.stateNode.$ === 'object') {
                        addPayload(cursor.stateNode.$.props);
                        addPayload(cursor.stateNode.$.data);
                        addPayload(cursor.stateNode.$.setupState);
                    }
                }
                // 检查 context
                if (cursor.context && typeof cursor.context === 'object') {
                    addPayload(cursor.context);
                }
                cursor = cursor.return;
                depth += 1;
            }

            // 向下遍历 child/sibling（最多 3 层深度，收集子组件的 props）
            function collectChildFibers(fiberNode, childDepth) {
                if (!fiberNode || typeof fiberNode !== 'object' || childDepth > 3) return;
                if (payloads.length > 200) return; // 避免过多载荷
                addPayload(fiberNode.memoizedProps);
                addPayload(fiberNode.memoizedState);
                if (fiberNode.child) {
                    collectChildFibers(fiberNode.child, childDepth + 1);
                }
                if (fiberNode.sibling && childDepth <= 2) {
                    collectChildFibers(fiberNode.sibling, childDepth + 1);
                }
            }

            if (fiber && fiber.child) {
                collectChildFibers(fiber.child, 0);
            }
        }

        for (var i = 0; i < names.length; i++) {
            var name = names[i];
            if (!name) continue;

            var value;
            try {
                value = node[name];
            } catch (e) {
                continue;
            }

            if (name.indexOf('__reactProps$') === 0 || name.indexOf('__reactEventHandlers$') === 0) {
                addPayload(value);
            } else if (
                name.indexOf('__reactFiber$') === 0 ||
                name.indexOf('__reactInternalInstance$') === 0 ||
                name.indexOf('__reactContainer$') === 0
            ) {
                addPayload(value);
                collectFiberPayloads(value);
            } else if (name.indexOf('__vueParentComponent') === 0 && value && typeof value === 'object') {
                addPayload(value.props);
                addPayload(value.data);
                addPayload(value.setupState);
            }
        }

        return payloads;
    }

    function scanReactTree(reason) {
        try {
            var nodes = [];

            function addNode(node) {
                if (!node) return;
                if (nodes.indexOf(node) === -1) {
                    nodes.push(node);
                }
            }

            addNode(document.getElementById('app'));
            addNode(document.getElementById('root'));
            addNode(document.getElementById('__next'));
            addNode(document.getElementById('page'));
            addNode(document.getElementById('container'));
            addNode(document.body);

            // 微信特有的容器选择器
            var wxSelectors = [
                '.feed-card', '.video-player', '.finder-video',
                '.player-container', '[class*="video"]', '[class*="feed"]',
                '[class*="player"]', '[class*="finder"]',
                '[data-feed-id]', '[data-object-id]', '[data-video-id]'
            ];
            for (var si = 0; si < wxSelectors.length; si++) {
                try {
                    var wxNodes = document.querySelectorAll(wxSelectors[si]);
                    for (var ni = 0; ni < wxNodes.length && ni < 5; ni++) {
                        addNode(wxNodes[ni]);
                    }
                } catch (e) {
                    // 忽略无效选择器
                }
            }

            var videos = document.querySelectorAll('video');
            for (var i = 0; i < videos.length; i++) {
                var current = videos[i];
                var steps = 0;
                while (current && steps < 15) {
                    addNode(current);
                    current = current.parentElement;
                    steps += 1;
                }
            }

            // 检查 Vue 3 应用实例
            try {
                var appEl = document.getElementById('app') || document.body;
                if (appEl && appEl.__vue_app__) {
                    var vueApp = appEl.__vue_app__;
                    if (vueApp.config && vueApp.config.globalProperties) {
                        var globals = vueApp.config.globalProperties;
                        if (globals.$store) {
                            submitFeedsToBackend(extractFeedData(globals.$store.state || globals.$store), reason + ' vue_store');
                        }
                        if (globals.$pinia) {
                            var piniaStores = globals.$pinia.state && globals.$pinia.state.value;
                            if (piniaStores) {
                                submitFeedsToBackend(extractFeedData(piniaStores), reason + ' pinia_store');
                            }
                        }
                    }
                }
            } catch (e) {
                // 忽略 Vue 检测失败
            }

            for (var nodeIndex = 0; nodeIndex < nodes.length; nodeIndex++) {
                var payloads = collectReactPayloadsFromNode(nodes[nodeIndex]);
                for (var payloadIndex = 0; payloadIndex < payloads.length; payloadIndex++) {
                    submitFeedsToBackend(extractFeedData(payloads[payloadIndex]), reason + ' react');
                }
            }
        } catch (e) {
            console.warn('[VidFlow] Failed to scan React tree:', e);
        }
    }

    var lastScanTime = 0;
    var SCAN_MIN_INTERVAL_MS = 2000;  // 扫描最小间隔 2 秒
    var deferredScanReason = null;
    var deferredScanTimer = null;

    function scanGlobalState(reason) {
        // 扫描级节流：防止 DOM mutation / video event 触发过于频繁的扫描
        var now = Date.now();
        var elapsed = now - lastScanTime;
        if (elapsed < SCAN_MIN_INTERVAL_MS) {
            // 延迟执行，保留最新的 reason
            deferredScanReason = reason;
            if (!deferredScanTimer) {
                deferredScanTimer = setTimeout(function() {
                    deferredScanTimer = null;
                    var r = deferredScanReason;
                    deferredScanReason = null;
                    if (r) scanGlobalStateImpl(r + '_deferred');
                }, SCAN_MIN_INTERVAL_MS - elapsed);
            }
            return;
        }
        scanGlobalStateImpl(reason);
    }

    function scanGlobalStateImpl(reason) {
        lastScanTime = Date.now();
        try {
            discoverAndHookWXRuntime(reason);
            var roots = collectKnownStateRoots();
            if (roots.length > 0) {
                console.log('[VidFlow] 扫描全局状态:', reason, '找到', roots.length, '个状态根');
            }
            for (var i = 0; i < roots.length; i++) {
                discoverAndHookWXRuntimeValue(roots[i], reason + ' root_runtime:' + i, 0, []);
                var stateFeeds = extractFeedData(roots[i]);
                if (stateFeeds.length > 0) {
                    console.log('[VidFlow] 从全局状态提取到', stateFeeds.length, '个 feed, 来源:', reason,
                        '首个: url=' + (stateFeeds[0].url ? 'yes' : 'no'),
                        'title=' + (stateFeeds[0].title || 'no'),
                        'dk=' + (stateFeeds[0].decodeKey ? 'yes' : 'no'),
                        'thumb=' + (stateFeeds[0].thumbUrl ? 'yes' : 'no'),
                        'keys=' + (stateFeeds[0].cacheKeys || []).length
                    );
                }
                submitFeedsToBackend(stateFeeds, reason + ' global_state');
            }
            extractFeedsFromDom(reason);
            scanReactTree(reason);
            scanWindowProperties(reason);
            scanInlineScripts(reason);
        } catch (e) {
            console.warn('[VidFlow] 扫描页面状态失败:', e);
        }
    }

    function scheduleMetadataScans() {
        var delays = [0, 800, 2000, 4000, 7000, 12000, 20000, 30000];
        for (var i = 0; i < delays.length; i++) {
            (function(delay) {
                setTimeout(function() {
                    scanGlobalState('scheduled_' + delay);
                }, delay);
            })(delays[i]);
        }

        window.addEventListener('load', function() {
            setTimeout(function() {
                scanGlobalState('window_load');
            }, 300);
        });

        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) {
                setTimeout(function() {
                    scanGlobalState('visibility_change');
                }, 300);
            }
        });

        if (window.MutationObserver && document.documentElement) {
            var debounceTimer = null;
            var observer = new MutationObserver(function(mutations) {
                for (var i = 0; i < mutations.length; i++) {
                    if (mutations[i].addedNodes && mutations[i].addedNodes.length > 0) {
                        if (debounceTimer) clearTimeout(debounceTimer);
                        debounceTimer = setTimeout(function() {
                            scanGlobalState('dom_mutation');
                        }, 600);
                        break;
                    }
                }
            });
            observer.observe(document.documentElement, { childList: true, subtree: true });
        }

        // 前 60 秒密集扫描（每 5 秒），之后降低为每 15 秒，持续运行
        // 以确保用户切换视频后仍能捕获新的元数据
        var periodicRuns = 0;
        var periodicTimer = setInterval(function() {
            periodicRuns += 1;
            if (!document.hidden) {
                scanGlobalState('periodic_' + periodicRuns);
            }
            if (periodicRuns >= 12) {
                // 切换到慢速周期扫描（每 15 秒），不再停止
                clearInterval(periodicTimer);
                setInterval(function() {
                    periodicRuns += 1;
                    if (!document.hidden) {
                        scanGlobalState('slow_periodic_' + periodicRuns);
                    }
                }, 15000);
            }
        }, 5000);
    }

    function scheduleVideoEventScans() {
        var debounceTimer = null;

        function queue(reason, delay) {
            setTimeout(function() {
                scanGlobalState(reason);
            }, delay);
        }

        function onVideoActivity(reason) {
            // 只保留一次延迟扫描（scanGlobalState 内部有节流，不需要多次触发）
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function() {
                scanGlobalState(reason);
            }, 800);
        }

        var events = ['play', 'playing', 'loadedmetadata', 'loadeddata', 'durationchange', 'canplay'];
        for (var i = 0; i < events.length; i++) {
            (function(eventName) {
                document.addEventListener(eventName, function(evt) {
                    var target = evt && evt.target;
                    if (!target || !target.tagName || String(target.tagName).toUpperCase() !== 'VIDEO') {
                        return;
                    }
                    onVideoActivity('video_' + eventName);
                }, true);
            })(events[i]);
        }
    }

    hookFetch();
    hookXHR();
    hookHistoryNavigation();
    hookNativeBridges();
    hookPropertyAssignment();
    discoverAndHookWXRuntime('bootstrap');
    scheduleMetadataScans();
    scheduleVideoEventScans();

    // =========================================
    // iframe 注入传播：将脚本注入到子 iframe 中
    // 解决 HTTP/2 连接复用导致新页面未被代理注入的问题
    // =========================================
    function tryInjectIntoFrame(frame) {
        try {
            var frameDoc = frame.contentDocument || (frame.contentWindow && frame.contentWindow.document);
            if (!frameDoc) return;
            // 检查 iframe 是否是微信视频号相关页面
            var frameUrl = '';
            try { frameUrl = frame.contentWindow.location.href || ''; } catch (e) { return; }  // 跨域 iframe 忽略
            if (frameUrl.indexOf('channels.weixin.qq.com') === -1 &&
                frameUrl.indexOf('finder.video') === -1 &&
                frameUrl.indexOf('mp.weixin.qq.com') === -1) return;
            // 检查是否已注入
            if (frame.contentWindow.__vidflow_injected__) return;
            // 注入脚本到 iframe
            var scriptEl = frameDoc.createElement('script');
            scriptEl.textContent = '(' + arguments.callee.caller.toString() + ')();';
            // 更安全的方式：通过 script src 加载
            var scriptSrc = frameDoc.createElement('script');
            scriptSrc.src = (frame.contentWindow.location.origin || window.location.origin) + '/__vidflow/channels/inject.js';
            scriptSrc.async = true;
            (frameDoc.head || frameDoc.documentElement || frameDoc).appendChild(scriptSrc);
            console.log('[VidFlow] 向子 iframe 注入脚本:', frameUrl.substring(0, 80));
        } catch (e) {
            // 跨域 iframe 会抛安全异常，忽略
        }
    }

    function scanAndInjectFrames() {
        try {
            var frames = document.querySelectorAll('iframe, webview');
            for (var i = 0; i < frames.length; i++) {
                tryInjectIntoFrame(frames[i]);
            }
            // 也尝试通过 window.open 打开的窗口（微信视频号可能用 window.open）
            // 注意：无法访问 window.open 的返回值，只能在被打开的页面中检测
        } catch (e) {}
    }

    // 监听新 iframe 的创建
    if (typeof MutationObserver === 'function') {
        var frameObserver = new MutationObserver(function(mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var added = mutations[i].addedNodes;
                if (!added) continue;
                for (var j = 0; j < added.length; j++) {
                    var node = added[j];
                    if (!node || !node.tagName) continue;
                    var tag = node.tagName.toUpperCase();
                    if (tag === 'IFRAME' || tag === 'WEBVIEW') {
                        // iframe 加载后注入
                        (function(frame) {
                            frame.addEventListener('load', function() {
                                setTimeout(function() { tryInjectIntoFrame(frame); }, 300);
                            });
                        })(node);
                    }
                }
            }
        });
        frameObserver.observe(document.documentElement, { childList: true, subtree: true });
    }

    // 定期扫描 iframe（处理已存在的 iframe）
    setTimeout(scanAndInjectFrames, 2000);
    setTimeout(scanAndInjectFrames, 8000);

    console.log('[VidFlow] 初始化完成，启用页面运行时 hook + 消息通道 hook + 属性拦截 + 状态扫描 + iframe 传播');
})();

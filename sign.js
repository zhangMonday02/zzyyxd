// 作者 古月
// 开发时间 2025/7/12 09:38
// 文件名 mz

require('./crypto-js')

// 写一个AESCBC加密的方法


function AESCBCEncryptF(data) {
    const keyHex = CryptoJS.enc.Utf8.parse("c175a358550d02e2")
    const ivHex = CryptoJS.enc.Utf8.parse("0123456789ABCDEF")
    const encrypted = CryptoJS.AES.encrypt(data, keyHex, {
        iv: ivHex,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    })
    return encrypted.toString()
}


function AESCBCEncryptS(data) {
    data = [
        "ab034ec0643f91399eb33e062dc7fae1",
        "W",
        data,
        "W20220202",
        "CLOUD",
        ""
    ].join("#")
    const keyHex = CryptoJS.enc.Utf8.parse("45f8ac1e1de14397")
    const ivHex = CryptoJS.enc.Utf8.parse("0123456789ABCDEF")
    const encrypted = CryptoJS.AES.encrypt(data, keyHex, {
        iv: ivHex,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    })
    return encrypted.toString()
}

function hr() {
    var t, r, e = "";
    for (t = 0; t < 32; t++)
        r = 16 * Math.random() | 0,
        8 !== t && 12 !== t && 16 !== t && 20 !== t || (e += "-"),
            e += (12 === t ? 4 : 16 === t ? 3 & r | 8 : r).toString(16);
    return e
}

// signature 算法


// HMAC-SHA1 Function
function generateHmacSHA1(message, key) {
    // Generate HMAC-SHA1 using CryptoJS
    const hmac = CryptoJS.HmacSHA1(message, key);

    // Return the result in the specified format: { words: Array, sigBytes: Number }
    return {
        words: hmac.words,  // the HMAC as an array of 32-bit words
        sigBytes: hmac.sigBytes  // the number of bytes in the HMAC
    };
}


function clamp(t) {
    var r = t.words
        , n = t.sigBytes;
    r[n >>> 2] &= 4294967295 << 32 - n % 4 * 8,
        r.length = Math.ceil(n / 4)
}

function enc_stringify(t) {
    var r = t.words
        , n = t.sigBytes
        , e = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
    clamp(t);
    for (var i = [], o = 0; o < n; o += 3)
        for (var u = (r[o >>> 2] >>> 24 - o % 4 * 8 & 255) << 16 | (r[o + 1 >>> 2] >>> 24 - (o + 1) % 4 * 8 & 255) << 8 | r[o + 2 >>> 2] >>> 24 - (o + 2) % 4 * 8 & 255, c = 0; c < 4 && o + .75 * c < n; c++)
            i.push(e.charAt(u >>> 6 * (3 - c) & 63));
    var a = e.charAt(64);
    if (a)
        for (; i.length % 4;)
            i.push(a);
    return i.join("")
}

function rU() {
    var t, r, e = "";
    for (t = 0; t < 32; t++)
        r = 16 * Math.random() | 0,
        (8 === t || 12 === t || 16 === t || 20 === t) && (e += "-"),
            e += (12 === t ? 4 : 16 === t ? 3 & r | 8 : r).toString(16);
    return e
}

function rq(t) {
    return null == t ? null : encodeURIComponent(t).replace("+", "%20").replace("*", "%2A").replace("%7E", "~")
}

function rB(t, r) {
    delete t.Signature;
    var e = Object.keys(t);
    e.sort();
    var n = !0
        , i = ""
        , a = !0
        , o = !1
        , c = void 0;
    try {
        for (var u, f = e[Symbol.iterator](); !(a = (u = f.next()).done); a = !0) {
            var s = u.value;
            n ? n = !1 : i += "&";
            var l = t[s];
            i = i + rq(s) + "=" + rq(l)
        }
    } catch (t) {
        o = !0,
            c = t
    } finally {
        try {
            !a && null != f.return && f.return()
        } finally {
            if (o)
                throw c
        }
    }
    var h = "POST&";
    return function (t, r) {
        var e = generateHmacSHA1(r, t);
        // console.log(enc_stringify(e))
        return enc_stringify(e)
    }(r + "&", h = h + rq("/") + "&" + rq(i))
}


function Sign(params, key) {
    var res = AESCBCEncryptF("W.10001.c#saf-captcha#1mtt2vr1#captcha-normal#d6lm8n#cn")
    // console.log(res)
    res = AESCBCEncryptS(res)
    // console.log(res)
    var data = res;
    params['SignatureNonce'] = hr()
    // params = {
    //     "AccessKeyId": "LTAI5tSEBwYMwVKAQGpxmvTd",
    //     "SignatureMethod": "HMAC-SHA1",
    //     "SignatureVersion": "1.0",
    //     "Format": "JSON",
    //     "Timestamp": "2025-07-12T01:47:41Z",
    //     "Version": "2023-03-05",
    //     "Action": "InitCaptcha",
    //     "SceneId": "1mtt2vr1",
    //     "Language": "cn",
    //     "Mode": "popup",
    //     "DeviceData": "byAgDBTTWK6iQ63aLnMRvywYbJ50c453wUz9CdNf4pWB+H4EOu7koqzwbASi1Zy3mY5XY6IaH8GbWEipbrzhYXtDupGz6x7biQ1/4pLzaqip0OzQfqAbPPdvJ9vKDNwKbxjf68SnxScRk1+PpGmzGzLAisJpsEZTWklbwQbyqBLcct35gEH2XLTDXMJPG4OA",
    //     "SignatureNonce": "d3a49822-6d4a-4bec-b5d4-bf810482f331"
    // }
    params.Signature = rB(params, key)
    // console.log(params)
    return params
}

function getDeviceData() {
    var res = AESCBCEncryptF("W.10001.c#saf-captcha#6mw4mrmg#captcha-normal#s5fgoo#cn")
    // console.log(res)
    res = AESCBCEncryptS(res)
    // console.log(res)
    var data = res;

    return data
}

// Sign()

module.exports = {
    Sign,
    getDeviceData
}


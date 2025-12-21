require('./crypto-js')

function AESCBCEncrypt_RES(data, key) {
    const keyHex = CryptoJS.enc.Utf8.parse(key)
    const ivHex = CryptoJS.enc.Utf8.parse("0123456789ABCDEF")
    const encrypted = CryptoJS.AES.encrypt(data, keyHex, {
        iv: ivHex,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    })
    return encrypted.toString()
}

function getDeviceToken(config, Dynamic_Key) {
    Dynamic_Key = Dynamic_Key
    key = config.key
    token_params3 = [
        "W.10050",
        "",
        "",
        "",
        "",
        "Win32",
        "Edge",
        "143.0.0.0",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "104",
        Dynamic_Key,
        "8",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "cb00626a032d01f53c7804479a626d6a",
        "",
        "24",
        "",
        "iOS",
        "18.5",
        "",
        "",
        "",
        "",
        config.ip,
        "",
        "true",
        "",
        "",
        "932*430",
        "",
        "1",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "saf-captcha",
        "0",
        "",
        "",
        "8OLCbIkR4UV72FVwr6ByvSaB8OlOS4KRLCRec6Fr",
        (parseInt(config.timestamp) - 3000).toString(),
        "0p4ZX9b0cQwIygeSQtbzYfYHPZ3fIOOyC4hXrBqCgE",
        (parseInt(config.timestamp) - 3000 + 100).toString(),
        "mobile",
        "false",
        "vYgpzNFuhu",
        "9d4568c009d203ab10e33ea9953a0264",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        config.timestamp,
        "MSMwIzAjMCMwIzAjMCMwIzAjMCMxIzAjMCMwIzAjMCMwIzAjMCMwIzEjMCMxMTExMTExMDExMTExMTExMTExMTExMTExMQ==",
        "1",
        "1",
        "true",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        ""
    ].join("#")

    token_params3 = AESCBCEncrypt_RES(token_params3, key)
    token = [
        "WEB",
        config.sessionId,
        token_params3,
        "3515",
        // "b3426db5da7c65500431b21fe9077e1d"
    ]
    temp_token = token.join("#") + '#daye,raolewoba!'
    token_md5 = CryptoJS.MD5(temp_token).toString()
    token[4] = token_md5
    token = token.join("#")
    res_token = btoa(token)
    // console.log(res_token)
    return res_token
}





require('./crypto-js')
const {Sign} = require("./sign");

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

function getLog3Data(data, config) {
    deviceConfig = config
    key = deviceConfig.key
    firt_ = '1#0#0#0#0#0#0#0#0#0#1#0#0#0#0#0#0#0#0#0#1#0#11111110111111111111111111'
    res_firt_ = AESCBCEncrypt_RES(firt_, key)
    sec_ = '{"mousemove":[{"x":988,"y":502,"t":30},{"x":988,"y":502,"t":80},{"x":1043,"y":361,"t":2000},{"x":1032,"y":356,"t":2026},{"x":1032,"y":356,"t":2052},{"x":979,"y":352,"t":2078},{"x":690,"y":352,"t":2105},{"x":690,"y":352,"t":2130},{"x":474,"y":360,"t":2157},{"x":244,"y":360,"t":2724},{"x":422,"y":311,"t":2750},{"x":422,"y":311,"t":2775},{"x":646,"y":238,"t":2802},{"x":646,"y":238,"t":2827},{"x":665,"y":227,"t":2864},{"x":666,"y":227,"t":2912},{"x":666,"y":227,"t":2938},{"x":672,"y":224,"t":2965},{"x":679,"y":219,"t":2991},{"x":679,"y":219,"t":3017},{"x":686,"y":206,"t":3043},{"x":686,"y":206,"t":3068},{"x":699,"y":183,"t":3094},{"x":699,"y":183,"t":3120},{"x":704,"y":176,"t":3148},{"x":634,"y":194,"t":3305}],"mouseclick":[{"x":0,"y":0,"t":281},{"x":706,"y":172,"t":3316}],"keyup":[],"scrollTop":[{"scrollTop":"256.0","t":1615},{"scrollTop":"254.0","t":1656},{"scrollTop":"254.7","t":1728},{"scrollTop":"256.7","t":1770}],"scrollLeft":[],"clientType":"desktop","startTime":1765693886095,"timestamp":"1765693886028"}'
    res_sec_ = AESCBCEncrypt_RES(sec_, key)
    common_p3 = AESCBCEncrypt_RES('saf-captcha', key)
    common_p4 = AESCBCEncrypt_RES('W.10050', key)
    now_ts = +Date.now()
    common_p6 = AESCBCEncrypt_RES(now_ts + '', key)
    common_p6_2 = AESCBCEncrypt_RES((now_ts + 2) + '', key)
    params2 = [
        deviceConfig.sessionId,
        res_firt_,
        common_p3,
        common_p4,
        "",
        common_p6
    ].join("#")
    init_res_params2 = btoa(params2) + '-504'
    params3 = [
        deviceConfig.sessionId,
        res_sec_,
        common_p3,
        common_p4,
        "",
        common_p6_2
    ].join('#')
    init_res_params3 = btoa(params3)
    input_params3 = 'W.10050#saf-captcha#6mw4mrmg'
    input_init_params = [
        "511",
        init_res_params2,
        init_res_params3
    ].join("#")
    res_params7 = btoa(input_init_params)
    res_params3 = AESCBCEncrypt_RES(input_params3, key)
    res_data = [
        "ab034ec0643f91399eb33e062dc7fae1",
        "W",
        res_params3,
        "W20220202",
        "CLOUD",
        "79",
        res_params7
    ].join("#")
    res_data = AESCBCEncrypt_RES(res_data, "a549a55c60a39aa0")
    console.log(res_data)

    data['Data'] = res_data
    data = Sign(data, 'fpOKzILEajkqgSpr9VvU98FwAgIRcX')
    // data = formatToQueryString(data)
    return data
}

function formatToQueryString(obj) {
    const params = [];

    // 按照字母顺序排序键（阿里云API通常需要排序）
    const sortedKeys = Object.keys(obj);

    for (const key of sortedKeys) {
        let value = obj[key];

        // 确保值是字符串
        if (value !== null && value !== undefined) {
            value = String(value);

            // URL编码：特殊字符如 +, /, = 需要编码
            // 注意：Data字段中的 '+' 需要编码为 %2B
            const encodedValue = encodeURIComponent(value)
                .replace(/\+/g, '%2B')   // 加号
                .replace(/\//g, '%2F')   // 斜杠
                .replace(/'/g, '%27')    // 单引号
                .replace(/"/g, '%22')    // 双引号
                .replace(/\(/g, '%28')   // 左括号
                .replace(/\)/g, '%29');  // 右括号

            params.push(`${key}=${encodedValue}`);
        }
    }

    return params.join('&');
}




(()=>{
    const origin_log = console.log;;
    console_log = function(){
        // return origin_log(...arguments)
    }
})();;;


!(function () {
    watch = function (obj, name) {
        return new Proxy(obj, {
            get(target, p, receiver) {
                // 过滤没用的信息，不进行打印
                if (name)
                    if (p === "Math" || p === "Symbol" || p === "Proxy" || p === "Promise" || p === "Array" || p === "isNaN" || p === "encodeURI" || p === "Uint8Array" || p.toString().indexOf("Symbol(") != -1) {
                        var val = Reflect.get(...arguments);
                        return val
                    }

                    else {
                        var val = Reflect.get(...arguments);

                        if (typeof val === 'function') {
                            console_log(`取值:`, name, '.', p, ` =>`, 'function');
                        }
                        else {
                            console_log(`取值:`, name, '.', p, ` =>`, val);
                        }

                        return val
                    }
            },
            set(target, p, value, receiver) {
                var val = Reflect.set(...arguments)
                if (typeof value === 'function') {
                    console_log(`设置值:${name}.${p}=>function `,);
                }
                else {
                    console_log(`设置值:${name}.${p}=> `, value);
                    if (name === '环境数组' && p === '4') {
                        debugger
                    }
                }
                return val
            },
            has(target, key) {
                console_log(`检查属性存在性: ${name}.${key.toString()}`);
                return key in target;
            },
            ownKeys(target) {
                console_log(`ownKeys检测: ${name}`);
                return Reflect.ownKeys(...arguments)
            }
        })
    }
})()
function makeFunction(name) {
    // 动态创建一个函数
    var func = new Function(`
        return function ${name}() {
            console_log('函数传参.${name}',arguments)
        }
    `)();
    safeFunction(func)
    func.prototype = watch(func.prototype, `方法原型:${name}.prototype`)
    func = watch(func, `方法本身:${name}`)
    return func;
};

(() => {
    Function.prototype.$call = Function.prototype.call
    const $toString = Function.toString;
    const myFunction_toString_symbol = Symbol('('.concat('', ')_'));
    const myToString = function toString() {
        return typeof this == 'function' && this[myFunction_toString_symbol] || $toString.$call(this);
    };

    function set_native(func, key, value) {
        Object.defineProperty(func, key, {
            "enumerable": false,
            "configurable": true,
            "writable": true,
            "value": value
        })
    }

    delete Function.prototype['toString'];

    set_native(Function.prototype, "toString", myToString);

    set_native(Function.prototype.toString, myFunction_toString_symbol, "function toString() { [native code] }");

    safeFunction = (func) => {
        set_native(func, myFunction_toString_symbol, `function ${func.name}() { [native code] }`);
    };
})();;;

Window = makeFunction('Window')
window = globalThis;
window.btoa_ = window.btoa;
window.btoa = function(str){
    var value = btoa_(str)
    if(value!==''){
        console.log(value)
        process.exit(1)
    }
    return value

}
window.Option=  makeFunction('Option')
window.Attr = makeFunction('Attr')
window.close = makeFunction('close')
window.alert = makeFunction('alert')
window.Text = makeFunction('Text')
window.Audio = makeFunction('Audio')
window.scroll = makeFunction('scroll')
window.Worker = makeFunction('Worker')
window.addEventListener = makeFunction('addEventListener')
window.resizeTo = makeFunction('resizeTo')
window.confirm = makeFunction('confirm')
window.print = makeFunction('print')
window.scrollBy = makeFunction('scrollBy')
window.blur = makeFunction('blur')
window.focus = makeFunction('focus')
window.open = makeFunction('open')
window.Element = makeFunction('Element')
window.File = makeFunction('File')
window.moveTo = makeFunction('moveTo')
window.Node = makeFunction('Node')
window.resizeBy = makeFunction('resizeBy')
window.Image = makeFunction('Image')
window.Blob = makeFunction('Blob')
window.CSSRule = makeFunction('CSSRule')
window.scrollTo = makeFunction('scrollTo')
window.Storage = makeFunction('Storage')
window.prompt  = makeFunction('prompt')
window.moveBy = makeFunction('moveBy')
window.Range = makeFunction('Range')
window.matchMedia = makeFunction('matchMedia')
window.XMLHttpRequest = makeFunction('XMLHttpRequest')
window.XMLHttpRequest.prototype.open = makeFunction('open')
window.XMLHttpRequest.prototype.send = function(data){
    console.log(data)
    process.exit(1)
    debugger
}
window.XMLHttpRequest.prototype . setRequestHeader  = makeFunction('setRequestHeader')
contentWindow = watch({
    document:watch({
        readyState:'complete',
        body:watch({
            style:watch({},'cw.body.style'),
            appendChild:function(obj){return obj}
        },'cw.body'),
        createElement:function(name){
            if(name==='div'){
                return watch({
                    style:watch({
                        setProperty:function(key,value){
                            this[key] = value
                        }
                    },'div.style'),
                    appendChild:function(obj){return obj}
                },'div')
            }
            if(name==='span'){
                return {
                    style:{}
                }
            }
            debugger
        }
    },'cw_document'),

},'contentWindow')

document1 = {
    addEventListener:makeFunction('addEventListener'),
    getElementsByTagName:function(name){
        if(name==='head'){
            return this.head
        }
        if(name==='script'){
            return watch({},'script')
        }
        debugger
    },
    head:watch({},'head'),
    body:watch({
        appendChild:function(obj){return obj}
    },'body'),
    createElement:function(name){
        if(name==='iframe'){
            return watch({
                parentNode:watch({
                },'iframe.parentNode'),
                style:watch({
                    setProperty:function(key,value){
                        this[key] = value
                    }
                },'iframe.style'),
                contentWindow:contentWindow
            },'iframe')
        }
        if(name==='span'){
            return watch({},'span')
        }
        if(name==='canvas'){
            return watch({},'canvas')
        }
        if(name==='script'){
            return watch({},'script')
        }
        if(name==='div'){
            return watch({},'div')
        }

        // debugger
    }
}
Object.defineProperty(window,'document',{
    get:function(){return document1}
})
Screen = makeFunction('Screen')
Document = makeFunction('Document')
History = makeFunction('History')
Location = makeFunction('Location')
location = {}
navigator1 = {}
screen1 = {}
Object.defineProperty(window,'screen',{
    get:function(){return screen1}
})
Object.defineProperty(window,'navigator',{
    get:function(){return navigator1}
})

history = {}
window = watch(window,'window')
window.self = window
document1 = watch(document1,'document1')
navigator = watch(navigator,'navigator')
screen = watch(screen,'screen')
history = watch(history,'history')

require('./AliyunCaptcha');


#jscode#



;;config__ = '#config#'

config_ = window.mr(config__)


__guyue = {
    "preCollectData": {
        "fontsNum": 104
    },
    "ENDPOINTS": [
        "https://cloudauth-device-dualstack.cn-shanghai.aliyuncs.com",
        "https://cn-shanghai.device.saf.aliyuncs.com"
    ],
    "sceneId": "q0hcfsca",
    "appName": "saf-captcha",
    "appKey": "ab034ec0643f91399eb33e062dc7fae1",
    "endpoints": [
        "https://cloudauth-device-dualstack.cn-shanghai.aliyuncs.com",
        "https://cn-shanghai.device.saf.aliyuncs.com"
    ],
    "DeviceConfig": config__,
    "deviceConfig": config_,
    "timestamp": "1765255309339",
    "feilinLoad": true
}

___guyue = makeFunction('guyue')

window.FEILIN.initFeiLin(__guyue, ___guyue)




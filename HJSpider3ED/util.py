from datetime import datetime, timedelta
import hashlib
import re
import time
import requests
import json
import logging

class Utils(object):

    logger = None

    # 文章相关host
    listenHost = 'http://ting.hujiang.com'
    # 用户相关host
    userHost = 'http://bulo.hujiang.com'
    # requests所需headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, sdch",
        "Accept-Language": "zh-CN,zh;q=0.8"
    }
    # json请求所需headers
    jsonHeaders = {
        "Host": "ting.hujiang.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
        "Content-Type": "application/json; charset=UTF-8",
        "Content - Length": "83"
    }

    # 获取md5加密后的值
    @staticmethod
    def md5_encode(string):
        m = hashlib.md5()
        m.update(string.encode())
        md5value=m.hexdigest()
        return md5value

    # 根据queryParams对象，创建url
    @staticmethod
    def urlCreate(host, queryParams):
        paramTemp = ''
        for key,value in queryParams.items():
            paramTemp += ('&' + str(key) + '=' + str(value))

        host += paramTemp[1:]
        return host

    # 将['x年前', 'x个月前', 'x天前', 'x小时前', 'x分钟前']转为datetime类型
    @staticmethod
    def chinese2datetime(string):
        if string == '':
            return datetime.strptime('1970/1/1 0:0:0', '%Y/%m/%d %H:%M:%S')

        timeValue = int(re.compile(r'(\d+)').search(string).group(1))
        timeObj = None

        for type in ['年', '月', '周','天', '小时', '分钟', '秒']:
            if string.find(type) != -1:
                current = datetime.now()

                if type is '年':
                    timeObj = current - timedelta(days=(timeValue * 365))
                elif type is '月':
                    timeObj = current - timedelta(days=(timeValue * 30))
                elif type is '周':
                    timeObj = current - timedelta(days=(timeValue * 7))
                elif type is '天':
                    timeObj = current - timedelta(days=timeValue)
                elif type is '小时':
                    timeObj = current - timedelta(hours=timeValue)
                elif type is '分钟':
                    timeObj = current - timedelta(minutes=timeValue)
                else:
                    timeObj = current - timedelta(seconds=timeValue)
        return timeObj

    # 用户登陆
    @staticmethod
    def userLogin(userName, userPass):

        # loginPageUrl = 'https://login.hujiang.com/'
        # loginPageHtml = requests.get(loginPageUrl, headers=headers)
        # print(loginPageHtml.text)
        # 需要构造的登陆url为：http://pass.hujiang.com/Handler/UCenter?action=Login&callback=jQuery18306339409919551378_1474079914039&userName=15161195812&password=a4c99a0683b75305dc36fae71047481d&imgcode=&token=2bc667751bcb5ee8a6909e533889c31f&_=1474080015221
        # # --------------------------------------------------------
        queryParams = {}
        queryParams['action'] = 'Login'
        queryParams['imgcode'] = ''

        # 获取token
        # url：https://captcha.yeshj.com/api.php?callback=jQuery183047967693999433547_1474094164557&w=100&h=30&t=1474094164741&_=1474094164744
        # 先得到13位时间戳
        timeStamp = ''.join(str(time.time()).split('.'))[:13]
        token_url = 'https://captcha.yeshj.com/api.php?callback=jQuery183047967693999433547_' + timeStamp + '&w=100&h=30&t=' + timeStamp + '&_=' + timeStamp
        try:
            tokenContent = requests.get(token_url)
        except Exception:
            raise Exception

        # print(tokenContent.text)
        # tokenContent = 'var HJCaptcha = { "token":"755374e9abe9893b034511e7aadff922","img":"//captcha.yeshj.com/captcha_v2.php?token=755374e9abe9893b034511e7aadff922&w=100&h=30"};jQuery183047967693999433547_1474094754998({ "token":"755374e9abe9893b034511e7aadff922","img":"//captcha.yeshj.com/captcha_v2.php?token=755374e9abe9893b034511e7aadff922&w=100&h=30"});'
        tokenJson = (tokenContent.text)[16:].split(';')[0]
        queryParams['token'] = json.loads(tokenJson)['token']

        # 用户名和密码，密码需要md5处理
        queryParams['userName'] = userName
        queryParams['password'] = Utils.md5_encode(userPass)

        # 构造模仿jquery jsonp的callback
        timeStamp = ''.join(str(time.time()).split('.'))[:13]
        queryParams['callback'] = 'jQuery183047967693999433547_' + timeStamp
        queryParams['_'] = timeStamp

        loginUrl = 'http://pass.hujiang.com/Handler/UCenter?'

        loginUrl = Utils.urlCreate(loginUrl, queryParams)

        try:
            session = requests.session()
            loginRespond = session.get(loginUrl, headers=Utils.headers)
        except Exception:
            raise Exception

        # loginRespond = 'jQuery183047967693999433547_1474096807628({"Code":0,"Message":"Ok","Data":{"ticket":"9fd38eff61fdf0c1c957abac7deac419","UserTag":{"GroupId":5000,"CategoryId":5001},"UserId":23868324,"UserName":"我了个去去啊","Cookie":"","Data":{"IsValidate":true},"BindMobileRequired":false,"Mobile":"151****5812"},"Success":false})'
        loginResJsonStr = loginRespond.text.split('(', maxsplit=1)[1][:-1]
        loginResJson = json.loads(loginResJsonStr)
        loginTicket = loginResJson['Data']['ticket']

        # 登陆同步处理 获取真正的cookie
        # url：/quick/synclogin.aspx?callback=jQuery18306339409919551378_1474079914039&token=79ce7d2ec9ff916c33e3286f93f2fa09&remeberdays=14&_=1474080015897
        syncParams = {}
        timeStamp = ''.join(str(time.time()).split('.'))[:13]
        syncParams['callback'] = 'jQuery183047967693999433547_' + timeStamp
        syncParams['_'] = timeStamp
        syncParams['remeberdays'] = '14'
        syncParams['token'] = loginTicket

        syncUrl = 'http://pass.hujiang.com/quick/synclogin.aspx?'
        syncUrl = Utils.urlCreate(syncUrl, syncParams)

        try:
            session.get(syncUrl, headers=Utils.headers)
        except Exception:
            raise Exception

        Utils.logger.info('登陆成功...')
        return session

    # 获取页数(几处有几页)
    @staticmethod
    def getPageCount(soup):
        pagesContent = soup.find(class_='pages').find_all('a')

        try:
            pageCount = 1 if len(pagesContent) == 0 else int(re.compile(r'必须在1~(.*?)之间', re.S).search(pagesContent[-1]['onclick']).group(1))
        except Exception:
            pageCount = 1

        return pageCount

    # 获取logger对象
    # 只支持 rootname
    @staticmethod
    def loggerInit(loggerName):
        # 获取一个hjspider的logger（每个模块的logger都可以有一个名字，如果不指定则为root）
        logger = logging.getLogger(loggerName)

        # 日志配置
        # 一般在简单的小脚本中才会用logging.basicConfig，因为稍大些每个模块的logger就需要分开
        # basicConfig配置后，会默认添加一个StreamHandler的，且获取的名为root的logger
        # 可参考 http://www.jb51.net/article/52022.htm
        # 输出到控制台的handler
        CHnadler = logging.StreamHandler()
        # 消息级别为WARNING及以上（级别分别是： NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL）
        CHnadler.setLevel(logging.INFO)
        # 输出到文件的handler
        FHandler = logging.FileHandler(filename='hjspider.log',
                                       mode='w',
                                       encoding='UTF-8')
        # 消息级别为DEBUG
        FHandler.setLevel(logging.DEBUG)
        # 设置格式
        formatter = logging.Formatter('%(thread)d %(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s:  %(message)s')
        # 设置格式
        CHnadler.setFormatter(formatter)
        FHandler.setFormatter(formatter)

        # 将handler附加在这个logger上（handler可以理解为消息先传到logger，然后在传给每个handler处理）
        logger.addHandler(CHnadler)
        logger.addHandler(FHandler)
        # 既然消息是传到handler的，那么如果这个logger的level就和handler的level息息相关
        # 比如logger的level为info（默认）, 那么即使handler的level设置为debug，也不可能得到debug的消息
        # 每个handler的level在logger指定的level的基础上继续进行筛选
        logger.setLevel(logging.DEBUG)

        return logger

Utils.logger = Utils.loggerInit('hjspider')
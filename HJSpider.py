# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from HJ_Info import UserInfo, ListenItemInfo, ListenArticleInfo
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from urllib.parse import urlparse, unquote
from queue import Queue
import requests
import time
import json
import util
import re
import logging
import logging.config
import configparser

# 两个问题
# 1. 数据集合是否要限制大小？(listenArticles, usersAll, listenItemsDict)
# 2. 302页面如和再处理？
#
class Spider(object):
    # 初始化
    def __init__(self, userCode):
        self.config = configparser.ConfigParser()
        self.config_privacy = configparser.ConfigParser()
        # 用户名密码配置文件username,password两个属性
        self.config_privacy.read('ConfigUser.conf', encoding='utf-8')
        self.config.read('ConfigHJ.conf', encoding='utf-8')

        #数据库配置
        self.mysql_user = self.config.get('MYSQL', 'user')
        self.mysql_password = self.config.get('MYSQL', 'password')
        self.mysql_host = self.config.get('MYSQL', 'host')
        self.mysql_port = self.config.get('MYSQL', 'port')
        self.mysql_db_name = self.config.get('MYSQL', 'db_name')
        self.mysql_max_overflow = int(self.config.get('MYSQL', 'max_overflow'))

        # echo为True表示每次执行操作会显示sql语句，可在生产环境关闭
        self.engin = create_engine('mysql+pymysql://' + self.mysql_user + ':' + self.mysql_password +
                                   '@' + self.mysql_host + ':' + self.mysql_port + '/' +
                                   self.mysql_db_name + '?charset=utf8', max_overflow=self.mysql_max_overflow,
                                   echo=False)
        self.mysql_session = (sessionmaker(bind=self.engin))()

        # 网站登陆所需配置
        self.start_url = self.config.get('SPIDER', 'startUrl')
        self.user_name = self.config_privacy.get(userCode, 'username')
        self.user_pass = self.config_privacy.get(userCode, 'password')

        # 工具类
        self.tools = util.Utils()

        # 日志初始化
        self.loggerInit()

        # 一个带登陆信息的session，用于获取更丰富的个人信息页面
        self.session = None

        # 以下数据集合会不会过大呢？ 是否要限制大小? 因为在存储进数据库之前也会查询是否在数据库中已存在.
        # 访问的页（没有必要限制）
        self.listenPages = []
        # 访问的节目（没有必要限制）
        self.listenItems = set()
        # 访问的文章（有必要限制）
        self.listenArticles = set()
        # 访问的用户（有必要限制）
        self.usersAll = dict()

        # 用户个数, 虽然len(self.userAll)可以得到结果，但因为302重定向（用户设置隐私）导致太慢，索性也将302的用户假如userall
        # 这样就需要另外的计数器保存用户数量
        # 虽然302避免不了，但重复的302必须隔绝
        self.userCurrentCount = 0

        # 节目与其对应的文章, key为节目url， value为数组[节目信息:object， 节目中的文章:array]
        # 即 {节目url : [节目信息， [节目文章1， 节目文章2， ... ]]}
        # 主要是为了初始化函数中的一个选项： 限制每个节目访问文章的数量
        # （有必要限制大小,目前来看，一个节目访问完毕后数据就没用了）
        self.listenItemsDict = dict()

        # 文章相关host
        self.listenHost = 'http://ting.hujiang.com'
        # 用户相关host
        self.userHost = 'http://bulo.hujiang.com'

        # 获取用户信息间隔
        # 在网站返回"访问太频繁"的消息后，时间间隔乘2
        self.tooFrequent = int(self.config.get('SPIDER', 'tooFrequent'))
        self.timeIntervalBase = float(self.config.get('SPIDER', 'timeIntervalBase'))
        # 等待时间缓慢增长，但是快速减少，但是要保证tooFrequent至少为0
        self.frequentAdd = int(self.config.get('SPIDER', 'frequentAdd'))
        self.frequentReduce = int(self.config.get('SPIDER', 'frequentReduce'))
        # 返回太频繁消息的用户，之后需要再次访问
        self.needReGain = []

        # 是否已经超出限制
        self.isOverLimited = False

        try:
            # 统计几个节目, 0表示无限制(因为我通过判断是否==限制数量来进行超出判断，所以0可以拿来当作无限大)
            self.listenItems_Max = int(self.config.get('SPIDER', 'listenItemsMax'))
            # 每个节目选取几篇文章， 0表示无限制
            self.listenArticlesEachItem_Max = int(self.config.get('SPIDER', 'listenArticlesEachItem'))
            # 统计的人数限制
            self.userLimit_Max = int(self.config.get('SPIDER', 'userLimit'))
            # 已听文章数量限制
            self.listenArticlesMax = int(self.config.get('SPIDER', 'listenArticlesMax'))
        except Exception as e:
            self.logger.error('各种限制请使用整型或是整型字符串！')
            exit(-1)

    # 日志初始化
    def loggerInit(self):
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
        formatter = logging.Formatter('%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s:  %(message)s')
        # 设置格式
        CHnadler.setFormatter(formatter)
        FHandler.setFormatter(formatter)

        # 获取一个hjspider的logger（每个模块的logger都可以有一个名字，如果不指定则为root）
        self.logger = logging.getLogger('hjspider')
        # 将handler附加在这个logger上（handler可以理解为消息先传到logger，然后在传给每个handler处理）
        self.logger.addHandler(CHnadler)
        self.logger.addHandler(FHandler)
        # 既然消息是传到handler的，那么如果这个logger的level就和handler的level息息相关
        # 比如logger的level为info（默认）, 那么即使handler的level设置为debug，也不可能得到debug的消息
        # 每个handler的level在logger指定的level的基础上继续进行筛选
        self.logger.setLevel(logging.DEBUG)

    # 用户登陆
    def userLogin(self):
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
        except Exception as e:
            self.logger.fatal('获取登陆所需token失败！')
            exit(-1)

        # print(tokenContent.text)
        # tokenContent = 'var HJCaptcha = { "token":"755374e9abe9893b034511e7aadff922","img":"//captcha.yeshj.com/captcha_v2.php?token=755374e9abe9893b034511e7aadff922&w=100&h=30"};jQuery183047967693999433547_1474094754998({ "token":"755374e9abe9893b034511e7aadff922","img":"//captcha.yeshj.com/captcha_v2.php?token=755374e9abe9893b034511e7aadff922&w=100&h=30"});'
        tokenJson = (tokenContent.text)[16:].split(';')[0]
        queryParams['token'] = json.loads(tokenJson)['token']
        self.logger.info('Login Token IS ' + queryParams['token'])

        # 用户名和密码，密码需要md5处理
        queryParams['userName'] = self.user_name
        queryParams['password'] = self.tools.md5_encode(self.user_pass)

        # 构造模仿jquery jsonp的callback
        timeStamp = ''.join(str(time.time()).split('.'))[:13]
        queryParams['callback'] = 'jQuery183047967693999433547_' + timeStamp
        queryParams['_'] = timeStamp

        loginUrl = 'http://pass.hujiang.com/Handler/UCenter?'

        loginUrl = self.tools.urlCreate(loginUrl, queryParams)

        headers = {
            'Host': 'pass.hujiang.com',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, sdch, br',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36'
        }

        try:
            session = requests.session()
        except Exception as e:
            self.logger.fatal('用户登陆失败')
            exit(-1)

        loginRespond = session.get(loginUrl, headers=headers)

        # loginRespond = 'jQuery183047967693999433547_1474096807628({"Code":0,"Message":"Ok","Data":{"ticket":"9fd38eff61fdf0c1c957abac7deac419","UserTag":{"GroupId":5000,"CategoryId":5001},"UserId":23868324,"UserName":"我了个去去啊","Cookie":"","Data":{"IsValidate":true},"BindMobileRequired":false,"Mobile":"151****5812"},"Success":false})'
        loginResJsonStr = loginRespond.text.split('(')[1][:-1]
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
        syncUrl = self.tools.urlCreate(syncUrl, syncParams)

        try:
            session.get(syncUrl, headers=headers)
        except Exception as e:
            self.logger.fatal('获取cookie失败')
            exit(-1)

        self.session = session

    # 获取页数(几处有几页)
    def getPageCount(self, soup):
        pagesContent = soup.find(class_='pages').find_all('a')

        if len(pagesContent) == 0:
            pageCount = 1
        else:
            try:
                pageCount = re.compile(r'必须在1~(.*?)之间', re.S).search(pagesContent[-1]['onclick']).group(1)
            except Exception:
                self.logger.error('获取页码失败，默认最大为1')
                pageCount = 1

        return int(pageCount)

    # 获取有节目的所有页面
    def getPagesHasItems(self):

        headers = {
            "Host": "ting.hujiang.com",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "http://ting.hujiang.com/menu/en",
            "Accept-Encoding": "gzip, deflate, sdch",
            "Accept-Language": "zh-CN,zh;q=0.8"
        }

        try:
            mainPage = requests.get('http://ting.hujiang.com/menu/en/', headers=headers)
            soup = BeautifulSoup(mainPage.text, "lxml")
            # 找几页
            maxPageNum = self.getPageCount(soup)
        except Exception as e:
            self.logger.error('获取最大页数失败，默认只访问第一页！')
            maxPageNum = 1

        self.logger.info('此次访问共有' + str(maxPageNum) + '页')

        # 开始对每一页的节目收集
        for i in range(int(maxPageNum)):
            listenItemsPageUrl = self.listenHost + '/menu/en/page' + str(i + 1) + '/'
            self.listenPages.append(listenItemsPageUrl)

            self.logger.info('当前访问页面：' + listenItemsPageUrl)
            self.getListenItems(listenItemsPageUrl)

            if self.isOverLimited:
                break


    # 获取听写节目
    def getListenItems(self, url):
        headers = {
            "Host": "ting.hujiang.com",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "http://ting.hujiang.com/menu/en",
            "Accept-Encoding": "gzip, deflate, sdch",
            "Accept-Language": "zh-CN,zh;q=0.8"
        }

        try:
            itemsContent = requests.get(url, headers=headers)
        except Exception as e:
            self.logger.error('某页节目获取失败：' + url)
            return

        try:
            soup = BeautifulSoup(itemsContent.text, "lxml")
        except:
            self.logger.error('某页解析失败: ' + url)
            return

        itemsList = soup.find_all(class_="menu_img fl")
        for li in itemsList:
            full_url = self.listenHost + li["href"]
            if full_url in self.listenItems:
                continue

            self.listenItems.add(full_url)
            self.listenItemsDict[full_url] = []

            self.logger.info('当前访问节目：' + full_url)
            self.getListenArticles(full_url)

            if self.isOverLimited:
                break

            if len(self.listenItems) == self.listenItems_Max:
                self.isOverLimited = True
                self.logger.info('节目访问数量超出限制，退出！')
                break


    # 通过节目获取文章ID
    def getListenArticles(self, url):
        headers = {
            "Host": "ting.hujiang.com",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "http://ting.hujiang.com/menu/en",
            "Accept-Encoding": "gzip, deflate, sdch",
            "Accept-Language": "zh-CN,zh;q=0.8"
        }

        try:
            articlesContent = requests.get(url, headers=headers)
        except Exception as e:
            self.logger.error('获取某节目首页失败: ' + url)
            return

        try:
            soup = BeautifulSoup(articlesContent.text, "lxml")
        except Exception:
            self.logger.error('解析某节目首页失败: ' + url)
            return

        pageCount = self.getPageCount(soup)
        self.logger.info('文章最大页数为：' + str(pageCount) + '; url is ' + url)

        self.listenItemsDict[url].append(self.getListenItemInfo(soup, url))
        self.listenItemsDict[url].append([])

        self.logger.debug(self.listenItemsDict[url][0])

        # 用于限制每个节目的文章访问数量的， 某节目文章超出限制后不能用overlimit这个全局停止变量
        # 只有所有节目已访问文章数量超出限制才会使用overlimit
        thisItemArticleCountOver = False
        # 获取某页节目的所有文章的url, 传递给getListenArticleInfo函数
        for pageIndex in range(1, int(pageCount) + 1):
            pageUrl = url + 'page' + str(pageIndex)
            try:
                articlesContent = requests.get(pageUrl, headers=headers)
            except Exception:
                self.logger.error('获取第' + str(pageIndex) + '页文章失败: ' + pageUrl)
                continue

            try:
                soup = BeautifulSoup(articlesContent.text, "lxml")
            except Exception:
                self.logger.error('解析第' + str(pageIndex) + '页面失败: ' + pageUrl )
                continue

            # 遍历该页所有文章
            articlesList = soup.find_all(class_='article_list_item')
            for article in articlesList:
                full_url = self.listenHost + article.find(class_='big search_titles')["href"]
                if full_url in self.listenArticles:
                    continue

                articleInfo = self.getListenArticleInfo(article, full_url, url)
                self.logger.debug(articleInfo)

                self.listenArticles.add(full_url)
                self.listenItemsDict[url][1].append(articleInfo)

                # 获取文章时，会获取文章作者资料，所以可能导致用户数量超出
                if self.userCurrentCount == self.userLimit_Max:
                    self.isOverLimited = True
                    self.logger.info('用户数量达到限制，退出！')
                    break

                self.logger.info('当前访问文章：' + full_url)
                self.getUsersId(full_url)

                # 用户超出限制
                if self.isOverLimited:
                    break

                # 文章总数超出限制
                if len(self.listenArticles) == self.listenArticlesMax:
                    self.isOverLimited = True
                    self.logger.info('文章数量超出限制，退出！')
                    break

                # 每个节目文章数量超出限制
                if len(self.listenItemsDict[url][1]) == self.listenArticlesEachItem_Max:
                    thisItemArticleCountOver = True
                    self.logger.info('此节目已访问文章数量超出限制，不再继续访问此节目文章！')
                    break

            # 用户或文章过多
            if self.isOverLimited:
                break

            # 该换节目了
            if thisItemArticleCountOver:
                break

    # 通过ajax尽可能获取用户Uid
    def getUsersId(self, articleUrl):
        #根据传入的url获取ajax所需的参数
        commentId = articleUrl.split('/')[-2][2:8]

        form = {}
        postUrl = 'http://ting.hujiang.com/ajax.do'

        headers = {
            "Host": "ting.hujiang.com",
            "Content-Length": "83",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
            "Content-Type": "application/json; charset=UTF-8"
        }

        form = {}
        form['classMethod'] = 'AjaxComs.GetListenedUserList'
        form['param'] = [1, int(commentId), 0]
        form['pageName'] = None

        try:
            # 需要先走一个，看看总共多少个听众，可以分多少页，即多少次请求(每次7个人)
            content = requests.post(postUrl, data=json.dumps(form), headers=headers)
        except Exception:
            self.logger.error('第一次获取某文章听众失败: ' + articleUrl)
            return

        try:
            contentText = content.text
            contentJson = json.loads(contentText)
        except Exception:
            self.logger.error('第一次json 解析文章听众失败: ' + articleUrl)
            return

        try:
            listenUserCount = int(contentJson['d'][1])
        except:
            self.logger.error('第一次获取的ajax数据错误，该页用户未被获取: ' + articleUrl)
            listenUserCount = 0

        totalPages = int(listenUserCount / 7)
        if listenUserCount % 7 != 0:
            totalPages += 1

        self.logger.info('该文章听众数量：' + str(listenUserCount) + '; 页数: ' + str(totalPages))
        for i in range(1,totalPages+1):
            self.logger.info('第 ' + str(i) + ' 页用户, 当前 ' + str(self.userCurrentCount) + ' 用户(不包括302)')
            form['param'][0] = i

            try:
                content = requests.post(postUrl, data=json.dumps(form), headers=headers)
            except Exception:
                self.logger.error('获取文章id的2-8位为' + str(form['param'][1]) + ' 第' + str(i) + '页失败！')
                continue

            try:
                contentText = content.text
                contentJson = json.loads(contentText)
            except Exception:
                self.logger.error('JSON解析文章id的2-8位为' + str(form['param'][1]) + ' 第' + str(i) + '页失败！')
                continue

            try:
                userInfoContainer = BeautifulSoup(contentJson['d'][2], "lxml")
            except Exception:
                self.logger.error('BeautifulSoup解析文章id的2-8位为' + str(form['param'][1]) + ' 第' + str(i) + '页失败！')
                continue

            userList = userInfoContainer.find_all(class_='userListItemIcon')
            if not userList:
                continue

            for user in userList:
                uid = user.find('a')['userid']
                if uid in self.usersAll:
                    continue

                getUserInfoStart = time.time()

                time2sleep = self.timeIntervalBase * 2 ** self.tooFrequent
                if time2sleep >= 2.0:
                    self.logger.warning('程序将沉睡'+str(time2sleep) + '秒以避免访问过于频繁')
                # 太快容易引发大量虚假302
                # time.sleep(time2sleep)
                # 更换代理地址

                self.getUserInfo(uid)
                getUserInfoEnd = time.time()

                self.logger.info('访问此用户消耗时间（秒）：' + str(getUserInfoEnd - getUserInfoStart))

                if self.userCurrentCount == self.userLimit_Max:
                    self.isOverLimited = True
                    self.logger.info('用户数量达到限制，退出！')
                    break

            if self.isOverLimited:
                break

    # 爬取用户信息
    # 获取 获取用户信息的 页面，如果没有登陆，有些信息不能完全显示，所以以后会携带cookie访问
    # 返回值： True，程序继续； False：程序停止；
    def getUserInfo(self, uid):

        user = UserInfo(uid)

        headers = {
            "Host": "bulo.hujiang.com",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, sdch",
            "Accept-Language": "zh-CN,zh;q=0.8"
        }

        full_url = self.userHost + '/u/' + uid + '/'
        try:
            content = self.session.get(full_url, headers=headers, allow_redirects=False)
        except Exception:
            self.logger.error('获取用户页面失败: ' + full_url)
            return

        # 有的人将部落设置为隐私，外部不能访问，页面会302转向error
        if content.status_code != 200:
            self.logger.warning(full_url + ': redirect ' + str(content.status_code))
            responseText = urlparse(unquote(content.headers['Location'])).query.split('=', maxsplit=1)[1]
            self.logger.warning('提示: ' + responseText)

           # 若为过于频繁
            if responseText[0:2] == '您的':
                # 不能存进userAll, 而是放进needReGain数组中等待重新访问的机会
                self.needReGain.append(uid)
                # 如果第一次遇到这种情况，最好睡眠时间快速增长，之后缓慢增长
                if self.tooFrequent == 0:
                    self.tooFrequent = 4
                else:
                    self.tooFrequent += self.frequentAdd

            else:
                # 若为私有，则存储进userAll
                self.usersAll[uid] = None
                if self.tooFrequent > 0:
                    self.tooFrequent -= self.frequentReduce
                self.tooFrequent = 0 if self.tooFrequent < 0 else self.tooFrequent

            return

        # 如果此时的返回不是过于频繁，那么等待时间即可缩小一倍
        if self.tooFrequent > 0:
            self.tooFrequent -= self.frequentReduce
        self.tooFrequent = 0 if self.tooFrequent < 0 else self.tooFrequent

        # 已添加进数据库的数据量
        self.userCurrentCount += 1

        try:
            soup = BeautifulSoup(content.text, "lxml")
        except Exception:
            self.logger.error('解析用户页面失败: ' + full_url)
            return

        # with open('file_0.txt', 'r', encoding='utf-8') as f:
        #     content = f.read()
        #
        # soup = BeautifulSoup(content, "lxml")

        # 统计
        countList = soup.find(attrs={'id':'LeftCnt_divUserCount'})

        # 处理一些数据
        if countList:
            # 访客数
            viewCount = countList.find(attrs={'id':'li_viewCount'})
            if viewCount and len(viewCount) != 0:
                user.viewCount = viewCount.string

            # 留言数
            msgCount = countList.find(attrs={'id':'li_msgCount'})
            if msgCount and len(msgCount) != 0:
                user.msgCount = msgCount.find('a').string

            # 碎碎数
            ingCount = countList.find(attrs={'id':'li_ingCount'})
            if ingCount and len(ingCount) != 0:
                user.ingCount = ingCount.find('a').string

            # 日志数
            blogCount = countList.find(attrs={'id':'li_blogCount'})
            if blogCount and len(blogCount) != 0:
                user.blogCount = blogCount.find('a').string

            # 听写数
            listenCount = countList.find(attrs={'id':'li_listenCount'})
            if listenCount and len(listenCount) != 0:
                user.listenCount = listenCount.find('a').string

            # 口语数
            talkCount = countList.find(attrs={'id':'li_talkCount'})
            if talkCount and len(talkCount) != 0:
                user.talkCount = talkCount.find('a').string

            # 礼物数
            giftCount = countList.find(attrs={'id':'li_giftCount'})
            if giftCount and len(giftCount) != 0:
                user.giftCount = giftCount.find('a').string

        # 个人信息
        profileList = soup.find(id='u_profile').find('ul')

        # 继续处理数据
        if profileList:
            for child in profileList.children:

                if child.name != 'li':
                    continue

                text = child.get_text(strip=True)
                if re.compile(r'性别').search(text):
                    user.gender = child.find_all('span')[1].string

                if re.compile(r'城市').search(text):
                    user.city = child.find_all('span')[1].string

                if re.compile(r'昵称').search(text):
                    child.span.replace_with('')
                    user.nickName = child.get_text(strip=True)

                if re.compile(r'签名').search(text):
                    child.span.replace_with('')
                    user.signature = child.get_text(strip=True)

                if re.compile(r'沪龄').search(text):
                    # user.yearLast = child.find_all('span')[1].string
                    user.registDate = child.find_all('span')[1]['title'][5:]

                if re.compile(r'打卡').search(text):
                    child.span.replace_with('')
                    user.signinLast = int(child.get_text(strip=True)[0:-1])

                if re.compile(r'登录').search(text):
                    user.lastSignin = child.find_all('span')[1].string

        # 自我介绍
        selfIntroPre = soup.find(id='user_Profile_span_reportIt')
        selfIntro = None

        if selfIntroPre:
            selfIntro = selfIntroPre.find_previous_sibling()

        if selfIntro and selfIntro.name == 'div':
            user.selfIntroduction = selfIntro.get_text(strip=True)

        # 城市，因为该部分是注释，所以用bs4找不出来就用re了
        cityMatch = re.compile(r'<li id="user_Profile_span_city.*?<span>(.*?)</span></li>', re.S).search(content.text)
        if cityMatch:
            user.city = cityMatch.group(1)

        # 获取名称
        userNameHtml = soup.find(id='cont_h1')
        userNameHtml.a.replace_with('')
        userNameHtml.span.replace_with('')
        user.name = userNameHtml.get_text(strip=True)[0:-5].strip()

        self.usersAll[uid] = user
        try:
            user.save(self.mysql_session)
        except Exception:
            self.logger.error('存储用户信息失败')

        self.logger.debug(user)

    # 不抓取信息，只收集ID
    def getUserInfo1(self, uid):

        if uid in self.usersAll:
            return

        user = UserInfo(uid)

        self.userCurrentCount += 1

        self.usersAll[uid] = user

    # 爬取节目信息
    def getListenItemInfo(self, soup, url):

        item = ListenItemInfo(url)

        detailContentSoup = soup.find(class_='topic')
        item.itemImgUrl = detailContentSoup.find(class_='menulogo')['src']
        item.title = detailContentSoup.find(class_='topic_name').find('a').get_text(strip=True)
        item.introduction = detailContentSoup.find(class_='p_summary').get_text(strip=True)

        detailMoreSoup = detailContentSoup.find(class_='topic_detail_right')
        detailList = detailMoreSoup.find_all('li')

        for attrLi in detailList:

            text = attrLi.get_text(strip=True)

            if re.compile(r'分　类').search(text):
                typeList = attrLi.find_all('a')
                for type in typeList:
                    item.type.append(type.get_text(strip=True))

            if re.compile(r'难　度').search(text):
                item.difficult = attrLi.find('a').get_text(strip=True)

            if re.compile(r'频　率').search(text):
                attrLi.span.replace_with('')
                item.updateRate = attrLi.get_text(strip=True)

            if re.compile(r'均用时').search(text):
                attrLi.span.replace_with('')
                item.averageComsume = attrLi.get_text(strip=True)

            if re.compile(r'均得分').search(text):
                attrLi.span.replace_with('')
                item.averageScore = attrLi.get_text(strip=True)

        try:
            item.save(self.mysql_session)
        except Exception:
            self.logger.error('存储节目信息失败')

        return item

    # 爬取文章信息
    def getListenArticleInfo(self, soup, url, oldurl):
        article = ListenArticleInfo(url.split('/')[-2])

        # 所属节目
        article.item = oldurl.split('/')[-2]

        # 类型和标题
        article.type = soup.find(class_='big redlink nobold')['title']
        article.title = soup.find(class_='search_titles').get_text(strip=True)

        # 筛选出听写人数以及平均正确率
        text = soup.find(class_='info').get_text(strip=True)
        article.commentCount = re.compile('(\d+)次评论').search(text).group(1)
        article.averageScore = re.compile('(\d+)%').search(text).group(1)

        # 获取更详细的内容
        headers = {
            "Host": "ting.hujiang.com",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "http://ting.hujiang.com/menu/en",
            "Accept-Encoding": "gzip, deflate, sdch",
            "Accept-Language": "zh-CN,zh;q=0.8"
        }
        content = requests.get(url, headers=headers)

        soup = BeautifulSoup(content.text, "lxml")
        detailInfoList = soup.find(id='listen_info_ul').find_all('li')

        for li in detailInfoList:
            text = li.get_text(strip=True)

            if re.compile(r'时长').search(text):
                li.span.replace_with('')
                article.timeLast = li.get_text(strip=True)

            elif re.compile(r'难度').search(text):
                article.difficultLevel = li.find(id='level_alert').get_text()

            elif re.compile(r'人数').search(text):
                article.listenCount = li.find_all('span')[1].get_text(strip=True)[0:-1]

            elif re.compile(r'标签').search(text):
                tags = li.find_all('a')
                for tag in tags:
                    article.tags.append(tag.get_text(strip=True))

            elif re.compile(r'发布').search(text):
                article.publishTime = li.find_all('span')[1]['title']

            elif re.compile(r'奖金').search(text):
                article.rewards = li.find_all('span')[1].get_text(strip=True)[0:-2]

            elif re.compile(r'贡献').search(text):
                article.contributorId = li.find('a')['href'].split('/')[1][1:]
                # ***为了数据的一致性(外键的存在)，这里需要提前获取contributor用户,否则无法存储article
                if article.contributorId not in self.usersAll:
                    self.getUserInfo(article.contributorId)

            # 登陆后才能下载
            #elif re.compile(r'下载').search(text):
            #    article.downloadUrl = self.listenHost + li.span.find_all('a')[0]['href']
        article.downloadUrl = self.listenHost + '/download/' + url.split('/')[-2][2:8] + '/'

        try:
            article.save(self.mysql_session)
        except Exception:
            self.logger.error('存储文章信息失败')

        return article

    # 重复爬取302（可能有的是虚假302）
    # 1. 在达到一定数量后
    # 2. 在所有文章遍历结束后
    # 3. 此函数另开线程（进程）处理
    def reAddress302(self):
        pass

    # 302 可能情况
    # 1. 私有不允许访问
    # 2. 访问太频繁
    def test302(self):
        self.getUserInfo('1469913')

    # run
    def run(self):
        self.logger.info('spider running ...')

        # 先登录获取session
        self.userLogin()

        # 测试区分302
        # self.test302()
        # return {}

        # 开始找
        self.getPagesHasItems()

        # 关闭数据库session
        self.mysql_session.close()

        # flush logger
        logging.shutdown()

        return self.usersAll



if __name__ == "__main__":
    timeStart = time.time()
    # 使用那个账号登陆（一个编号对应一个账号）
    spider = Spider(userCode='321')
    res = spider.run()
    timeEnd = time.time()
    timeDelta = timeEnd - timeStart
    print('耗时：' + str(timeDelta) + ' 秒')


    # body = requests.get('http://bulo.hujiang.com/u/54071261/', headers=headers, allow_redirects=False)



# 隐私用户也可以获取信息
# 在头像上放置一段时间就显示的那个
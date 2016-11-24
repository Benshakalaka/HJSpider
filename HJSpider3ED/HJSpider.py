# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from views.ListenUsers import ListenUsers
from views.ListenArticles import ListenArticles
from views.ListenItems import ListenItems
from models.models import Models
from sqlalchemy.ext.declarative import declarative_base
from util import Utils
import requests
import time
import logging
import logging.config
import configparser



class Spider(object):
    # 初始化
    def __init__(self, userCode='', isLogin=True, userQueue=None):
        self.config = configparser.ConfigParser()
        self.config_privacy = configparser.ConfigParser()
        # 用户名密码配置文件username,password两个属性
        self.config_privacy.read('config/ConfigUser.conf', encoding='utf-8')
        self.config.read('config/ConfigHJ.conf', encoding='utf-8')

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
        self.currentTotalPageCounts = 0
        self.currentPageIndex = 1

        # 是否需要登陆
        self.isLogin = isLogin

        # 多线程使用的userQueue，此线程用于存储另外几个线程趴下来的用户信息实例
        self.userQueue = userQueue
        # 已经存储进数据库的数量
        self.userSavedCount = 0

        # 日志初始化
        self.loggerInit()

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

        # 获取用户信息间隔
        # 在网站返回"访问太频繁"的消息后，时间间隔乘2
        self.timeIntervalBase = float(self.config.get('SPIDER', 'timeIntervalBase'))
        # 等待时间缓慢增长，但是快速减少，但是要保证tooFrequent至少为0
        self.frequentAdd = int(self.config.get('SPIDER', 'frequentAdd'))
        self.frequentReduce = int(self.config.get('SPIDER', 'frequentReduce'))
        # 用户页面失败访问最大次数
        self.failedToVisitCountLimit = int(self.config.get('SPIDER', 'failedToVisitCountLimit'))

        # 节目对象
        self.items = ListenItems(self.mysql_session, self.listenItems_Max)
        # 文章对象
        self.articles = ListenArticles(self.mysql_session, self.listenArticlesMax)
        # 用户对象
        if isLogin is True:
            self.user_name = self.config_privacy.get(userCode, 'username')
            self.user_pass = self.config_privacy.get(userCode, 'password')
            self.users = ListenUsers(
                self.mysql_session, self.userLimit_Max,
                self.user_name, self.user_pass,
                self.timeIntervalBase
            )
        else:
            self.users = ListenUsers(
                self.mysql_session, self.userLimit_Max,
                timeIntervalBase=self.timeIntervalBase,
                isLogin=False
            )

        self.isOverLimited = False

        # clear database
        model = Models(declarative_base(), self.engin)
        model.clearAllData()

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


    # 获取某语种的某页, index可设置起始页，下一次重复调用index将不再可用
    def getPagesHasItems(self, index=0):
        if self.currentPageIndex != 1 and self.currentPageIndex > self.currentTotalPageCounts:
            self.currentTotalPageCounts = 0
            self.currentPageIndex = 1
            return None

        if self.currentTotalPageCounts == 0:
            try:
                index = max(0, int(index))
            except Exception:
                self.logger.error('起始页为整数.')
                exit(-1)
            self.currentPageIndex = index if index is not 0 else self.currentPageIndex

        fullUrl = self.start_url + 'page' + str(self.currentPageIndex) + '/'
        try:
            mainPage = requests.get(fullUrl, headers=Utils.headers)
            soup = BeautifulSoup(mainPage.text, "lxml")
            self.currentPageIndex += 1
        except Exception:
            self.logger.error('节目页面获取失败!')
            return

        if self.currentTotalPageCounts == 0:
            try:
                # 找几页
                self.currentTotalPageCounts = Utils.getPageCount(soup)
            except Exception as e:
                self.logger.error('获取最大页数失败，默认只访问第一页！')
                self.currentTotalPageCounts = 1
            self.logger.info('此次访问共有' + str(self.currentTotalPageCounts) + '页')

        return fullUrl


    # 获取uid, main runner
    def getUserUids(self):
        # loop: 获取某语种的包含节目的页面
        while True:
            url = self.getPagesHasItems(16)
            if url is None:
                break
            self.logger.info('*' * 50 + '访问此语种页面：' + url)

            # loop: 存储节目信息， 获取某节目包含文章的页面soup对象
            self.items.appendFromUrl(url)
            while True:
                itemRet = self.items.getSomeArticlesPageSoup()
                if itemRet is None:
                    break
                itemUrl, itemSoup = itemRet
                self.logger.info('*' * 30 + '访问节目页面：' + itemUrl)

                # loop: 存储文章信息， 获取该文章的uid
                self.articles.appendFromUrl(itemUrl, itemSoup)
                articleEachItemCount = 0
                while True:
                    articleRet = self.articles.getOneArticlePageSoup()
                    if articleRet is None:
                        break

                    articleUid, contributorId = articleRet
                    self.logger.info('*' * 10 + '正在访问文章的UID是：%s  贡献者为：%s' % (articleUid, contributorId))

                    # loop: 存储用户信息， 获取该用户的uid
                    self.users.appendFromUid(articleUid)
                    self.users.appendUidPriority(contributorId)
                    while True:
                        userRet = self.users.getOneUserUid(self.frequentAdd, self.frequentReduce)
                        if userRet is None:
                            break
                        userUid, timeDelta = userRet
                        self.logger.info('获取的用户uid为：%s  消耗时间：%s' % (str(userUid), str(timeDelta)))

                        if self.users.userIsOverLimited() is True:
                            self.isOverLimited = True
                            break

                    if self.isOverLimited is True or self.articles.articleIsOverLimited() is True:
                        self.isOverLimited = True
                        break

                    articleEachItemCount += 1
                    if articleEachItemCount == self.listenArticlesEachItem_Max:
                        self.isOverLimited = True
                        break

                if self.isOverLimited is True or self.items.itemIsOverLimited() is True:
                    self.isOverLimited = True
                    break

            if self.isOverLimited is True:
                break

        while self.userSavedCount <= self.users.getUserSize():
            self.UserInfoSave()

        logging.shutdown()
        return None


    # 存储用户信息进入mysql
    def UserInfoSave(self):
        # 那么数据库存储用户的模式就要改变
        # 依旧在爬取： 非阻塞获取user信息，存储进数据库
        # 如果因为数量限制而停止爬取了： 阻塞直到所有信息都获取且存入数据库
        if self.isOverLimited is True:
            user = self.userQueue.get(block=True)
        else:
            try:
                user = self.userQueue.get_nowait()
            except:
                user = None

        if user is None:
            return

        self.mysql_session.add(user)
        self.mysql_session.commit()
        self.userSavedCount += 1



if __name__ == "__main__":
    timeStart = time.time()
    # 使用那个账号登陆（一个编号对应一个账号）
    # spider = Spider(userCode='322')
    spider = Spider(isLogin=False)
    res = spider.getUserUids()
    timeEnd = time.time()
    timeDelta = timeEnd - timeStart
    print('耗时：' + str(timeDelta) + ' 秒')
    print('共%s个节目； 共%s篇文章； \n共访问%s个用户, 其中成功获取%s个用户, 失败%s个用户' % (
            str(spider.items.getItemsSize()),
            str(spider.articles.getArticleSize()),
            str(spider.users.getAllUserSize()),
            str(spider.users.getUserSize()),
            str(spider.users.getAllUserSize() - spider.users.getUserSize())
            )
    )

    failArray = spider.users.getFailUsers()
    if len(failArray) > 0:
        print('失败的用户为: ' + str(failArray))


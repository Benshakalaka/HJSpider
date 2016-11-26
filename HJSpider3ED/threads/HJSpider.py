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
from threading import Thread
import requests
import time
import logging
import configparser



class Spider(Thread):
    # 初始化
    def __init__(self, user_name='', password='', isLogin=True, userQueue=None, uidQueue=None):
        super(Spider, self).__init__()

        self.config = configparser.ConfigParser()
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

        # 多线程使用的userQueue，此队列用于存储另外几个线程趴下来的用户信息实例，让此线程来存储
        self.userQueue = userQueue
        # 已经存储进数据库的数量
        self.userSavedCount = 0
        # 此队列用于存储此线程趴下来的uid， 供其他几个线程去爬取详细数据
        self.uidQueue = uidQueue

        # 日志初始化
        self.logger = logging.getLogger('hjspider.spider')

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
            self.users = ListenUsers(
                self.mysql_session, self.userLimit_Max,
                user_name, password,
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
    def run(self):
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

                        if self.isLogin is False:
                            self.logger.info('获取的用户uid为：%s ' % str(userUid))

                            self.uidQueue.put(userUid, block=True)

                            # 用户数量为 8 的倍数的时候调用一次
                            if self.users.getUserSize() & 7 == 0 :
                                self.UserInfoSave()
                        else:
                            self.logger.info('获取的用户uid为：%s ; 消耗时间为: %s' % (str(userUid), str(timeDelta)))

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

        if self.isLogin is False:
            # 达到限制或爬取结束后，队列中插入一个None，用以通知详细信息获取线程
            self.uidQueue.put(None, block=True)

            while self.userSavedCount < self.users.getUserSize():
                self.UserInfoSave()
                self.logger.info('目前已存储%d个用户；共有%d个用户；' % (self.userSavedCount, self.users.getUserSize()))

        self.logger.info('Productor : 此线程结束')
        return


    # 存储用户信息进入mysql
    # 依旧在爬取： 非阻塞获取user信息，存储进数据库
    # 如果因为数量限制而停止爬取了： 阻塞直到有信息且存入数据库
    def UserInfoSave(self):
        # 同时获取多个继而commit
        commitAmount = 0
        if self.isOverLimited is True:
            user = self.userQueue.get(block=True)
            # 每次最多20个， 多了出错rollback太伤
            commitAmount = qsize = min(self.userQueue.qsize(), 19)
            users = [user]
            while qsize > 0:
                users.append(self.userQueue.get(block=True))
                qsize -= 1
            commitAmount += 1
            self.mysql_session.add_all(users)

        else:
            try:
                user = self.userQueue.get_nowait()
                commitAmount = 1
            except:
                user = None

            if user is not None:
                self.mysql_session.add(user)

        try:
            self.mysql_session.commit()
        except:
            self.mysql_session.rollback()
            self.logger.fatal('数据库持久化失败')
            exit(-1)

        self.userSavedCount += commitAmount
        self.logger.info('此次添加 %d 个用户' % commitAmount)



if __name__ == "__main__":
    timeStart = time.time()
    # 使用那个账号登陆（一个编号对应一个账号）
    # spider = Spider(userCode='322')
    spider = Spider(isLogin=False)
    res = spider.run()
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


from models.ListenItem import ListenItem
from util import Utils
from bs4 import BeautifulSoup
import requests
import logging
import re

class ListenItems(object):
    '''
    input: 包含许多节目的页面URL
    output: 包含多个文章的某个页面的soup对象实例
    '''

    def __init__(self, mysql_session, limit):
        # 获取很多节目页面的地址列表
        self.fromUrls = list()
        # 下一个要访问的下标
        self.fromUrlsIndex = 0
        # 已访问的节目url
        self.itemUrls = set()
        # 与数据库的连接
        self.mysql_session = mysql_session
        # 访问节目数量限制
        self.limit = limit
        # 是否已经超时限制
        self.isOverLimited = False

        # 存储的类型为beautifulsoup的函数find_all返回的列表
        self.currentSoupList = []
        # 当前正在分析的节目(只有一个作用，当前节目的首页地址)
        self.currentSoup = None
        # 访问当前节目的第x页
        self.currentPageIndex = 1
        # 访问当前节目总共x页
        self.currentTotalPageCounts = 0
        # 节目实例是否已经被存储进数据库(延迟存储，因为所需属性在任意包含多个文章的页面)
        # 所以会在外部打算获取某页节目以获取多个文章的时候存储
        self.hasBeenSaved = False
        # 保存当前访问节目的信息
        self.currentItemInfo = None

        # 此模块日志
        self.logger = logging.getLogger('hjspider.item')

    # 获取一个节目的第n页包含多个文章的页面soup对象
    # 是哪个节目无法确定
    # skilfail：表示是否跳过访问失败的页面
    def getSomeArticlesPageSoup(self, index=0, skipfail=False):
        '''
        1. 获取当前节目总共页数
        2. 存储节目信息
        3. 获取并解析节目第index页html内容
        :return: BeautifulSoup类实例，已访问过返回None
        '''
        # 如果当前没有正在访问的节目
        if self.currentSoup is None:
            try:
                # 获取到包含多个节目页面某个节目的解析
                while True:
                    # 没有内容则抛出异常
                    self.currentSoup = self.currentSoupList.pop()
                    itemUrl = Utils.listenHost + self.currentSoup["href"]
                    if itemUrl not in self.itemUrls:
                        self.itemUrls.add(itemUrl)
                        break
            except Exception:
                # 没有节目了，看看fromUrl里有没有可以获取节目的页面
                self.currentSoup  = None
                if self.fromUrlsIndex >= len(self.fromUrls): return None
                currentFromUrl = self.fromUrls[self.fromUrlsIndex]
                self.fromUrlsIndex += 1
                try:
                    self.currentSoupList = self.getItemsFromUrl(currentFromUrl)
                    return self.getSomeArticlesPageSoup(index=index, skipfail=skipfail)
                except Exception:
                    self.logger.error('节目包含页面访问失败，地址： ' + currentFromUrl)
                    # 此页面访问失败后，若再次调用此函数，依旧访问此页面
                    if skipfail == False:
                        self.fromUrlsIndex -= 1
                    raise Exception

            # 既然换了节目，就要初始化一些属性
            self.currentItemInit()
        else:
            itemUrl = Utils.listenHost + self.currentSoup["href"]

        # 已经获取到了节目首页，现在要根据传入的index获取页面
        # index为0则表示自增
        index = max(0, int(index))
        index = self.currentPageIndex if index == 0 else index

        itemFullUrl = itemUrl + 'page' + str(index) + '/'

        try:
            articlesContent = requests.get(itemFullUrl, headers=Utils.headers)
            resSoup = BeautifulSoup(articlesContent.text, "lxml")
        except Exception as e:
            self.logger.error('获取某节目某页失败: ' + itemFullUrl)
            raise Exception

        # 如果是第一次访问这个节目（无论哪一页）,那么要做一些被延迟处理的事
        # 1. 持久化节目信息
        if self.hasBeenSaved is False:
            # 即使index非法，也能获取到节目信息
            try:
                self.currentItemInfo = self.getListenItemInfo(resSoup, itemFullUrl)
            except Exception:
                self.logger.error('节目信息存储失败: ' + itemFullUrl)
                raise Exception

            self.hasBeenSaved = True

        # 2. 获取总页数
        if self.currentTotalPageCounts == 0 :
            # 获取页数，若指定的index值过大，是无法获取到总页数的，即认为index非法
            self.currentTotalPageCounts = Utils.getPageCount(resSoup)
            # index非法，此次获取失败，恢复currentTotalPageCounts的值
            if index > self.currentTotalPageCounts:
                self.currentTotalPageCounts = 0
                return None

        # 如果指定了index，则下次访问index下一页
        # 默认访问下一页
        self.currentPageIndex = index + 1
        if self.currentPageIndex > self.currentTotalPageCounts:
            self.currentSoup = None

        # 如果当前节目访问完毕，且数量达到限制，那么设置超出位
        if self.currentSoup is None and self.getItemsSize() == self.limit:
            self.isOverLimited = True

        # 节目完整url（包含页码）， 该页的soup
        return (itemFullUrl, resSoup)



    # 添加一个fromUrl（包含很多节目的一个页面）
    # 返回True表示添加成功，失败则表示重复
    def appendFromUrl(self, fromUrl):
        if fromUrl in self.fromUrls:
            return False
        self.fromUrls.append(fromUrl)
        return True

    # 当前节目属性初始化
    def currentItemInit(self):
        self.currentPageIndex = 1
        self.currentTotalPageCounts = 0
        self.hasBeenSaved = False

    # 获取所有听写节目
    def getItemsFromUrl(self, fromUrl):
        try:
            itemsContent = requests.get(fromUrl, headers=Utils.headers)
            soup = BeautifulSoup(itemsContent.text, "lxml")
            list = soup.find_all(class_="menu_img fl")
        except Exception:
            self.logger.error('获取该页所有节目失败: ' + fromUrl)
            raise Exception

        return list


    # 爬取节目信息
    def getListenItemInfo(self, soup, url):

        item = ListenItem(url)

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

            if re.compile(r'状　态').search(text):
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
            self.logger.error('数据库存储节目失败')
            raise Exception

        self.logger.debug(item)
        return item

    # 已访问的节目数量
    def getItemsSize(self):
        return len(self.itemUrls)

    # 当前正在访问的节目url
    def getItemUrl(self):
        return Utils.listenHost + self.currentSoup["href"]

    # 接下来要访问第几页
    def getNextPageIndex(self):
        return self.currentPageIndex

    # 当前访问节目共多少页
    def getTotalPageCounts(self):
        return self.currentTotalPageCounts

    # 获取当前访问节目信息
    def getItem(self):
        return self.currentItemInfo

    # 节目数量是否超出限制
    def itemIsOverLimited(self):
        if self.isOverLimited is True:
            self.logger.warning('节目数量超出限制！')
        return self.isOverLimited
from models.ListenArticle import ListenArticle
from util import Utils
from bs4 import BeautifulSoup
import requests
import logging
import re

class ListenArticles(object):
    '''
    input: 包含许多文章的页面soup
    output: 某文章的uid
    '''
    def __init__(self, mysql_session):
        # 获取很多文章页面的地址列表与页面soup对象列表
        self.fromUrls = list()
        self.fromUrlsSoup = list()
        # 下次要访问的index
        self.fromUrlsIndex = 0
        # 已访问的文章url
        self.articleUrls = set()
        # 与数据库的连接
        self.mysql_session = mysql_session

        # 存储的类型为beautifulsoup的函数find_all返回的文章对象列表
        self.currentSoupList = []
        # 当前正在分析的文章(当前文章的地址，以及一些属性)
        self.currentSoup = None

        # 上一次访问的文章的实例
        self.lastArticle = None

        # 此模块日志
        self.logger = logging.getLogger('hjspider.article')

    # 添加一个fromUrl（包含很多文章的一个页面）
    # 返回True表示添加成功，失败则表示重复
    def appendFromUrl(self, fromUrl, fromSoup):
        if fromUrl in self.fromUrls:
            return False
        self.fromUrls.append(fromUrl)
        self.fromUrlsSoup.append(fromSoup)
        return True

    # 获取一个文章uid
    def getOneArticlePageSoup(self):
        try:
            while True:
                article = self.currentSoupList.pop()
                articleFullUrl = Utils.listenHost + article.find(class_='big search_titles')["href"]
                if articleFullUrl not in self.articleUrls:
                    self.articleUrls.add(articleFullUrl)
                    break
        except Exception:
            if self.fromUrlsIndex == len(self.fromUrls):
                return None
            try:
                self.currentSoupList = self.getArticlesFromUrl()
                self.fromUrlsIndex += 1
                return self.getOneArticlePageSoup()
            except Exception:
                self.logger.warning('获取文章失败，地址： ' + self.fromUrls[self.fromUrlsIndex])
                return None

        try:
            self.lastArticle = self.getListenArticleInfo(article, articleFullUrl, self.fromUrls[self.fromUrlsIndex])
        except Exception:
            self.logger.error('文章信息获取/存储失败，地址: ' + articleFullUrl)
            raise Exception

        return self.lastArticle.uid



    # 根据传来的包含多文章页面的soup对象，获取此页的所有文章对象
    def getArticlesFromUrl(self):
        try:
            list = self.fromUrlsSoup[self.fromUrlsIndex].find_all(class_='article_list_item')
        except Exception:
            raise Exception

        return list

    # 爬取文章信息
    # 某文章对象的soup实s.例， 文章地址， 所属节目地址(地址包含某页信息)
    def getListenArticleInfo(self, soup, articleUrl, itemUrl):
        article = ListenArticle(articleUrl)

        # 所属节目
        article.item = itemUrl.split('/')[-3]

        # 类型和标题
        article.type = soup.find(class_='big redlink nobold')['title']
        article.title = soup.find(class_='search_titles').get_text(strip=True)

        # 筛选出听写人数以及平均正确率
        text = soup.find(class_='info').get_text(strip=True)
        article.commentCount = re.compile('(\d+)次评论').search(text).group(1)
        article.averageScore = re.compile('(\d+)%').search(text).group(1)

        content = requests.get(articleUrl, headers=Utils.headers)

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
            #    article.downloadUrl = Utils.listenHost + li.span.find_all('a')[0]['href']
        article.downloadUrl = Utils.listenHost + '/download/' + articleUrl.split('/')[-2][2:8] + '/'

        try:
            article.save(self.mysql_session)
        except Exception:
            self.logger.error('数据库存储文章失败!')
            raise Exception

        return article

    # 获取当前已访问的文章
    def getArticleSize(self):
        return len(self.articleUrls)

    # 获取上一次的文章实例以获取更多信息
    def getArticle(self):
        return self.lastArticle

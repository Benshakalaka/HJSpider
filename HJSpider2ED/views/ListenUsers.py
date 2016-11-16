from models.ListenUser import ListenUser
from util import Utils
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote
import requests
import logging
import re
import json
import time

class ListenUsers(object):
    '''
    input: 某文章的uid
    output: 用户的uid
    '''
    def __init__(self, mysql_session, limit, loginUser, loginPass):
        # 此模块日志
        self.logger = logging.getLogger('hjspider.user')

        # 传入的要访问的文章uid
        self.fromUids = []
        # 下一个要访问的uid的下标
        self.fromUidsIndex = 0
        # 以访问的用户（包括私有用户）
        self.userUids = set()
        # 私有用户数量
        self.privateUids = 0
        # 访问用户数量限制
        self.limit = limit
        # 判断是否已超出限制
        self.isOverLimited = False
        # 因为某种原因添加进来的uid，需要提前访问（比如文章作者）
        self.uidsPriority = []

        # 当前的用户数组
        self.currentUsersSoupList = []
        # 下一次要访问的页数
        self.currentPageIndex = 1
        # 当前文章共有多少页用户
        self.currentTotalPageCounts = 0
        # 上一次访问的用户的信息
        self.lastUserInfo = None

        try:
            # 获取信息所需的登陆session
            self.session = Utils.userLogin(loginUser, loginPass)
        except Exception:
            self.logger.error('登陆失败!')
            exit(-1)
        # 数据库
        self.mysql_session = mysql_session



    # 添加文章uid
    def appendFromUid(self, articleUid):
        if articleUid in self.fromUids:
            return False
        self.fromUids.append(articleUid)
        return True

    # 根据传入的uid获取用户数组（BeautifulSoup实例数组）
    def getUsersFromUid(self, articleUid):
        if self.currentPageIndex != 1 and self.currentPageIndex > self.currentTotalPageCounts:
            return None

        #根据传入的uid获取ajax所需的参数
        commentId = articleUid[2:len(articleUid)-4]
        postUrl = 'http://ting.hujiang.com/ajax.do'

        form = {}
        form['classMethod'] = 'AjaxComs.GetListenedUserList'
        # 无论如何第一页总是有的
        form['param'] = [int(self.currentPageIndex), int(commentId), 0]
        form['pageName'] = None

        try:
            content = requests.post(postUrl, data=json.dumps(form), headers=Utils.jsonHeaders)
            contentText = content.text
            contentJson = json.loads(contentText)
        except Exception:
            self.logger.error('获取用户组失败: ' + postUrl)
            raise Exception

        self.currentPageIndex += 1

        # 获取总页数
        if self.currentTotalPageCounts == 0:
            try:
                listenUserCount = int(contentJson['d'][1])
            except:
                listenUserCount = 0

            self.currentTotalPageCounts = int(listenUserCount / 7)
            if listenUserCount % 7 != 0:
                self.currentTotalPageCounts += 1

            self.currentTotalPageCounts = max(1, self.currentTotalPageCounts)

        # 获取数组
        try:
            userInfoContainer = BeautifulSoup(contentJson['d'][2], "lxml")
            userList = userInfoContainer.find_all(class_='userListItemIcon')
        except Exception:
            self.logger.error('BeautifulSoup解析文章id的2-8位为' + str(form['param'][1]) + ' 第' + str(self.currentPageIndex - 1) + '页失败！')
            return None

        return userList


    # 获取单个用户的uid
    def getOneUserUid(self):

        # 首先从这个列表获取uid，没有再去找
        if len(self.uidsPriority) != 0:
            userUid = self.uidsPriority.pop()
            self.userUids.add(userUid)
        else:
            try:
                while True:
                    user = self.currentUsersSoupList.pop()
                    userUid = user.find('a')['userid']
                    if userUid not in self.userUids:
                        self.userUids.add(userUid)
                        break
            except Exception:
                if self.fromUidsIndex >= len(self.fromUids):
                    return None
                try:
                    articleUid = self.fromUids.pop()
                    self.currentUsersSoupList = self.getUsersFromUid(articleUid)
                    return self.getOneUserUid()
                except Exception:
                    return None

        getUserInfoStart = time.time()

        try:
            self.lastUserInfo = self.getUserInfo(userUid)
        except Exception:
            raise Exception

        getUserInfoEnd = time.time()

        if self.getUserSize() == self.limit:
            self.isOverLimited = True

        return userUid, getUserInfoEnd - getUserInfoStart


    # 获取用户信息
    def getUserInfo(self, uid):
        full_url = Utils.userHost + '/u/' + uid + '/'
        user = ListenUser(full_url)

        try:
            content = self.session.get(full_url, headers=Utils.headers, allow_redirects=False)
        except Exception:
            self.logger.error('获取用户页面失败: ' + full_url)
            return

        # 有的人将部落设置为隐私，外部不能访问，页面会302转向error
        if content.status_code != 200:
            self.privateUids += 1
            return

        try:
            soup = BeautifulSoup(content.text, "lxml")
        except Exception:
            self.logger.error('解析用户页面失败: ' + full_url)
            return

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

        try:
            user.save(self.mysql_session)
        except Exception:
            self.logger.error('存储用户信息失败')
            raise Exception

        self.logger.debug(user)
        return user

    # 因为某种原因添加进来的uid，需要优先访问
    def appendUidPriority(self, uid):
        # 不重复添加
        if uid in self.uidsPriority:
            return
        # 不添加已访问过的用户
        if uid in self.userUids:
            return
        self.uidsPriority.append(uid)

    # 获取已访问用户数量（不包括设置未隐私的用户）
    def getUserSize(self):
        return len(self.userUids) - self.privateUids

    # 获取上一次访问的用户信息
    def getUser(self):
        return self.lastUserInfo

    # 判断是否超出限制
    def userIsOverLimited(self):
        if self.isOverLimited is True:
            self.logger.warning('用户数量超出限制！')
        return self.isOverLimited
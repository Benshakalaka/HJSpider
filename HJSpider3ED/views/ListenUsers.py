from models.ListenUser import ListenUser
from util import Utils
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote
from threading import current_thread
import requests
import logging
import re
import json
import time
import datetime

class ListenUsers(object):
    '''
    input: 某文章的uid
    output: 用户的uid
    '''
    def __init__(self, mysql_session, limit, loginUser='', loginPass='', timeIntervalBase=0.5, failedToVisitCountLimit=5, isLogin=True):
        '''
        :param mysql_session:               数据库会话       required
        :param limit:                       用户数量限制     required
        :param loginUser:                   若要登陆，则需要传入用户名，密码
        :param loginPass:
        :param timeIntervalBase:            普通状态下每次sleep值， 或是 timeIntervalBase * 2 ** ? 的基数
        :param failedToVisitCountLimit:     用户页面访问失败后，重试的次数
        :param isLogin:                     是否需要用户登陆去访问网页
        :return:
        '''

        loggerName = 'hjspider.' + str(current_thread())
        self.logger = logging.getLogger(loggerName)

        # 传入的要访问的文章uid
        self.fromUids = []
        # 下一个要访问的uid的下标
        self.fromUidsIndex = 0
        # 以访问的用户（包括私有用户）
        self.userUids = set()
        # 访问用户数量限制
        self.limit = limit
        # 判断是否已超出限制
        self.isOverLimited = False
        # 因为某种原因添加进来的uid，需要提前访问（比如文章作者）
        self.uidsPriority = []

        # 当前在访问的文章uid
        self.currArticleUid = ''
        # 当前的用户数组
        self.currentUsersSoupList = []
        # 下一次要访问的页数
        self.currentPageIndex = 1
        # 当前文章共有多少页用户
        self.currentTotalPageCounts = 0
        # 上一次访问的用户的信息
        self.lastUserInfo = None
        # 上一次访问的用户，以及访问的次数（有时候因为某种原因，访问某用户页面频繁出错，一定次数后需放弃）
        self.lastUserVisitInfo = ['', 0]
        # 次数限制
        self.failedToVisitCountLimit = failedToVisitCountLimit
        # 访问失败的用户数组（不是设为隐私的用户，隐私用户自动放弃，可有些不是隐私却访问不到，这种要收集起来）
        self.failedToVisit = []
        # 是否需要登陆
        self.isLogin = isLogin
        if isLogin is True and loginUser == '' and loginPass == '':
            self.logger.error('username or password is needed !')
            exit(-1)

        try:
            # 获取信息所需的登陆session
            self.session = Utils.userLogin(loginUser, loginPass) if isLogin is True else None
        except Exception:
            self.logger.error('登陆失败!')
            exit(-1)
        # 数据库
        self.mysql_session = mysql_session

        # 在网站返回"访问太频繁"的消息后，时间间隔乘2
        self.tooFrequent = 0
        self.timeIntervalBase = float(timeIntervalBase)

    # 获取下一次的文章uid（可能因为没访问完而不变，也有可能访问完了变化）
    @property
    def articleUid(self):
        if self.currentPageIndex > self.currentTotalPageCounts:
            if self.fromUidsIndex >= len(self.fromUids):
                return None
            else:
                self.currArticleUid = self.fromUids.pop()
                self.currentPageIndex = 1
                self.currentTotalPageCounts = 0

        return self.currArticleUid


    # 获取每次要沉睡的间隔
    @property
    def time2sleep(self):
        return self.timeIntervalBase * 2 ** self.tooFrequent

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
    def getOneUserUid(self, frequentAdd=1, frequentReduce=2):

        # 首先从这个列表获取uid，没有再去找
        if len(self.uidsPriority) != 0:
            userUid = self.uidsPriority.pop()
        else:
            try:
                while True:
                    user = self.currentUsersSoupList.pop()
                    userUid = user.find('a')['userid']
                    if userUid not in self.userUids:
                        break
            except Exception:
                articleUid = self.articleUid
                if articleUid is None:
                    return None

                try:
                    self.currentUsersSoupList = self.getUsersFromUid(articleUid)
                    return self.getOneUserUid()
                except Exception:
                    return None

        # 获取到uid即将此uid放入set，以后不会在访问
        # 不用担心在某uid被加入优先队列后会有重复id出现在currentUsersSoupList中，因为优先队列永远是优先访问的
        self.userUids.add(userUid)

        deltaInfoGet = 0
        if self.isLogin is True:
            getUserInfoStart = time.time()

            try:
                lastUserInfo = self.getUserInfo(userUid, frequentAdd, frequentReduce)
                self.lastUserInfo = lastUserInfo if lastUserInfo is not None else self.lastUserInfo
            except Exception:
                raise Exception

            getUserInfoEnd = time.time()
            deltaInfoGet = getUserInfoEnd - getUserInfoStart

        if self.getUserSize() == self.limit:
            self.isOverLimited = True

        return userUid, deltaInfoGet


    # 获取用户信息
    def getUserInfo(self, uid, frequentAdd=1, frequentReduce=2):
        # 沉睡间隔
        t2s = self.time2sleep
        if t2s >= 2.0:
            self.logger.warning('程序将沉睡'+str(t2s) + '秒以避免访问过于频繁')

        time.sleep(t2s)

        full_url = Utils.userHost + '/u/' + uid + '/'
        try:
            content = self.session.get(full_url, headers=Utils.headers, allow_redirects=False)
        except Exception:
            self.logger.error('获取用户页面失败: ' + full_url)
            return None

        # 有的人将部落设置为隐私，外部不能访问，页面会302转向error
        if content.status_code != 200:
            self.logger.warning(full_url + ': redirect ' + str(content.status_code))
            responseText = urlparse(unquote(content.headers['Location'])).query.split('=', maxsplit=1)[1]
            self.logger.warning('提示: ' + responseText)

            if responseText[0:2] == '用户':
                user = self.getPrivateUserInfo(uid)

                if self.tooFrequent > 0:
                    self.tooFrequent -= frequentReduce
                self.tooFrequent = 0 if self.tooFrequent < 0 else self.tooFrequent

                self.logger.debug(user)
                return user
            else:
                # 某用户页面访问次数限制
                if self.lastUserVisitInfo[0] == uid:
                    self.lastUserVisitInfo[1] += 1
                else:
                    self.lastUserVisitInfo[0] = uid
                    self.lastUserVisitInfo[1] = 0

                # 满足次数要求的话，就放进优先队列等待下一次重试访问
                if self.lastUserVisitInfo[1] <= self.failedToVisitCountLimit:
                    # 不能存进userAll, 而是放进放进uidsPriority数组等待重新访问
                    self.appendUidPriority(uid)
                else:
                    # 记录失败的访问用户
                    self.failedToVisit.append(uid)

                # 如果第一次遇到这种情况，最好睡眠时间快速增长，之后缓慢增长
                if self.tooFrequent == 0:
                    self.tooFrequent = 4
                else:
                    self.tooFrequent += frequentAdd

                self.logger.warning('太频繁了，我想把它塞回去，长度是 %d' % self.getPriorityLength())

                return None

        # 如果此时的返回不是过于频繁，那么等待时间即可缩小一倍
        if self.tooFrequent > 0:
            self.tooFrequent -= frequentReduce
        self.tooFrequent = 0 if self.tooFrequent < 0 else self.tooFrequent

        user = self.getNormalUserInof(uid, content)
        self.logger.debug(user)
        return user

    # 获取普通用户信息
    def getNormalUserInof(self, uid, content):
        full_url = Utils.userHost + '/u/' + uid + '/'
        user = ListenUser(full_url)

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

        return user

    # 获取隐私用户信息
    def getPrivateUserInfo(self, uid):
        user = ListenUser(Utils.userHost + '/u/' + uid + '/')
        # 若为私有，需要换种访问信息的方式
        user.isPrivate = 1

        # 如下jsonp可用于获取部分信息
        # encodeUri后：http://bulo.hujiang.com/service/GetUserFace.ashx?ver=2016/11/23%20%E4%B8%8B%E5%8D%888:29:28&userId=5326257&callback=jQuery17202552129787287378_1479904148908&_=1479904168992
        # decodeUri后：http://bulo.hujiang.com/service/GetUserFace.ashx?ver=2016/11/23 下午8:29:28&userId=5326257&callback=jQuery17202552129787287378_1479904148908&_=1479904168992
        queryParams = {}
        nt = datetime.datetime.now()
        currHour = int(datetime.datetime.now().hour)
        verTime = nt.strftime('%Y/%m/%d {half}%I:%M:%S').format(half=('上午' if currHour < 12 else '下午'))
        queryParams['ver'] = verTime
        queryParams['userId'] = uid
        timeStamp = ''.join(str(time.time()).split('.'))[:13]
        queryParams['callback'] = 'jQuery17202552129787287378_' + str(timeStamp)
        queryParams['_'] = str(timeStamp)
        info_url = Utils.urlCreate(Utils.userHost + '/service/GetUserFace.ashx?', queryParams)

        try:
            infoRespond = requests.get(info_url, headers=Utils.headers)
        except Exception:
            self.logger.error('隐私用户信息获取失败: ' + uid)
            return None

        infoRespondStr = infoRespond.text.split('(', maxsplit=1)[1][:-1]
        infoRespondJson = json.loads(infoRespondStr)

        user.name = infoRespondJson['UserName'] if 'UserName' in infoRespondJson else ''
        user.nickName = infoRespondJson['NickName'][1:-1] if 'NickName' in infoRespondJson else ''
        user.signature = infoRespondJson['UserSign'] if 'UserSign' in infoRespondJson else ''
        user.city = infoRespondJson['city'] if 'city' in infoRespondJson else ''
        user.signinLast = infoRespondJson['PunchCount'] if 'PunchCount' in infoRespondJson else ''
        gender = infoRespondJson['Gender'] if 'PunchCount' in infoRespondJson else ''
        if gender == '1' or gender == '0':
            user.gender = '男' if gender == '1' else '女'

        try:
            user.save(self.mysql_session)
        except Exception:
            self.logger.error('存储隐私用户信息失败')
            raise Exception

        return user

    # 因为某种原因添加进来的uid，需要优先访问
    def appendUidPriority(self, uid):
        # 不重复添加
        if uid in self.uidsPriority:
            return
        # 不添加已访问过的用户
        # 由于在取得uid后就将此uid添加进了userUids集合中，若在之后访问过程中遇到过于频繁错误，那么
        #
        if uid in self.userUids and self.lastUserVisitInfo[0] != uid:
            return
        self.uidsPriority.append(uid)

    # 获取当前优先队列中uid的数量
    def getPriorityLength(self):
        return len(self.uidsPriority)

    # 获取已访问用户数量（不包含多次访问失败的用户）
    def getUserSize(self):
        return len(self.userUids) - len(self.failedToVisit)

    # 获取总共访问的用户数量
    def getAllUserSize(self):
        return len(self.userUids)

    # 获取失败的用户数组
    def getFailUsers(self):
        return self.failedToVisit

    # 获取上一次成功访问的用户的信息
    def getUser(self):
        return self.lastUserInfo

    # 判断是否超出限制
    def userIsOverLimited(self):
        if self.isOverLimited is True:
            self.logger.warning('用户数量超出限制！')
        return self.isOverLimited